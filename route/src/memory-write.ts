// FR-G04 记忆写调度:接收剧情引擎(01)的 memory_write[],按大臣归属分发到五库(04 写入接口)。
// 链路:归属校验 → 显著性打标(FR-G05)→ 事实校验(与 KG 冲突标待审)→ 写库 →
// 失败重试 1 次 → 仍失败入死信队列(DLQ)并告警(WS 事件 + 埋点 + 审计)。
// 白名单命中(FR-G05)同步登记;全部结果回写 memory_write_ack。

import { EventEmitter } from 'node:events';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type {
  Emotion,
  MemoryWriteEntry,
  MinisterId,
  StoreId,
  WriteAckItem,
} from './types.ts';
import { MINISTER_STORE } from './types.ts';
import { newId, dayOf, readJsonlSync } from './util.ts';
import type { SalienceEngine, StoredMemory } from './salience.ts';
import type { StoreRegistry } from './stores/local.ts';
import type { NeverForgetWhitelist } from './stores/local.ts';
import type { SemanticKG } from './stores/kg.ts';
import type { AuditLog } from './audit.ts';
import type { Metrics } from './metrics.ts';

const MAX_ATTEMPTS = 2; // 首写 + 重试 1 次(PRD 验收口径)

export interface DeadLetter {
  id: string;
  entry: MemoryWriteEntry;
  error: string;
  attempts: number;
  day: string;
  ts: number;
}

export interface WriteContext {
  emotion?: Emotion;
  session_id?: string;
}

export class MemoryWriteScheduler {
  private dlq: DeadLetter[] = [];

  constructor(
    private stores: StoreRegistry,
    private salience: SalienceEngine,
    private whitelist: NeverForgetWhitelist,
    private kg: SemanticKG,
    private audit: AuditLog,
    private metrics: Metrics,
    private bus: EventEmitter,
    private dataDir: string,
  ) {
    this.loadDlq();
  }

  private dlqFile(): string {
    return join(this.dataDir, 'dlq.jsonl');
  }

  private loadDlq(): void {
    for (const line of readJsonlSync(this.dlqFile())) {
      this.dlq.push(line as unknown as DeadLetter);
    }
  }

  private persistDlq(): void {
    // DLQ 全量重写,保证 retryAll 后文件与内存一致
    const f = this.dlqFile();
    mkdirSync(dirname(f), { recursive: true });
    writeFileSync(f, this.dlq.map((i) => JSON.stringify(i)).join('\n') + (this.dlq.length ? '\n' : ''), 'utf8');
  }

  resolveStore(entry: MemoryWriteEntry): StoreId {
    if (entry.store) return entry.store;
    if (entry.minister) return MINISTER_STORE[entry.minister];
    throw new Error('memory_write 条目缺少 store 且无法从 minister 推导');
  }

  validateEntry(entry: MemoryWriteEntry): string | null {
    if (!entry || typeof entry !== 'object') return '条目必须是对象';
    if (!entry.kind) return '缺少 kind';
    if (!entry.payload || typeof entry.payload !== 'object') return '缺少 payload';
    if (entry.store && entry.minister) {
      const expected = MINISTER_STORE[entry.minister];
      if (expected !== entry.store) {
        return `store(${entry.store}) 与 minister(${entry.minister}) 归属不符,应为 ${expected}`;
      }
    }
    return null;
  }

  async submit(entries: MemoryWriteEntry[], ctx: WriteContext = {}): Promise<WriteAckItem[]> {
    const acks: WriteAckItem[] = [];
    for (const entry of entries ?? []) {
      acks.push(await this.processOne(entry, ctx));
    }
    return acks;
  }

