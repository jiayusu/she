// FR-G03 上下文注入包:切换大臣时按规范拼装
// { 剧本状态, 最近 10 轮, 今日已学词, 孩子情绪分 },token 预算分级(闲聊 500 / 任务 1500 / 澄清 300)。
// 预算不足时按优先级裁剪:剧本状态 > 情绪 > 今日已学词 > 最近对话轮(从最旧开始丢,保最新)。
// 注入规范详见 docs/context-injection.md。

import type { BudgetsCfg } from './config.ts';
import type { CtxBundle, Intent, Turn } from './types.ts';
import { estimateTokens, percentile } from './util.ts';
import { RECENT_TURNS_FOR_CTX, type SessionState } from './session.ts';

export interface BuildOptions {
  needClarify?: boolean;
  safetyNotes?: string[];
  minister?: import('./types.ts').MinisterId;
}

export interface BuildResult {
  bundle: CtxBundle;
  elapsed_ms: number;
  trimmed_turns: number;
}

function fitTurnToBudget(turn: Turn, budgetTokens: number): Turn {
  let text = turn.text;
  let fitted: Turn = { ...turn, text };
  // 二分逼近可用预算;至少保留 1 个字符,结尾加截断标记
  while (estimateTokens(JSON.stringify(fitted)) + 1 > budgetTokens && text.length > 1) {
    text = text.slice(0, Math.max(1, Math.floor(text.length / 2)));
    fitted = { ...turn, text: text + '…' };
  }
  return fitted;
}

const SAMPLE_CAP = 512;

export class ContextBuilder {
  private latencies: number[] = [];

  constructor(private budgets: BudgetsCfg) {}

  resolveBudget(intent: Intent, needClarify?: boolean): number {
    if (needClarify) return this.budgets.by_intent.clarify ?? 300;
    return this.budgets.by_intent[intent] ?? this.budgets.default_budget;
  }

  build(session: SessionState, intent: Intent, opts: BuildOptions = {}): BuildResult {
    const t0 = performance.now();
    const budget = this.resolveBudget(intent, opts.needClarify);
    const notes: string[] = [...(opts.safetyNotes ?? [])];

    // 固定头部:剧本状态(优先级最高)+ 情绪
    const scriptState = this.truncateScriptState(session.script_state, budget);
    const headerParts: Array<{ key: string; json: string }> = [
      { key: 'script_state', json: JSON.stringify(scriptState) },
      { key: 'emotion', json: JSON.stringify(session.emotion) },
    ];
    let used = headerParts.reduce((acc, p) => acc + estimateTokens(p.json) + 2, 0);

    // 今日已学词(封顶 max_today_words)
    const words = session.today_words.slice(-this.budgets.max_today_words);
    const wordsJson = JSON.stringify(words);
    const wordsTokens = estimateTokens(wordsJson) + 2;
    const includeWords = used + wordsTokens <= budget;
    if (includeWords) used += wordsTokens;
    else notes.push('今日已学词因 token 预算被裁剪');

    // 最近对话轮:从最新往回装,直到预算用尽;输出保持时间升序。
    // 最新一轮即使超预算也强制注入(截断文本),避免出现空对话的注入包。
    const turnsBudget = budget - used;
    const picked: Turn[] = [];
    let turnsUsed = 0;
    const recent = session.turns.slice(-this.budgets.max_recent_turns);
    let trimmed = 0;
    for (let i = recent.length - 1; i >= 0; i--) {
      const turn = recent[i]!;
      const t = estimateTokens(JSON.stringify(turn)) + 1;
      if (turnsUsed + t > turnsBudget) {
        trimmed = i + 1;
        break;
      }
      picked.unshift(turn);
      turnsUsed += t;
    }
    if (trimmed > 0) notes.push(`最近 ${trimmed} 轮对话因 token 预算被裁剪`);
    if (picked.length === 0 && recent.length > 0 && turnsBudget > 0) {
      const newest = recent[recent.length - 1]!;
      const fitted = fitTurnToBudget(newest, turnsBudget);
      picked.unshift(fitted);
      turnsUsed = estimateTokens(JSON.stringify(fitted)) + 1;
      notes.push('最新一轮对话超预算,已截断注入');
    }

    const bundle: CtxBundle = {
      intent,
      minister: opts.minister ?? session.minister_on_duty,
      budget,
      tokens_used: used + turnsUsed,
      script_state: scriptState,
      recent_turns: picked,
      today_words: includeWords ? words : [],
      emotion: session.emotion,
      notes,
    };

    const elapsed = performance.now() - t0;
    this.latencies.push(elapsed);
    if (this.latencies.length > SAMPLE_CAP) this.latencies.shift();
    return { bundle, elapsed_ms: elapsed, trimmed_turns: trimmed };
  }

  private truncateScriptState(state: Record<string, unknown>, budget: number): Record<string, unknown> {
    if (estimateTokens(JSON.stringify(state)) + 2 <= budget) return state;
    // 剧本状态超预算(极罕见):保留字段键、值截断,保证注入包结构稳定
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(state)) {
      const s = typeof v === 'string' ? v : JSON.stringify(v) ?? '';
      out[k] = typeof v === 'string' ? s.slice(0, 64) : JSON.parse(s.slice(0, 64) || 'null');
    }
    return out;
  }

  latencyStats(): { p50: number; p95: number; max: number; samples: number } {
    const sorted = [...this.latencies].sort((a, b) => a - b);
    return {
      p50: percentile(sorted, 0.5),
      p95: percentile(sorted, 0.95),
      max: sorted.length ? sorted[sorted.length - 1]! : 0,
      samples: sorted.length,
    };
  }
}
