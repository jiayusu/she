// FR-P04 确认话术状态机测试：≤2 轮、肯定/否定/超时各路径、纠正计数、优雅退出。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ConfirmFlow } from '../web/js/pipeline.js';
import { parseAnswer } from '../web/js/config.js';

const C = [
  { label: '杯子', bbox: [0, 0, 10, 10] },
  { label: '球', bbox: [20, 0, 10, 10] },
  { label: '书', bbox: [40, 0, 10, 10] },
];

function scripted(answers) {
  const log = { asks: [] };
  const queue = [...answers];
  const speech = {
    nameOf: (b) => b.label,
    askYesNo: async (name, round) => log.asks.push(['yesno', name, round]),
    askPair: async (a, b, round) => log.asks.push(['pair', a, b, round]),
    getAnswer: async () => queue.shift() ?? { kind: 'timeout' },
  };
  return { speech, log };
}

test('词表：任意中文肯定/否定表达可识别；否定优先于肯定（"不是"≠"是"）', () => {
  const cases = [
    ['是的', 'affirm'], ['对', 'affirm'], ['对呀', 'affirm'], ['嗯嗯', 'affirm'],
    ['好', 'affirm'], ['没错', 'affirm'], ['我想知道', 'affirm'], ['就是它', 'affirm'],
    ['ok', 'affirm'], ['Yes', 'affirm'],
    ['不是', 'deny'], ['不对', 'deny'], ['不', 'deny'], ['错了', 'deny'],
    ['没有', 'deny'], ['换一个', 'deny'], ['不想要', 'deny'], ['no', 'deny'],
    ['不知道', 'deny'],
    ['西瓜', 'none'], ['黄色', 'none'], ['哎呀', 'none'],
  ];
  for (const [text, kind] of cases) {
    assert.equal(parseAnswer(text).kind, kind, `"${text}" 应为 ${kind}`);
  }
  // 说出候选名 = 指认该候选
  assert.equal(parseAnswer('这是杯子', { names: ['杯子'] }).kind, 'choice');
  assert.equal(parseAnswer('不是杯子', { names: ['杯子'] }).kind, 'deny'); // 否定优先
  assert.equal(parseAnswer('那个球', { names: ['杯子', '球'] }).name, '球');
});

test('轻确认：第 1 轮肯定 → 选中候选 1，1 轮 0 纠正', async () => {
  const { speech, log } = scripted([{ kind: 'affirm' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'light', speech });
  const r = await flow.run();
  assert.equal(r.type, 'selected');
  assert.equal(r.box.label, '杯子');
  assert.equal(r.meta.rounds, 1);
  assert.equal(r.meta.corrections, 0);
  assert.equal(log.asks[0][1], '杯子');
});

test('轻确认：第 1 轮 2 秒无否定 → 视为确认（快进路径）', async () => {
  const { speech } = scripted([]);
  const flow = new ConfirmFlow({ candidates: C, style: 'light', speech });
  const r = await flow.run();
  assert.equal(r.type, 'selected');
  assert.equal(r.box.label, '杯子');
  assert.equal(r.meta.autoPassed, true);
});

test('轻确认：否定 → 第二候选再问（≤2 轮），肯定 → 选中候选 2', async () => {
  const { speech, log } = scripted([{ kind: 'deny' }, { kind: 'affirm' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'light', speech });
  const r = await flow.run();
  assert.equal(r.type, 'selected');
  assert.equal(r.box.label, '球');
  assert.equal(r.meta.rounds, 2);
  assert.equal(r.meta.corrections, 1);
  assert.deepEqual(log.asks.map((a) => [a[1], a[2]]), [['杯子', 1], ['球', 2]]);
});

test('连续否定 2 次 → 优雅退出，轮次不超过 2', async () => {
  const { speech } = scripted([{ kind: 'deny' }, { kind: 'deny' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'light', speech });
  const r = await flow.run();
  assert.equal(r.type, 'exit');
  assert.equal(r.meta.rounds, 2);
  assert.equal(r.meta.corrections, 2);
});

test('轻确认第 2 轮超时 → 退出（第 1 轮才允许静默通过）', async () => {
  const { speech } = scripted([{ kind: 'deny' }, { kind: 'timeout' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'light', speech });
  const r = await flow.run();
  assert.equal(r.type, 'exit');
});

test('重确认（双候选）：回答"球" → 选中球', async () => {
  const { speech, log } = scripted([{ kind: 'choice', name: '球' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'heavy', speech });
  const r = await flow.run();
  assert.equal(r.type, 'selected');
  assert.equal(r.box.label, '球');
  assert.equal(log.asks[0][0], 'pair');
  assert.deepEqual(log.asks[0].slice(1, 3), ['杯子', '球']);
});

test('重确认双候选：含糊"是" → 重问一轮 → 再含糊 → 退出', async () => {
  const { speech } = scripted([{ kind: 'affirm' }, { kind: 'none' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'heavy', speech });
  const r = await flow.run();
  assert.equal(r.type, 'exit');
  assert.equal(r.meta.rounds, 2);
});

test('重确认双候选：否定 → 重问 → 仍否定 → 退出，纠正计数 2', async () => {
  const { speech } = scripted([{ kind: 'deny' }, { kind: 'deny' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'heavy', speech });
  const r = await flow.run();
  assert.equal(r.type, 'exit');
  assert.equal(r.meta.corrections, 2);
});

test('重确认单候选（中心兜底场景）：肯定 → 选中；否定×2 → 退出', async () => {
  const only = [C[0]];
  const a = scripted([{ kind: 'affirm' }]);
  const r1 = await new ConfirmFlow({ candidates: only, style: 'heavy', speech: a.speech }).run();
  assert.equal(r1.type, 'selected');

  const b = scripted([{ kind: 'deny' }, { kind: 'deny' }]);
  const r2 = await new ConfirmFlow({ candidates: only, style: 'heavy', speech: b.speech }).run();
  assert.equal(r2.type, 'exit');
});

test('重确认超时 → 重问一轮 → 退出（双候选 pair 流，不空转）', async () => {
  const { speech, log } = scripted([{ kind: 'timeout' }, { kind: 'timeout' }]);
  const flow = new ConfirmFlow({ candidates: C, style: 'heavy', speech });
  const r = await flow.run();
  assert.equal(r.type, 'exit');
  assert.deepEqual(log.asks.map((a) => [a[1], a[2], a[3]]), [['杯子', '球', 1], ['杯子', '球', 2]]);
});

test('空候选 → 直接退出', async () => {
  const { speech } = scripted([]);
  const r = await new ConfirmFlow({ candidates: [], style: 'light', speech }).run();
  assert.equal(r.type, 'exit');
});
