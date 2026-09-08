// FR-G06 巩固触发器(每周批量):扫描阿海情景库中"出现 ≥3 次且评估通过"的词,
// 生成 diff 报告;人工一键确认后经 KG 热更新接口写入老颞语义层。
// 孩子无感知;每周自动产出 diff 报告(默认 draft 状态,不自动生效)。

import { randomUUID } from 'node:crypto';
import type { StoreRegistry } from './stores/local.ts';
import type { SemanticKG } from './stores/kg.ts';
import type { Metrics } from './metrics.ts';
import type { AuditLog } from './audit.ts';
import type { StoredMemory } from './salience.ts';
import type { EventEmitter } from 'node:events';

export const CONSOLIDATION_MIN_COUNT = 3;

export interface ConsolidationCandidate {
  word: string;
  count: number;
  evals_passed: number;
  evals_total: number;
}

export interface ConsolidationReport {
  id: string;
  created_at: number;
  status: 'draft' | 'confirmed' | 'empty';
  candidates: ConsolidationCandidate[];
  existing: string[];          // 已在语义层,无需重复巩固
  rejected: ConsolidationCandidate[]; // 次数不足或评估未通过
  applied?: { words: number };
}

export class ConsolidationService {
  private reports = new Map<string, ConsolidationReport>();

  constructor(
    private stores: StoreRegistry,
    private kg: SemanticKG,
    private metrics: Metrics,
    private audit: AuditLog,
    private bus: EventEmitter,
    private dataDir: string,
  ) {}

  /** 扫描情景库,产出(或复用同批次)diff 报告。同一自然周内重复触发返回缓存报告。 */
  runDraft(): ConsolidationReport {
    const cached = this.findDraftThisWeek();
    if (cached) return cached;

    const byWord = new Map<string, { count: number; passed: number; total: number }>();
    for (const mem of this.stores.get('episodic').all()) {
      if (mem.kind !== 'word_learned') continue;
      const word = mem.payload.word;
      if (typeof word !== 'string' || !word) continue;
      const evalResult = mem.payload.eval;
      const agg = byWord.get(word) ?? { count: 0, passed: 0, total: 0 };
      agg.count++;
      if (evalResult !== undefined) {
        agg.total++;
        if (evalResult === 'passed') agg.passed++;
      }
      byWord.set(word, agg);
    }

    const candidates: ConsolidationCandidate[] = [];
    const rejected: ConsolidationCandidate[] = [];
    const existing: string[] = [];
    for (const [word, agg] of byWord) {
      const item: ConsolidationCandidate = {
        word,
        count: agg.count,
        evals_passed: agg.passed,
        evals_total: agg.total,
      };
      if (this.kg.hasWord(word)) {
        existing.push(word);
      } else if (agg.count >= CONSOLIDATION_MIN_COUNT && (agg.total === 0 || agg.passed === agg.total)) {
        // 出现 ≥3 次且评估通过(无评估记录的旧数据按次数放行)
        candidates.push(item);
      } else {
        rejected.push(item);
      }
    }

    candidates.sort((a, b) => b.count - a.count);
    const report: ConsolidationReport = {
      id: `cons_${new Date().toISOString().slice(0, 10)}_${randomUUID().slice(0, 8)}`,
      created_at: Date.now(),
      status: candidates.length > 0 ? 'draft' : 'empty',
      candidates,
      existing,
      rejected,
    };
    this.reports.set(report.id, report);
    this.audit.append({
      ts: Date.now(),
      type: 'consolidation',
      detail: { action: 'draft', report_id: report.id, candidates: candidates.length, existing: existing.length },
    });
    return report;
  }

  private findDraftThisWeek(): ConsolidationReport | null {
    const weekStart = startOfWeek(Date.now());
    for (const r of this.reports.values()) {
      if (r.status === 'draft' && r.created_at >= weekStart) return r;
    }
    return null;
  }

  getReport(id: string): ConsolidationReport | null {
    return this.reports.get(id) ?? null;
  }

  listReports(): ConsolidationReport[] {
    return [...this.reports.values()].sort((a, b) => b.created_at - a.created_at);
  }

  /** 人工一键确认:diff 报告生效,词经热更新接口进老颞语义层。 */
  confirm(reportId: string): { applied: number; report: ConsolidationReport | null } {
    const report = this.reports.get(reportId);
    if (!report) return { applied: 0, report: null };
    if (report.status !== 'draft') return { applied: 0, report };

    const res = this.kg.hotUpdate({
      words: report.candidates.map((c) => ({ word: c.word, examples: c.count })),
    });
    report.status = 'confirmed';
    report.applied = { words: res.words };
    this.metrics.consolidateBatch(res.words);
    this.bus.emit('consolidation_confirmed', { report_id: report.id, words: res.words });
    this.audit.append({
      ts: Date.now(),
      type: 'consolidation',
      detail: { action: 'confirmed', report_id: report.id, words: res.words },
    });
    return { applied: res.words, report };
  }

  /** 崩溃恢复:从落盘报告回放(报告写 data/reports/)。 */
  restoreReport(report: ConsolidationReport): void {
    this.reports.set(report.id, report);
  }

  /** 供元认知 review 使用的情景词统计快照。 */
  episodicWordStats(): Array<{ word: string; count: number }> {
    const m = new Map<string, number>();
    for (const mem of this.stores.get('episodic').all() as StoredMemory[]) {
      if (mem.kind !== 'word_learned') continue;
      const w = mem.payload.word;
      if (typeof w === 'string') m.set(w, (m.get(w) ?? 0) + 1);
    }
    return [...m.entries()].map(([word, count]) => ({ word, count })).sort((a, b) => b.count - a.count);
  }
}

export function startOfWeek(ts: number): number {
  const d = new Date(ts);
  const day = (d.getDay() + 6) % 7; // 周一为一周开始
  d.setHours(0, 0, 0, 0);
  return d.getTime() - day * 24 * 3600 * 1000;
}
