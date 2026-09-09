import { readFileSync } from 'node:fs';

export type SeedLanguageLevel = 0 | 1 | 2 | 3 | 4 | 5;
export type SeedScaffoldLevel = SeedLanguageLevel | 6;
export type WorldEventKind = 'virtual_item_granted' | 'quest_completed';
export interface StoryPrompt { prompt_id: string; scaffold_level: SeedScaffoldLevel }
export interface AcceptedForm { text: string; requires_prompt_id: string | null }
export type SpeechCriterion = {
  criterion_id: string;
  accepted_forms: AcceptedForm[];
} & ({ act: 'request_item'; slots: { item: string } }
  | { act: 'select_item'; slots: { item: string; color: string } });

interface NodeContent {
  node_id: string;
  required_objects: string[];
  world_role: string;
  motivation: string;
  learning_goal: string;
  target_expression: string;
  prompts: StoryPrompt[];
  success_feedback_id: string;
  failure_feedback_id: string;
}
export type StoryNode = NodeContent & ({
  terminal: false;
  criterion: SpeechCriterion;
  success_event: { kind: 'virtual_item_granted'; item_id: string };
  next_node_id: string;
} | {
  terminal: true;
  criterion: null;
  success_event: { kind: 'quest_completed'; quest_id: string };
  next_node_id: null;
});
export interface StorySeed {
  seed_id: string;
  version: number;
  language_levels: SeedLanguageLevel[];
  start_node_id: string;
  completion_node_id: string;
  allowed_world_events: WorldEventKind[];
  allowed_items: string[];
  nodes: StoryNode[];
}

function fail(path: string, reason: string): never {
  throw new Error(`invalid_story_seed:${path}:${reason}`);
}
function object(value: unknown, keys: string[], path: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path, 'object_required');
  const result = value as Record<string, unknown>;
  if (Object.keys(result).some(key => !keys.includes(key))) fail(path, 'unknown_field');
  if (keys.some(key => !Object.hasOwn(result, key))) fail(path, 'missing_field');
  return result;
}
function text(value: unknown, path: string): string {
  if (typeof value !== 'string' || !value.trim() || value.trim() !== value || value.length > 240)
    fail(path, 'invalid_text');
  return value;
}
function id(value: unknown, path: string): string {
  const result = text(value, path);
  if (!/^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}$/.test(result)) fail(path, 'invalid_id');
  return result;
}
function array(value: unknown, path: string, min = 1): unknown[] {
  if (!Array.isArray(value) || value.length < min || value.length > 64) fail(path, 'invalid_array');
  return value;
}
function unique<T>(values: T[], path: string): T[] {
  if (new Set(values).size !== values.length) fail(path, 'duplicate');
  return values;
}
function ids(value: unknown, path: string, min = 1): string[] {
  return unique(array(value, path, min).map(v => id(v, path)), path);
}
function integer(value: unknown, min: number, max: number, path: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max)
    fail(path, 'invalid_integer');
  return value;
}
function criterion(value: unknown, prompts: StoryPrompt[], path: string): SpeechCriterion {
  const raw = object(value, ['criterion_id', 'act', 'slots', 'accepted_forms'], path);
  const act = raw.act;
  if (act !== 'request_item' && act !== 'select_item') fail(path, 'invalid_speech_act');
  const slots = object(raw.slots, act === 'select_item' ? ['item', 'color'] : ['item'], `${path}.slots`);
  const accepted_forms = array(raw.accepted_forms, `${path}.accepted_forms`).map(value => {
    const form = object(value, ['text', 'requires_prompt_id'], `${path}.form`);
    const requires_prompt_id = form.requires_prompt_id === null ? null : id(form.requires_prompt_id, `${path}.prompt`);
    if (requires_prompt_id !== null && !prompts.some(p => p.prompt_id === requires_prompt_id))
      fail(path, 'foreign_context_prompt');
    return { text: text(form.text, `${path}.form.text`), requires_prompt_id };
  });
  unique(accepted_forms.map(form => form.text.toLowerCase()), `${path}.accepted_forms`);
  const common = { criterion_id: id(raw.criterion_id, `${path}.criterion_id`), accepted_forms };
  const item = id(slots.item, `${path}.slots.item`);
  return act === 'request_item' ? { ...common, act, slots: { item } }
    : { ...common, act, slots: { item, color: id(slots.color, `${path}.slots.color`) } };
}

