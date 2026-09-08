// FR-G07 元认知三 agent:
//   复盘 review      —— 每周剧情质量报告(意图分布 / 澄清率 / 延迟 / 写入成功率)
//   遗忘剪枝 prune   —— 低显著性记忆按 EMA 置信度衰减,低于地板删除;白名单豁免
//   巩固触发 consolidate —— FR-G06 的调度壳(每周自动 draft,确认仍需人工)
// 三任务均可观测(状态/历史)、可手动触发(POST /admin/jobs/:name/trigger)。

import { EventEmitter } from 'node:events';
import { join } from 'node:path';
import { writeJson } from './util.ts';
import type { AuditLog } from './audit.ts';
import type { Metrics } from './metrics.ts';
import type { SalienceEngine } from './salience.ts';
import type { StoreRegistry } from './stores/local.ts';
import type { NeverForgetWhitelist } from './stores/local.ts';
import type { ConsolidationService, ConsolidationReport } from './consolidation.ts';

export interface JobResult {
  ok: boolean;
  ran_at: number;
  duration_ms: number;
  summary: Record<string, unknown>;
  error?: string;
}

export interface JobView {
  name: string;
  description: string;
  schedule: string;
  enabled: boolean;
  last?: JobResult;
  history: JobResult[];
}

export interface Job {
  name: 'review' | 'prune' | 'consolidate';
  description: string;
  schedule: string;
  run(): Promise<Record<string, unknown>>;
}

const HISTORY_CAP = 20;

export class JobScheduler {
  private jobs = new Map<string, Job>();
  private last = new Map<string, JobResult>();
  private history = new Map<string, JobResult[]>();
  private timer: NodeJS.Timeout | null = null;

  constructor(private bus: EventEmitter) {}

  register(job: Job): void {
    this.jobs.set(job.name, job);
  }

  get(name: string): Job | undefined {
    return this.jobs.get(name);
  }

  start(intervalMs = 60_000): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.tick(), intervalMs);
    this.timer.unref?.();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /** 每分钟检查一次周/日任务是否到期(到点自动补跑一次)。 */
  private async tick(): Promise<void> {
    for (const job of this.jobs.values()) {
      const lastRun = this.last.get(job.name)?.ran_at ?? 0;
      if (due(job.schedule, lastRun)) {
        await this.triggerNow(job.name).catch(() => {});
      }
    }
  }

  async triggerNow(name: string): Promise<JobResult> {
    const job = this.jobs.get(name);
    if (!job) throw new Error(`未知任务: ${name}`);
    const t0 = performance.now();
    let result: JobResult;
    try {
      const summary = await job.run();
      result = { ok: true, ran_at: Date.now(), duration_ms: performance.now() - t0, summary };
    } catch (e) {
      result = { ok: false, ran_at: Date.now(), duration_ms: performance.now() - t0, summary: {}, error: (e as Error).message };
    }
    this.last.set(name, result);
    const hist = this.history.get(name) ?? [];
    hist.push(result);
    if (hist.length > HISTORY_CAP) hist.shift();
    this.history.set(name, hist);
    this.bus.emit('job_done', { name, ok: result.ok, summary: result.summary });
    return result;
  }

  status(): JobView[] {
    return [...this.jobs.values()].map((j) => ({
      name: j.name,
      description: j.description,
      schedule: j.schedule,
      enabled: true,
      last: this.last.get(j.name),
      history: this.history.get(j.name) ?? [],
    }));
  }
}

function due(schedule: string, lastRun: number): boolean {
  const now = Date.now();
  if (schedule.startsWith('weekly@')) {
    return now - lastRun >= 7 * 24 * 3600 * 1000;
  }
  if (schedule.startsWith('daily@')) {
    return now - lastRun >= 24 * 3600 * 1000;
  }
  return false;
}

// ---- 复盘 agent:每周剧情质量报告 ----

export interface ReviewReport {
  generated_at: number;
  dispatches: number;
  intent_distribution: Record<string, number>;
  clarify_rate: number;
  fallback_rate: number;
  route_latency: { p50: number; p95: number };
  ctx_latency: { p50: number; p95: number };
  memory_write: { total: number; ok: number; success_rate: number; dlq_open: number };
  whitelist_size: number;
  verdict: string;
}

