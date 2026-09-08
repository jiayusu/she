// 五库适配器(对接 04 记忆存储的写入接口)。本模块内为内存 + JSONL 落盘的本地实现,
// 替换为 04 的远程实现时只需实现 MemoryStoreAdapter 接口。
// 支持注入故障(failureRate / failEveryNth)以便测试 FR-G04 的重试与死信路径。

import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { StoreId } from '../types.ts';
import type { StoredMemory } from '../salience.ts';

export interface MemoryStoreAdapter {
  readonly id: StoreId;
  write(mem: StoredMemory): Promise<void>;
  all(): StoredMemory[];
  get(id: string): StoredMemory | null;
  update(id: string, patch: Partial<StoredMemory>): void;
  delete(id: string): boolean;
  stats(): { count: number; failures: number };
}

export interface StoreFaultCfg {
  /** 每次写尝试的随机失败概率 0..1 */
  failureRate?: number;
  /** 每 N 次写尝试固定失败一次(确定性故障,测试用) */
  failEveryNth?: number;
}

export class LocalMemoryStore implements MemoryStoreAdapter {
  private items = new Map<string, StoredMemory>();
  private attempts = 0;
  failures = 0;

  private rng: () => number = Math.random;

  constructor(
    readonly id: StoreId,
    private dataDir: string,
    private fault: StoreFaultCfg = {},
  ) {
    this.loadFromDisk();
  }

  private file(): string {
    return join(this.dataDir, 'stores', `${this.id}.jsonl`);
  }

  private loadFromDisk(): void {
    const f = this.file();
    if (!existsSync(f)) return;
    for (const line of readFileSync(f, 'utf8').split('\n')) {
      const t = line.trim();
      if (!t) continue;
      try {
        const ev = JSON.parse(t) as { op: 'put' | 'del'; mem?: StoredMemory; id?: string };
        if (ev.op === 'put' && ev.mem) this.items.set(ev.mem.id, ev.mem);
        if (ev.op === 'del' && ev.id) this.items.delete(ev.id);
      } catch {
        // 崩溃留下的尾部半行,忽略
      }
    }
  }

  private persist(op: 'put' | 'del', mem?: StoredMemory, id?: string): void {
    const f = this.file();
    mkdirSync(dirname(f), { recursive: true });
    appendFileSync(f, JSON.stringify(op === 'put' ? { op, mem } : { op, id }) + '\n', 'utf8');
  }

  private attemptGuard(): void {
    this.attempts++;
    const { failureRate, failEveryNth } = this.fault;
    // 第 1、N+1、2N+1…次尝试失败:模拟"每次写都失败,靠重试恢复"
    if (failEveryNth && (this.attempts - 1) % failEveryNth === 0) {
      this.failures++;
      throw new Error(`store ${this.id} transient failure (nth=${this.attempts})`);
    }
    if (failureRate && this.rng() < failureRate) {
      this.failures++;
      throw new Error(`store ${this.id} transient failure (rate)`);
    }
  }

  async write(mem: StoredMemory): Promise<void> {
    this.attemptGuard();
    this.items.set(mem.id, mem);
    this.persist('put', mem);
  }

  all(): StoredMemory[] {
    return [...this.items.values()];
  }

  get(id: string): StoredMemory | null {
    return this.items.get(id) ?? null;
  }

  update(id: string, patch: Partial<StoredMemory>): void {
    const cur = this.items.get(id);
    if (!cur) return;
    this.items.set(id, { ...cur, ...patch });
    this.persist('put', this.items.get(id));
  }

  delete(id: string): boolean {
    if (!this.items.has(id)) return false;
    this.items.delete(id);
    this.persist('del', undefined, id);
    return true;
  }

  setFault(fault: StoreFaultCfg): void {
    this.fault = fault;
  }

  /** 测试注入确定性随机源(配 failureRate 用)。 */
  setRng(rng: () => number): void {
    this.rng = rng;
  }

  stats(): { count: number; failures: number } {
    return { count: this.items.size, failures: this.failures };
  }
}

export class StoreRegistry {
  private stores = new Map<StoreId, MemoryStoreAdapter>();

  register(store: MemoryStoreAdapter): void {
    this.stores.set(store.id, store);
  }

  get(id: StoreId): MemoryStoreAdapter {
    const s = this.stores.get(id);
    if (!s) throw new Error(`store 未注册: ${id}`);
    return s;
  }

  ids(): StoreId[] {
    return [...this.stores.keys()];
  }
}

/** "永不遗忘"白名单(FR-G05):只增不删,人工可增不可减 —— 故意不提供任何删除方法。 */
export interface WhitelistItem {
  id: string;
  ref_id: string;      // 关联的记忆条目 id(手工加入时可自拟)
  reason: string;
  score: number;
  source: 'auto' | 'manual';
  ts: number;
}

export class NeverForgetWhitelist {
  private items = new Map<string, WhitelistItem>();

  constructor(private dataDir: string) {
    const f = join(dataDir, 'whitelist.json');
    if (existsSync(f)) {
      try {
        const arr = JSON.parse(readFileSync(f, 'utf8')) as WhitelistItem[];
        for (const it of arr) this.items.set(it.id, it);
      } catch {
        // 白名单文件损坏时保持空载;jsonl 审计仍有记录
      }
    }
  }

  add(item: Omit<WhitelistItem, 'id' | 'ts'>): { added: boolean; item: WhitelistItem } {
    const full: WhitelistItem = { ...item, id: `wf_${item.ref_id}`, ts: Date.now() };
    let added = false;
    if (!this.items.has(full.id)) {
      this.items.set(full.id, full);
      added = true;
      this.persist();
    }
    return { added, item: this.items.get(full.id)! };
  }

  has(refId: string): boolean {
    return this.items.has(`wf_${refId}`);
  }

  list(): WhitelistItem[] {
    return [...this.items.values()].sort((a, b) => a.ts - b.ts);
  }

  private persist(): void {
    const f = join(this.dataDir, 'whitelist.json');
    mkdirSync(dirname(f), { recursive: true });
    writeFileSync(f, JSON.stringify(this.list(), null, 2), 'utf8');
  }
}
