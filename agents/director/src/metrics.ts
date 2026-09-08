// 埋点(§8):route_done(intent, minister, conf) / ctx_built(tokens) /
// memory_write(store, ok) / consolidate_batch(count)。全部决策与指标可通过
// GET /admin/metrics 观测。

import { percentile } from './util.ts';

type Labels = Record<string, string | number | boolean>;

function labelKey(name: string, labels?: Labels): string {
  if (!labels || Object.keys(labels).length === 0) return name;
  const pairs = Object.entries(labels).map(([k, v]) => `${k}=${String(v)}`);
  return `${name}{${pairs.sort().join(',')}}`;
}

export interface Summary {
  count: number;
  sum: number;
  p50: number;
  p95: number;
  max: number;
}

const SAMPLE_CAP = 1024;

export class Metrics {
  counters = new Map<string, number>();
  private samples = new Map<string, number[]>();

  inc(name: string, labels?: Labels, by = 1): void {
    const key = labelKey(name, labels);
    this.counters.set(key, (this.counters.get(key) ?? 0) + by);
  }

  observe(name: string, value: number, labels?: Labels): void {
    const key = labelKey(name, labels);
    let arr = this.samples.get(key);
    if (!arr) {
      arr = [];
      this.samples.set(key, arr);
    }
    arr.push(value);
    if (arr.length > SAMPLE_CAP) arr.shift();
  }

  // route_done(intent, minister, conf):计数 + 置信度观测
  routeDone(intent: string, minister: string, conf: number): void {
    this.inc('route_done', { intent, minister });
    this.observe('route_conf', conf, { intent });
  }

  ctxBuilt(tokens: number, budget: number): void {
    this.inc('ctx_built', { budget });
    this.observe('ctx_tokens', tokens);
  }

  memoryWrite(store: string, ok: boolean): void {
    this.inc('memory_write', { store, ok });
  }

  consolidateBatch(count: number): void {
    this.inc('consolidate_batch', { count });
  }

  summary(name: string, labels?: Labels): Summary {
    const arr = [...(this.samples.get(labelKey(name, labels)) ?? [])].sort((a, b) => a - b);
    return {
      count: arr.length,
      sum: arr.reduce((a, b) => a + b, 0),
      p50: percentile(arr, 0.5),
      p95: percentile(arr, 0.95),
      max: arr.length ? arr[arr.length - 1]! : 0,
    };
  }

  snapshot(): {
    counters: Record<string, number>;
    summaries: Record<string, Summary>;
  } {
    return {
      counters: Object.fromEntries(this.counters),
      summaries: Object.fromEntries([...this.samples.keys()].map((k) => [k, this.summary(k)])),
    };
  }
}
