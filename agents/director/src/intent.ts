// FR-G01 意图分类器:输入 ASR 文本 + 声学情绪分 → 六类意图 + 置信度。
// 词法评分 + 情绪加权 + softmax 归一化;低置信度交给"小P 反问澄清"。
// 词典/权重来自 config/lexicon.json,可运营调整,不硬编码。

import { INTENTS, type AsrMeta, type Emotion, type Intent, type IntentResult } from './types.ts';
import { clamp } from './util.ts';

export interface LexiconPattern {
  pattern: string;
  weight: number;
}

export interface EmotionBoostCfg {
  comfort_valence_below: number;
  comfort_boost: number;
  comfort_negative_labels: string[];
  chitchat_valence_above: number;
  chitchat_boost: number;
}

export interface LexiconCfg {
  intents: Record<Intent, LexiconPattern[]>;
  emotion_boost: EmotionBoostCfg;
  injection_patterns?: string[];
}

export interface ClassifyInput {
  utterance: string;
  emotion?: Emotion;
  asr?: AsrMeta;
  threshold?: number;
}

interface CompiledPattern {
  re: RegExp;
  weight: number;
  intent: Intent;
}

const SOFTMAX_SHARPNESS = 1.6;

export class IntentClassifier {
  private compiled: CompiledPattern[] = [];
  private cfg: LexiconCfg;

  constructor(cfg: LexiconCfg) {
    this.cfg = cfg;
    this.compile();
  }

  reload(cfg: LexiconCfg): void {
    this.cfg = cfg;
    this.compile();
  }

  private compile(): void {
    this.compiled = [];
    for (const intent of INTENTS) {
      const pats = this.cfg.intents[intent] ?? [];
      for (const p of pats) {
        try {
          this.compiled.push({ re: new RegExp(p.pattern, 'i'), weight: p.weight, intent });
        } catch {
          // 运营配置了非法正则时跳过该条,不让整个分类器崩溃
        }
      }
    }
  }

  classify(input: ClassifyInput): IntentResult {
    const text = (input.utterance ?? '').trim();
    const scores = Object.fromEntries(INTENTS.map((i) => [i, 0])) as Record<Intent, number>;

    if (text.length > 0) {
      for (const p of this.compiled) {
        if (p.re.test(text)) scores[p.intent] += p.weight;
      }
      this.applyEmotionBoost(scores, input.emotion);
    }

    const probs = softmax(scores, SOFTMAX_SHARPNESS);
    const ranked = [...INTENTS].sort((a, b) => probs[b]! - probs[a]!);
    const top = ranked[0]!;
    const top2 = [ranked[0]!, ranked[1]!] as [Intent, Intent];

    let confidence = probs[top]!;
    // ASR 识别置信度低时整体下调,推动进入澄清分支
    const asrConf = input.asr?.conf;
    if (asrConf !== undefined) confidence *= 0.6 + 0.4 * asrConf;
    confidence = clamp(confidence, 0, 1);

    const threshold = input.threshold ?? 0.55;
    return {
      intent: top,
      confidence,
      scores,
      need_clarify: confidence < threshold,
      top2,
    };
  }

  private applyEmotionBoost(scores: Record<Intent, number>, emotion?: Emotion): void {
    if (!emotion) return;
    const eb = this.cfg.emotion_boost;
    if (emotion.valence <= eb.comfort_valence_below) {
      scores.comfort += eb.comfort_boost * Math.abs(emotion.valence);
    }
    if (emotion.label && eb.comfort_negative_labels.includes(emotion.label)) {
      scores.comfort += 1.5;
    }
    if (emotion.valence >= eb.chitchat_valence_above && scores.chitchat > 0) {
      scores.chitchat += eb.chitchat_boost;
    }
  }
}

function softmax(scores: Record<Intent, number>, sharpness: number): Record<Intent, number> {
  const max = Math.max(...INTENTS.map((i) => scores[i]!));
  const exps = INTENTS.map((i) => [i, Math.exp((scores[i]! - max) * sharpness)] as const);
  const sum = exps.reduce((acc, [, v]) => acc + v, 0);
  return Object.fromEntries(exps.map(([i, v]) => [i, v / sum])) as Record<Intent, number>;
}

// 小P 反问澄清话术:按置信度前两名意图生成"是…还是…"句式
const CLARIFY_TEMPLATES: Record<Intent, string> = {
  memory: '想问问之前发生过的事',
  word: '想学一个新词',
  object: '想问问身边某个东西',
  comfort: '心里有点不舒服',
  court: '想开朝会',
  chitchat: '想随便聊聊天',
};

export function makeClarifyQuestion(top2: [Intent, Intent]): string {
  const a = CLARIFY_TEMPLATES[top2[0]];
  const b = CLARIFY_TEMPLATES[top2[1]];
  if (top2[0] === top2[1]) return `小P没太听明白,你是${a}吗?`;
  return `小P没太听明白,你是${a},还是${b}呀?`;
}
