// 配置加载:config/*.json(运营可改);文件缺失或损坏时回退到内置默认值,保证服务可启动。

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DEFAULT_MINISTER_MAP, MinisterMapTable, validateMinisterMap } from './mapping.ts';
import type { LexiconCfg } from './intent.ts';
import type { SalienceCfg } from './salience.ts';

export function loadJson<T>(file: string, fallback: T, validate?: (v: unknown) => T): T {
  try {
    const parsed: unknown = JSON.parse(readFileSync(file, 'utf8'));
    return validate ? validate(parsed) : (parsed as T);
  } catch {
    return fallback;
  }
}

export interface BudgetsCfg {
  default_budget: number;
  by_intent: Record<string, number>;
  max_recent_turns: number;
  max_today_words: number;
}

export const DEFAULT_BUDGETS: BudgetsCfg = {
  default_budget: 1500,
  by_intent: { chitchat: 500, clarify: 300 },
  max_recent_turns: 10,
  max_today_words: 30,
};

export const DEFAULT_LEXICON: LexiconCfg = {
  // 与 config/lexicon.json 保持一致;configDir 不可用或文件损坏时的兜底
  intents: {
    memory: [
      { pattern: '什么来着', weight: 3.0 },
      { pattern: '记不记得|还记得|还记得吗|忘了|忘了吗|忘记了', weight: 2.5 },
      { pattern: '(昨天|上次|那天|之前|前几天|刚才).*(教会?|学|说|讲|玩|发生|去|吃|看)', weight: 2.5 },
      { pattern: '教会?.*(什么|什么来着)', weight: 2.5 },
      { pattern: '(以前|之前).*(告诉|说过|讲过)', weight: 2.0 },
      { pattern: '再讲一遍|再(说|讲)一次|上次的故事|昨天(发生|玩|学)', weight: 2.0 },
      { pattern: '小熊(记得|学过|会什么)', weight: 2.0 },
      { pattern: '回忆|想起来了吗|你记得吗', weight: 1.5 },
    ],
    court: [
      { pattern: '朝会|上朝|开朝|升朝|早朝', weight: 3.0 },
      { pattern: '(大臣们|各位大臣).*(集合|到齐|开始|点名)', weight: 2.5 },
      { pattern: '敲钟|升帐|金銮殿|上殿', weight: 2.0 },
      { pattern: '今天(要|该)?(开|上)朝', weight: 2.5 },
      { pattern: '传(朕的)?(旨|令)|宣.{0,4}觐见', weight: 2.0 },
    ],
    word: [
      { pattern: '是什么意思|啥意思|什么含义', weight: 3.0 },
      { pattern: '怎么读|怎么念|怎么写|怎么拼', weight: 3.0 },
      { pattern: '(教|学)(我|会我)?(一)?(个|下)?(新)?(的)?(词|字|单词|成语)', weight: 2.5 },
      { pattern: '这个字|那个词|生字|新词|成语', weight: 2.0 },
      { pattern: '用.{1,8}(怎么说|怎么读|怎么念|怎么写)', weight: 2.0 },
      { pattern: '什么意思呀|啥呀这是', weight: 2.0 },
    ],
    comfort: [
      { pattern: '害怕|好怕|我怕|不敢|吓(死|到)', weight: 3.0 },
      { pattern: '难过|伤心|委屈|想哭|呜呜|呜呜呜', weight: 3.0 },
      { pattern: '不想(一个人|睡|上学|去)|睡不着|做噩梦|噩梦', weight: 2.5 },
      { pattern: '打雷|闪电|黑漆漆|好黑|停电', weight: 2.0 },
      { pattern: '抱抱|陪我|别(走|离开)|留下来', weight: 2.0 },
      { pattern: '疼|痛|不舒服|生病', weight: 2.0 },
    ],
    object: [
      { pattern: '^这是什么$|^这是什么呀|这是什么(东西|声音)|是什么(声音|动静|响声)', weight: 3.0 },
      { pattern: '(冰箱|电视|洗衣机|空调|微波炉|风扇|桌子|椅子|门|窗|台灯|水壶|闹钟).{0,12}(为什么|怎么会?|怎么在|怎么自己)', weight: 3.0 },
      { pattern: '为什么(会)?(响|动|亮|转|叫|冒|滴|闪|震)', weight: 2.5 },
      { pattern: '(那个|这个)(东西|盒子|机器)(在干嘛|怎么了|会说话)', weight: 2.5 },
      { pattern: '(天|太阳|月亮|星星|云|雨|风|彩虹)(为什么|怎么会)', weight: 2.0 },
      { pattern: '它是活的|它会(听|说话|动)', weight: 2.0 },
    ],
    chitchat: [
      { pattern: '^(你好|哈喽|hello|嗨|hi|嗨哟)', weight: 3.0 },
      { pattern: '哈哈|嘿嘿|嘻嘻|好开心|真好玩|太好玩了', weight: 2.0 },
      { pattern: '讲个笑话|说个好玩的|陪我玩|一起玩', weight: 2.5 },
      { pattern: '好无聊|无聊死了', weight: 2.0 },
      { pattern: '我喜欢你|你真棒|你真可爱', weight: 2.0 },
      { pattern: '今天(真|好)(开心|高兴|快乐)', weight: 2.0 },
    ],
  },
  emotion_boost: {
    comfort_valence_below: -0.4,
    comfort_boost: 2.2,
    comfort_negative_labels: ['sad', 'afraid', 'angry', 'sobbing', 'crying'],
    chitchat_valence_above: 0.6,
    chitchat_boost: 0.6,
  },
  injection_patterns: [
    '忽略(之前|以上|上面)(的)?(所有)?(指令|规则|设定)',
    '(system\\s*prompt|system instructions)',
    '你现在是(个|一个)?(不|没有)(受|限)(任何)?(限制|约束)',
    '关闭(内容)?(安全|过滤|审查)',
    '(ignore|disregard)\\s+(all\\s+)?(previous|prior|above)',
    '(解锁|解除)(安全|限制|审查)模式',
    'jailbreak|dan模式|开发者模式已开启',
  ],
};

