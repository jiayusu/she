import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadStorySeed, validateStorySeed } from '../src/story-seed.ts';

function fixture(): Record<string, any> {
  return {
    seed_id: 'synthetic_story', version: 1, language_levels: [0, 1, 2],
    start_node_id: 'request', completion_node_id: 'done',
    allowed_world_events: ['virtual_item_granted', 'quest_completed'],
    allowed_items: ['milk_token'],
    nodes: [{
      node_id: 'request', terminal: false, required_objects: ['fridge'],
      world_role: 'Drink keeper', motivation: 'Prepare a pretend picnic.',
      learning_goal: 'Request milk.', target_expression: 'I want milk.',
      criterion: {
        criterion_id: 'request_milk.v1', act: 'request_item', slots: { item: 'milk' },
        accepted_forms: [
          { text: 'milk', requires_prompt_id: 'request_s2' },
          { text: 'I want milk', requires_prompt_id: null },
        ],
      },
      prompts: Array.from({ length: 7 }, (_, scaffold_level) => ({
        prompt_id: `request_s${scaffold_level}`, scaffold_level,
      })),
      success_feedback_id: 'milk_ready', failure_feedback_id: 'milk_help',
      success_event: { kind: 'virtual_item_granted', item_id: 'milk_token' },
      next_node_id: 'done',
    }, {
      node_id: 'done', terminal: true, required_objects: [],
      world_role: 'Picnic guide', motivation: 'Celebrate together.',
      learning_goal: 'Hear a story ending.', target_expression: 'Our picnic is ready.',
      criterion: null,
      prompts: Array.from({ length: 7 }, (_, scaffold_level) => ({
        prompt_id: `done_s${scaffold_level}`, scaffold_level,
      })),
      success_feedback_id: 'picnic_ready', failure_feedback_id: 'picnic_pause',
      success_event: { kind: 'quest_completed', quest_id: 'synthetic_story' },
      next_node_id: null,
    }],
  };
}

test('accepts a complete finite story with contextual and independent speech forms', () => {
  assert.deepEqual(validateStorySeed(fixture()), fixture());
});

test('loads the milk picnic chain with its required objects and virtual rewards', () => {
  const seed = loadStorySeed(new URL('../content/story-seeds/milk_picnic.v1.json', import.meta.url));
  assert.equal(seed.seed_id, 'milk_picnic');
  assert.equal(seed.version, 1);
  assert.deepEqual(seed.nodes.map(node => node.node_id), ['collect_milk', 'find_red_cup', 'picnic_ready']);
  assert.deepEqual(seed.nodes.map(node => node.required_objects), [
    ['fridge'], ['table', 'red_cup', 'blue_cup'], [],
  ]);
  assert.deepEqual(seed.nodes[0].criterion?.slots, { item: 'milk' });
  assert.deepEqual(seed.nodes[1].criterion?.slots, { item: 'cup', color: 'red' });
  assert.equal(seed.nodes[0].next_node_id, 'find_red_cup');
  assert.equal(seed.nodes[1].next_node_id, 'picnic_ready');
  assert.deepEqual(seed.nodes[0].success_event, { kind: 'virtual_item_granted', item_id: 'milk_token' });
  assert.deepEqual(seed.nodes[1].success_event, { kind: 'virtual_item_granted', item_id: 'red_cup_token' });
  assert.equal(seed.nodes[2].terminal, true);
  assert.equal(seed.nodes[2].next_node_id, null);
});

const invalid: Array<[string, (seed: Record<string, any>) => void]> = [
  ['duplicate node', s => s.nodes.push(structuredClone(s.nodes[0]))],
  ['missing nodes', s => delete s.nodes],
  ['empty nodes', s => s.nodes = []],
  ['missing start', s => s.start_node_id = 'missing'],
  ['missing completion', s => s.completion_node_id = 'missing'],
  ['unreachable node', s => s.nodes.push({ ...structuredClone(s.nodes[0]), node_id: 'orphan',
    criterion: { ...s.nodes[0].criterion, criterion_id: 'orphan.v1', accepted_forms: [{ text: 'milk please', requires_prompt_id: null }] },
    prompts: s.nodes[0].prompts.map((p: any) => ({ ...p, prompt_id: `orphan_s${p.scaffold_level}` })),
    success_feedback_id: 'orphan_ok', failure_feedback_id: 'orphan_help' })],
  ['invalid successor', s => s.nodes[0].next_node_id = 'missing'],
  ['cycle', s => s.nodes[0].next_node_id = 'request'],
  ['terminal successor', s => s.nodes[1].next_node_id = 'request'],
  ['nonterminal without successor', s => s.nodes[0].next_node_id = null],
  ['completion is nonterminal', s => s.completion_node_id = 'request'],
  ['undeclared event', s => s.allowed_world_events = ['quest_completed']],
  ['unknown event kind', s => s.nodes[0].success_event.kind = 'open_real_fridge'],
  ['undeclared item', s => s.nodes[0].success_event.item_id = 'unknown_token'],
  ['wrong completion quest', s => s.nodes[1].success_event.quest_id = 'other_story'],
  ['empty prompt id', s => s.nodes[0].prompts[0].prompt_id = ' '],
  ['duplicate prompt id', s => s.nodes[1].prompts[0].prompt_id = 'request_s0'],
  ['missing scaffold coverage', s => s.nodes[0].prompts.pop()],
  ['duplicate scaffold level', s => s.nodes[0].prompts[0].scaffold_level = 1],
  ['foreign contextual prompt', s => s.nodes[0].criterion.accepted_forms[0].requires_prompt_id = 'done_s2'],
  ['empty accepted forms', s => s.nodes[0].criterion.accepted_forms = []],
  ['duplicate accepted form', s => s.nodes[0].criterion.accepted_forms.push({ text: 'MILK', requires_prompt_id: 'request_s2' })],
  ['terminal criterion', s => s.nodes[1].criterion = s.nodes[0].criterion],
  ['missing select color', s => s.nodes[0].criterion.act = 'select_item'],
  ['unsupported speech act', s => s.nodes[0].criterion.act = 'free_chat'],
  ['empty feedback', s => s.nodes[0].failure_feedback_id = ''],
  ['invalid language level', s => s.language_levels = [6]],
  ['duplicate language level', s => s.language_levels = [1, 1]],
  ['fractional version', s => s.version = 1.5],
  ['unknown top-level field', s => s.patch = {}],
  ['unknown node field', s => s.nodes[0].world_patch = {}],
  ['unknown criterion field', s => s.nodes[0].criterion.script = 'anything'],
  ['unknown slot field', s => s.nodes[0].criterion.slots.mastery = 1],
  ['unknown form field', s => s.nodes[0].criterion.accepted_forms[0].regex = '.*'],
  ['unknown prompt field', s => s.nodes[0].prompts[0].text = 'unreviewed'],
  ['unknown event field', s => s.nodes[0].success_event.command = 'open'],
];

for (const [name, mutate] of invalid) {
  test(`rejects ${name}`, () => {
    const seed = fixture();
    mutate(seed);
    assert.throws(() => validateStorySeed(seed), /invalid_story_seed:/);
  });
}

for (const value of [null, [], 'story']) {
  test(`rejects a non-object seed (${JSON.stringify(value)})`, () => {
    assert.throws(() => validateStorySeed(value), /invalid_story_seed:/);
  });
}
