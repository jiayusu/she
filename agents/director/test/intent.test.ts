// FR-G01 验收:六类意图准确率 ≥90%;低置信度走"小P 反问澄清"。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { IntentClassifier, makeClarifyQuestion } from '../src/intent.ts';
import { DEFAULT_LEXICON } from '../src/config.ts';
import type { Intent } from '../src/types.ts';

const classifier = new IntentClassifier(DEFAULT_LEXICON);

const LABELED: Array<[Intent, string]> = [
  // 记忆 → 阿海
  ['memory', '我昨天教会小熊什么来着'],
  ['memory', '小熊还记得我们上次玩的游戏吗'],
  ['memory', '昨天我们讲到哪里了'],
  ['memory', '你记得我昨天说过什么吗'],
  ['memory', '上次你给我讲的故事再讲一遍'],
  ['memory', '我之前学会的那个词是什么来着'],
  ['memory', '我们昨天玩了什么来着'],
  ['memory', '小熊忘了昨天学会的词了吗'],
  // 朝会 → 小脑
  ['court', '今天我们要开朝会吗'],
  ['court', '大臣们都到齐了吗,可以上朝了吧'],
  ['court', '敲钟啦,上朝咯'],
  ['court', '传朕的旨意,宣小熊觐见'],
  ['court', '现在升朝,请各位大臣就位'],
  ['court', '金銮殿上集合啦'],
  ['court', '我们去上朝吧,小脑等着呢'],
  ['court', '早朝时间到了'],
  // 学词 → 老颞
  ['word', "'聪明'是什么意思呀"],
  ['word', "'熊'字怎么写"],
  ['word', '教我一个新的词好不好'],
  ['word', '生字卡上的这个词怎么读'],
  ['word', '这个词用小熊的话怎么说'],
  ['word', "'再见'用英语怎么说"],
  ['word', '什么是成语呀'],
  ['word', '我要学新词'],
  // 安抚 → 杏杏
  ['comfort', '我怕黑,不敢一个人睡'],
  ['comfort', '打雷了好吓人'],
  ['comfort', '我今天好难过'],
  ['comfort', '呜呜呜,我做噩梦了'],
  ['comfort', '妈妈不要走,我害怕'],
  ['comfort', '肚子好疼'],
  ['comfort', '我睡不着,黑漆漆的'],
  ['comfort', '小朋友都不跟我玩,好伤心'],
  // 万物 → 老颞
  ['object', '这是什么呀'],
  ['object', '冰箱为什么会响'],
  ['object', '这个盒子里是什么声音'],
  ['object', '天为什么是蓝的'],
  ['object', '洗衣机怎么自己在转'],
  ['object', '太阳为什么会下山'],
  ['object', '它是活的吗,会听我说话'],
  ['object', '门缝里怎么在冒白气'],
  // 闲聊 → 小P
  ['chitchat', '你好呀,小P'],
  ['chitchat', '哈哈,太好玩了'],
  ['chitchat', '给我讲个笑话吧'],
  ['chitchat', '今天真开心'],
  ['chitchat', '我好无聊啊'],
  ['chitchat', '小P你真棒'],
  ['chitchat', '陪我玩一会儿嘛'],
  ['chitchat', '嘿,我们一起玩个游戏'],
];

describe('FR-G01 意图分类器', () => {
  it('六类意图准确率 ≥ 90%(验收线)', () => {
    let correct = 0;
    const misses: string[] = [];
    for (const [expected, text] of LABELED) {
      const r = classifier.classify({ utterance: text });
      if (r.intent === expected && !r.need_clarify) correct++;
      else misses.push(`${text} → ${r.intent}(${r.confidence.toFixed(2)}) 期望 ${expected}`);
    }
    const accuracy = correct / LABELED.length;
    assert.ok(
      accuracy >= 0.9,
      `准确率 ${(accuracy * 100).toFixed(1)}% < 90%\n未命中:\n${misses.join('\n')}`,
    );
  });

  it('六类意图全部正确(盲测集基线 100%)', () => {
    const misses: string[] = [];
    for (const [expected, text] of LABELED) {
      const r = classifier.classify({ utterance: text });
      if (r.intent !== expected) misses.push(`${text} → ${r.intent}`);
    }
    assert.deepEqual(misses, []);
  });

  it('空/含糊输入 → 低置信度,需澄清', () => {
    for (const text of ['', '嗯嗯', '哦', '啊?', '呃呃呃呃', '嗯,后来呢']) {
      const r = classifier.classify({ utterance: text });
      assert.ok(r.need_clarify, `"${text}" 应判定低置信度`);
    }
  });

  it('两意图得分接近 → 低置信度触发澄清', () => {
    // 记忆 2.5(昨天…教)与 学词 2.5(教我…成语)打平
    const r = classifier.classify({ utterance: '昨天教我单词' });
    assert.ok(r.need_clarify, `置信度 ${r.confidence.toFixed(2)} 应低于阈值`);
    assert.deepEqual([...r.top2].sort(), ['memory', 'word']);
  });

  it('声学情绪分低落时抬升安抚意图', () => {
    const r = classifier.classify({ utterance: '我不想说话', emotion: { valence: -0.9, arousal: 0.7 } });
    assert.equal(r.intent, 'comfort');
    assert.ok(!r.need_clarify);
  });

  it('ASR 识别置信度低会拉低总置信度', () => {
    const base = classifier.classify({ utterance: '昨天教我单词' });
    const noisy = classifier.classify({ utterance: '昨天教我单词', asr: { conf: 0.2 } });
    assert.ok(noisy.confidence < base.confidence);
    assert.ok(noisy.need_clarify);
  });

  it('澄清话术覆盖前两名意图', () => {
    const q = makeClarifyQuestion(['memory', 'word']);
    assert.ok(q.includes('小P'));
    assert.ok(q.includes('之前发生过的事'));
    assert.ok(q.includes('新词'));
  });
});