export function createReviewJob(deps: {
  metrics: Metrics;
  audit: AuditLog;
  whitelist: NeverForgetWhitelist;
  writeScheduler: { openDlqCount(): number };
  dataDir: string;
}): Job {
  return {
    name: 'review',
    description: '每周剧情质量报告(复盘 agent)',
    schedule: 'weekly@mon-03:00',
    async run() {
      const snap = deps.metrics.snapshot();
      const intentDist: Record<string, number> = {};
      let dispatches = 0;
      let clarifies = 0;
      let fallbacks = 0;
      for (const [key, n] of Object.entries(snap.counters)) {
        if (key.startsWith('route_done{')) {
          dispatches += n;
          const intent = /intent=(\w+)/.exec(key)?.[1] ?? 'unknown';
          intentDist[intent] = (intentDist[intent] ?? 0) + n;
        }
      }
      for (const rec of deps.audit.query({ type: 'dispatch' })) {
        if (rec.route?.need_clarify) clarifies++;
        if (rec.route?.fallback_used) fallbacks++;
      }
      let writeTotal = 0;
      let writeOk = 0;
      for (const [key, n] of Object.entries(snap.counters)) {
        const m = /^memory_write\{.*ok=(\w+).*\}$/.exec(key);
        if (m) {
          writeTotal += n;
          if (m[1] === 'true') writeOk += n;
        }
      }
      const route = deps.metrics.summary('route_conf');
      const report: ReviewReport = {
        generated_at: Date.now(),
        dispatches,
        intent_distribution: intentDist,
        clarify_rate: dispatches ? clarifies / dispatches : 0,
        fallback_rate: dispatches ? fallbacks / dispatches : 0,
        route_latency: { p50: route.p50, p95: route.p95 },
        ctx_latency: { p50: deps.metrics.summary('ctx_build_ms').p50, p95: deps.metrics.summary('ctx_build_ms').p95 },
        memory_write: {
          total: writeTotal,
          ok: writeOk,
          success_rate: writeTotal ? writeOk / writeTotal : 1,
          dlq_open: deps.writeScheduler.openDlqCount(),
        },
        whitelist_size: deps.whitelist.list().length,
        verdict:
          (writeTotal ? writeOk / writeTotal : 1) >= 0.999 && deps.writeScheduler.openDlqCount() === 0
            ? 'healthy'
            : 'attention',
      };
      await writeJson(join(deps.dataDir, 'reports', `review-${new Date().toISOString().slice(0, 10)}.json`), report);
      return report as unknown as Record<string, unknown>;
    },
  };
}

// ---- 遗忘剪枝 agent:低显著性记忆 EMA 衰减 ----

export interface PruneSummary {
  scanned: number;
  pruned: number;
  decayed: number;
  protected_whitelist: number;
}

export function createPruneJob(deps: {
  stores: StoreRegistry;
  salience: SalienceEngine;
  whitelist: NeverForgetWhitelist;
}): Job {
  const TARGET_STORES = ['episodic', 'affective', 'working'] as const;
  return {
    name: 'prune',
    description: '遗忘剪枝:低显著性记忆按 EMA 置信度衰减(floor 删除,白名单豁免)',
    schedule: 'daily@04:00',
    async run() {
      const now = Date.now();
      const summary: PruneSummary = { scanned: 0, pruned: 0, decayed: 0, protected_whitelist: 0 };
      for (const storeId of TARGET_STORES) {
        const store = deps.stores.get(storeId);
        for (const mem of store.all()) {
          summary.scanned++;
          if (deps.whitelist.has(mem.id)) {
            summary.protected_whitelist++;
            continue;
          }
          // 闲置天数按整天计,避免刚写入的记忆因毫秒级闲置被记为"衰减"
          const idleDays = Math.floor(Math.max(0, (now - Math.max(mem.ts, mem.last_access)) / 86_400_000));
          const effective = deps.salience.decayed(mem.salience, idleDays);
          if (effective < deps.salience.config.prune.floor) {
            store.delete(mem.id);
            summary.pruned++;
          } else if (effective < mem.salience) {
            store.update(mem.id, { salience: effective });
            summary.decayed++;
          }
        }
      }
      return summary as unknown as Record<string, unknown>;
    },
  };
}

// ---- 巩固触发 agent:FR-G06 调度壳 ----

export function createConsolidateJob(deps: {
  consolidation: ConsolidationService;
}): Job {
  return {
    name: 'consolidate',
    description: '每周巩固:情景库高频词 → 老颞语义层 diff 报告(draft,人工确认后生效)',
    schedule: 'weekly@sun-03:30',
    async run() {
      const report: ConsolidationReport = deps.consolidation.runDraft();
      return {
        report_id: report.id,
        status: report.status,
        candidates: report.candidates.length,
        existing: report.existing.length,
        note: 'diff 报告已生成,等待人工一键确认(POST /admin/consolidation/confirm)',
      };
    },
  };
}