  private async processOne(entry: MemoryWriteEntry, ctx: WriteContext): Promise<WriteAckItem> {
    const id = entry.id ?? newId('mw_');
    const invalid = this.validateEntry(entry);
    if (invalid) {
      const ack: WriteAckItem = { id, store: 'working', ok: false, attempts: 0, salience: 0, whitelisted: false, error: invalid };
      this.audit.append({ ts: Date.now(), type: 'memory_write', session_id: ctx.session_id, write_results: [ack], detail: { reason: invalid } });
      return ack;
    }

    let store: StoreId;
    try {
      store = this.resolveStore(entry);
    } catch (e) {
      const ack: WriteAckItem = { id, store: 'working', ok: false, attempts: 0, salience: 0, whitelisted: false, error: (e as Error).message };
      return ack;
    }

    // FR-G05 显著性打标
    const verdict = this.salience.evaluate(entry, { emotion: ctx.emotion });

    // 风险对策:语义事实先过 KG 冲突校验,冲突则标待审,不直接固化
    let pendingReview = false;
    if (store === 'semantic' && entry.kind === 'fact' && isFactShape(entry.payload)) {
      const fact = entry.payload.fact as { subject: string; predicate: string; object: string };
      const check = this.kg.checkConflict(fact);
      if (check.conflict) {
        this.kg.submitForReview(fact, check.existing_object!);
        pendingReview = true;
      }
    }

    let attempts = 0;
    let lastError: string | undefined;
    const adapter = this.stores.get(store);

    if (!pendingReview) {
      while (attempts < MAX_ATTEMPTS) {
        attempts++;
        try {
          const mem: StoredMemory = {
            id,
            store,
            minister: entry.minister,
            kind: entry.kind,
            payload: entry.payload,
            salience: verdict.score,
            reasons: verdict.reasons,
            ts: entry.ts ?? Date.now(),
            last_access: Date.now(),
          };
          await adapter.write(mem);
          lastError = undefined;
          break;
        } catch (e) {
          lastError = (e as Error).message;
        }
      }
    }

    let deadLetter = false;
    if (!pendingReview && lastError) {
      deadLetter = true;
      const dl: DeadLetter = {
        id,
        entry,
        error: lastError,
        attempts,
        day: dayOf(Date.now()),
        ts: Date.now(),
      };
      this.dlq.push(dl);
      this.persistDlq();
      // 告警:WS 事件 + 审计
      this.bus.emit('dlq_alert', { id, store, error: lastError, session_id: ctx.session_id });
      this.audit.append({
        ts: Date.now(),
        type: 'dlq',
        session_id: ctx.session_id,
        detail: { id, store, error: lastError, attempts },
      });
    }

    // FR-G05:显著性达标 → 永不遗忘白名单
    let whitelisted = false;
    if (!lastError || pendingReview) {
      if (verdict.whitelisted) {
        const res = this.whitelist.add({
          ref_id: id,
          reason: verdict.reasons.join(' + ') || '显著性达标',
          score: verdict.score,
          source: 'auto',
        });
        whitelisted = res.added || this.whitelist.has(id);
        if (res.added) this.bus.emit('whitelist_added', { ref_id: id, score: verdict.score });
      }
    }

    const ack: WriteAckItem = {
      id,
      store,
      ok: !lastError,
      attempts,
      salience: verdict.score,
      whitelisted,
      pending_review: pendingReview || undefined,
      dead_letter: deadLetter || undefined,
      error: lastError,
    };

    this.metrics.memoryWrite(store, ack.ok);
    this.audit.append({
      ts: Date.now(),
      type: 'memory_write',
      session_id: ctx.session_id,
      write_results: [ack],
      detail: { kind: entry.kind, salience: verdict.score, reasons: verdict.reasons },
    });
    return ack;
  }

  // ---- 死信队列运维(验收:死信当日清零) ----

  listDlq(): DeadLetter[] {
    return [...this.dlq];
  }

  openDlqCount(): number {
    return this.dlq.length;
  }

  /** 重推全部死信;返回 {retried, recovered}。 */
  async retryDlq(ctx: WriteContext = {}): Promise<{ retried: number; recovered: number }> {
    const items = [...this.dlq];
    this.dlq = [];
    let recovered = 0;
    for (const dl of items) {
      const ack = await this.processOne(dl.entry, ctx);
      if (ack.ok) recovered++;
      else {
        this.dlq.push({ ...dl, attempts: ack.attempts, ts: Date.now() });
      }
    }
    this.persistDlq();
    this.audit.append({ ts: Date.now(), type: 'dlq_retry', detail: { retried: items.length, recovered, open: this.dlq.length } });
    return { retried: items.length, recovered };
  }

  /** 当日清零巡检:重推全部在队死信(验收:死信当日清零)。 */
  async sweepDlq(ctx: WriteContext = {}): Promise<{ cleared: boolean; open: number }> {
    await this.retryDlq(ctx);
    return { cleared: this.dlq.length === 0, open: this.dlq.length };
  }
}

function isFactShape(payload: Record<string, unknown>): boolean {
  const f = payload.fact as { subject?: unknown; predicate?: unknown; object?: unknown } | undefined;
  return !!f && typeof f.subject === 'string' && typeof f.predicate === 'string' && typeof f.object === 'string';
}

export type { MinisterId };
