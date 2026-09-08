// FR-G05 显著性打标(杏杏规则):里程碑事件 / 孩子首次行为 / 情绪高峰
// 自动打 salience 分;≥阈值进"永不遗忘"白名单(白名单只增不删,人工可增不可减)。

import type { Emotion, MemoryWriteEntry } from './types.ts';
import { clamp } from './util.ts';

export interface SalienceCfg {
  whitelist_threshold: number;
  base_score: number;
  rules: { milestone: number; first_behavior: number; emotion_peak: number };
  emotion_peak_abs_valence: number;
  prune: { decay_lambda_per_day: number; floor: number };
}

export const DEFAULT_SALIENCE_CFG: SalienceCfg = {
  whitelist_threshold: 0.8,
  base_score: 0.3,
  rules: { milestone: 0.9, first_behavior: 0.7, emotion_peak: 0.8 },
  emotion_peak_abs_valence: 0.85,
  prune: { decay_lambda_per_day: 0.05, floor: 0.05 },
};

export interface SalienceVerdict {
  score: number;
  reasons: string[];
  whitelisted: boolean;
}

export interface StoredMemory {
  id: string;
  store: string;
  minister?: string;
  kind: string;
  payload: Record<string, unknown>;
  salience: number;
  reasons?: string[];
  ts: number;
  last_access: number;
}

export class SalienceEngine {
  private seenBehaviors = new Set<string>();

  constructor(
    private cfg: SalienceCfg = DEFAULT_SALIENCE_CFG,
    seedBehaviors: string[] = [],
  ) {
    for (const b of seedBehaviors) this.seenBehaviors.add(b);
  }

  /** 首次行为集合持久化:由 app 启动时从情景库回放注入。 */
  seedBehavior(behavior: string): void {
    if (behavior) this.seenBehaviors.add(behavior);
  }

  get seenBehaviorCount(): number {
    return this.seenBehaviors.size;
  }

  evaluate(entry: MemoryWriteEntry, ctx: { emotion?: Emotion } = {}): SalienceVerdict {
    const reasons: string[] = [];
    let score = this.cfg.base_score;
    if (typeof entry.payload?.salience === 'number') {
      score = clamp(entry.payload.salience, 0, 1);
    }

    const tags = Array.isArray(entry.payload?.tags) ? (entry.payload.tags as string[]) : [];
    if (entry.kind === 'milestone' || tags.includes('milestone')) {
      score += this.cfg.rules.milestone;
      reasons.push('里程碑事件');
    }

    const behavior = typeof entry.payload?.behavior === 'string' ? entry.payload.behavior : null;
    const isFirstBehavior =
      entry.kind === 'first_behavior' || (behavior !== null && !this.seenBehaviors.has(behavior));
    if (isFirstBehavior && behavior !== null) {
      score += this.cfg.rules.first_behavior;
      reasons.push('孩子首次行为');
      // 首次行为登记后不再重复加分
      this.seenBehaviors.add(behavior);
    }

    const emo = ctx.emotion;
    const peakByScore =
      emo !== undefined && Math.abs(emo.valence) >= this.cfg.emotion_peak_abs_valence;
    const peakByLabel = emo?.label === 'sobbing' || emo?.label === 'ecstatic';
    if (entry.kind === 'affect_event' || peakByScore || peakByLabel) {
      score += this.cfg.rules.emotion_peak;
      reasons.push('情绪高峰');
    }

    score = clamp(score, 0, 1);
    return { score, reasons, whitelisted: score >= this.cfg.whitelist_threshold };
  }

  /** FR-G07 遗忘剪枝的衰减函数:EMA 式置信度衰减,闲置越久有效显著性越低。 */
  decayed(salience: number, idleDays: number): number {
    return salience * Math.exp(-this.cfg.prune.decay_lambda_per_day * idleDays);
  }

  get config(): SalienceCfg {
    return this.cfg;
  }
}