export const DEFAULT_SALIENCE: SalienceCfg = {
  whitelist_threshold: 0.8,
  base_score: 0.3,
  rules: { milestone: 0.9, first_behavior: 0.7, emotion_peak: 0.8 },
  emotion_peak_abs_valence: 0.85,
  prune: { decay_lambda_per_day: 0.05, floor: 0.05 },
};

export interface LoadedConfigs {
  mapTable: MinisterMapTable;
  mapFile: string | null;
  lexicon: LexiconCfg;
  lexiconFile: string | null;
  budgets: BudgetsCfg;
  budgetsFile: string | null;
  salience: SalienceCfg;
  salienceFile: string | null;
}

export function loadConfigs(configDir: string | null): LoadedConfigs {
  const f = (name: string) => (configDir ? join(configDir, name) : null);

  const mapFile = f('minister-map.json');
  const mapTable = new MinisterMapTable(DEFAULT_MINISTER_MAP);
  if (mapFile) {
    try {
      mapTable.loadFile(mapFile);
    } catch {
      // 配置损坏时保持默认映射,由 /admin/map/reload 修复
    }
  }

  const lexiconFile = f('lexicon.json');
  const lexicon = loadJson<LexiconCfg>(lexiconFile ?? '', DEFAULT_LEXICON);

  const budgetsFile = f('budgets.json');
  const budgets = loadJson<BudgetsCfg>(budgetsFile ?? '', DEFAULT_BUDGETS);

  const salienceFile = f('salience.json');
  const salience = loadJson<SalienceCfg>(salienceFile ?? '', DEFAULT_SALIENCE);

  return { mapTable, mapFile, lexicon, lexiconFile, budgets, budgetsFile, salience, salienceFile };
}

export { validateMinisterMap };
