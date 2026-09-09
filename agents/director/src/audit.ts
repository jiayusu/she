// 审计日志(非功能):全部调度决策留痕 —— 路由理由 / 注入内容摘要 / 写库结果。
// 按天写 JSONL(data/audit/audit-YYYYMMDD.jsonl),支持按日期/类型/条数查询。

import { appendFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { dayOf, readJsonlSync } from './util.ts';

export type AuditType =
  | 'learning_loop'
  | 'dispatch'
  | 'map_reload'
  | 'memory_write'
  | 'dlq'
  | 'dlq_retry'
  | 'whitelist_add'
  | 'consolidation'
  | 'job_run'
  | 'session_rebuild'
  | 'tool_invoke';

export interface AuditRecord {
  ts: number;
  type: AuditType;
  route_id?: string;
  session_id?: string;
  route?: {
    intent: string;
    minister: string;
    confidence: number;
    reason: string;
    fallback_used: boolean;
    need_clarify?: boolean;
  };
  ctx_summary?: { budget: number; tokens_used: number; turns: number; today_words: number; notes: string[] };
  write_results?: Array<{ id: string; store: string; ok: boolean; attempts: number; dead_letter?: boolean; pending_review?: boolean }>;
  detail?: Record<string, unknown>;
}

export class AuditLog {
  constructor(private dataDir: string) {}

  private fileFor(ts: number): string {
    return join(this.dataDir, 'audit', `audit-${dayOf(ts)}.jsonl`);
  }

  append(rec: AuditRecord): void {
    try {
      const file = this.fileFor(rec.ts);
      mkdirSync(dirname(file), { recursive: true });
      appendFileSync(file, JSON.stringify(rec) + '\n', 'utf8');
    } catch {
      // 审计写失败不允许阻塞调度主链路
    }
  }

  query(opts: { date?: string; type?: AuditType; limit?: number } = {}): AuditRecord[] {
    const files = this.listFiles(opts.date);
    let out: AuditRecord[] = [];
    for (const f of files) {
      for (const line of readJsonlSync(f)) {
        const rec = line as unknown as AuditRecord;
        if (opts.type && rec.type !== opts.type) continue;
        out.push(rec);
      }
    }
    out = out.sort((a, b) => a.ts - b.ts);
    return opts.limit ? out.slice(-opts.limit) : out;
  }

  private listFiles(date?: string): string[] {
    const dir = join(this.dataDir, 'audit');
    if (date) {
      const f = join(dir, `audit-${date}.jsonl`);
      return existsSync(f) ? [f] : [];
    }
    if (!existsSync(dir)) return [];
    return readdirSync(dir)
      .filter((n) => n.startsWith('audit-') && n.endsWith('.jsonl'))
      .sort()
      .map((n) => join(dir, n));
  }
}