/** Parse a reviewed finite chain. No runtime writes, code execution or model calls. */
export function validateStorySeed(value: unknown): StorySeed {
  const raw = object(value, ['seed_id', 'version', 'language_levels', 'start_node_id',
    'completion_node_id', 'allowed_world_events', 'allowed_items', 'nodes'], 'seed');
  const seed_id = id(raw.seed_id, 'seed_id');
  const allowed_world_events = ids(raw.allowed_world_events, 'allowed_world_events').map(kind => {
    if (kind !== 'virtual_item_granted' && kind !== 'quest_completed') fail('allowed_world_events', 'invalid_kind');
    return kind;
  });
  const allowed_items = ids(raw.allowed_items, 'allowed_items', 0);
  const nodes: StoryNode[] = array(raw.nodes, 'nodes').map((value, index) => {
    const path = `nodes[${index}]`;
    const node = object(value, ['node_id', 'terminal', 'required_objects', 'world_role', 'motivation',
      'learning_goal', 'target_expression', 'criterion', 'prompts', 'success_feedback_id',
      'failure_feedback_id', 'success_event', 'next_node_id'], path);
    const terminal = node.terminal;
    if (typeof terminal !== 'boolean') fail(path, 'invalid_terminal');
    const prompts: StoryPrompt[] = array(node.prompts, `${path}.prompts`).map(value => {
      const prompt = object(value, ['prompt_id', 'scaffold_level'], `${path}.prompt`);
      return { prompt_id: id(prompt.prompt_id, `${path}.prompt_id`),
        scaffold_level: integer(prompt.scaffold_level, 0, 6, `${path}.scaffold_level`) as SeedScaffoldLevel };
    });
    if (prompts.length !== 7) fail(path, 'missing_scaffold_coverage');
    unique(prompts.map(p => p.scaffold_level), `${path}.scaffold_level`);
    const common: NodeContent = {
      node_id: id(node.node_id, `${path}.node_id`),
      required_objects: ids(node.required_objects, `${path}.required_objects`, terminal ? 0 : 1),
      world_role: text(node.world_role, `${path}.world_role`),
      motivation: text(node.motivation, `${path}.motivation`),
      learning_goal: text(node.learning_goal, `${path}.learning_goal`),
      target_expression: text(node.target_expression, `${path}.target_expression`),
      prompts, success_feedback_id: id(node.success_feedback_id, `${path}.success_feedback_id`),
      failure_feedback_id: id(node.failure_feedback_id, `${path}.failure_feedback_id`),
    };
    const event = object(node.success_event, terminal ? ['kind', 'quest_id'] : ['kind', 'item_id'], `${path}.success_event`);
    if (!allowed_world_events.includes(event.kind as WorldEventKind)) fail(path, 'undeclared_event');
    if (terminal) {
      if (node.next_node_id !== null || node.criterion !== null || common.required_objects.length)
        fail(path, 'invalid_terminal_content');
      if (event.kind !== 'quest_completed' || event.quest_id !== seed_id) fail(path, 'invalid_completion_event');
      return { ...common, terminal, criterion: null, next_node_id: null,
        success_event: { kind: 'quest_completed', quest_id: seed_id } };
    }
    const item_id = id(event.item_id, `${path}.item_id`);
    if (event.kind !== 'virtual_item_granted' || !allowed_items.includes(item_id)) fail(path, 'undeclared_item_or_event');
    return { ...common, terminal, criterion: criterion(node.criterion, prompts, `${path}.criterion`),
      next_node_id: id(node.next_node_id, `${path}.next_node_id`),
      success_event: { kind: 'virtual_item_granted', item_id } };
  });
  unique(nodes.map(n => n.node_id), 'nodes');
  unique(nodes.flatMap(n => n.prompts.map(p => p.prompt_id)), 'prompt_ids');
  unique(nodes.flatMap(n => n.criterion ? [n.criterion.criterion_id] : []), 'criterion_ids');
  const start_node_id = id(raw.start_node_id, 'start_node_id');
  const completion_node_id = id(raw.completion_node_id, 'completion_node_id');
  const byId = new Map(nodes.map(n => [n.node_id, n]));
  if (!byId.has(start_node_id)) fail('start_node_id', 'missing_node');
  if (!byId.get(completion_node_id)?.terminal) fail('completion_node_id', 'terminal_required');
  for (const node of nodes) {
    if (node.terminal && node.node_id !== completion_node_id) fail('nodes', 'extra_terminal');
    if (!node.terminal && !byId.has(node.next_node_id)) fail('nodes', 'missing_successor');
  }
  const visited = new Set<string>();
  let next: string | null = start_node_id;
  while (next !== null) {
    if (visited.has(next)) fail('nodes', 'cycle');
    visited.add(next);
    next = byId.get(next)!.next_node_id;
  }
  if (visited.size !== nodes.length) fail('nodes', 'unreachable_node');
  return { seed_id, version: integer(raw.version, 1, Number.MAX_SAFE_INTEGER, 'version'),
    language_levels: unique(array(raw.language_levels, 'language_levels').map(v =>
      integer(v, 0, 5, 'language_levels') as SeedLanguageLevel), 'language_levels'),
    start_node_id, completion_node_id, allowed_world_events, allowed_items, nodes };
}

export function loadStorySeed(path: string | URL = new URL('../content/story-seeds/milk_picnic.v1.json', import.meta.url)): StorySeed {
  const source = readFileSync(path, 'utf8');
  let value: unknown;
  try { value = JSON.parse(source); }
  catch { fail('json', 'malformed'); }
  return validateStorySeed(value);
}
