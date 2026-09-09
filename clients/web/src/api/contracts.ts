export const SUPPORTED_CONTRACT_VERSION = "1.0";

export interface VersionedContract {
  contract_version: string;
}

export type MasteryState =
  | "UNSEEN"
  | "HEARD"
  | "COMPREHENDED"
  | "IMITATED"
  | "PROMPTED_OUTPUT"
  | "SPONTANEOUS_OUTPUT"
  | "TRANSFERRED";

export type EvidenceKind = "prompted" | "spontaneous" | "transferred" | "comprehension";

export type TeachingPressure = "low" | "normal";

export interface PetSummary {
  name: string;
  mood: string;
  accessibility_label: string;
}

export interface HighlightSummary {
  text: string;
  evidence_id: string;
}

export interface TodayTask {
  title: string;
  subtitle: string;
  progress: number;
  action_label: string;
}

export interface DashboardMetrics {
  spontaneous_speaking_count: number;
  unprompted_output_count: number;
  new_words: string[];
}

export interface DeviceSummary {
  device_id: string;
  name: string;
  online: boolean;
  battery_percent: number | null;
}

export interface DashboardSnapshot extends VersionedContract {
  generated_at: string;
  greeting: string;
  pet: PetSummary;
  highlight: HighlightSummary;
  task: TodayTask;
  metrics: DashboardMetrics;
  device: DeviceSummary;
  mock: boolean;
}

export interface LearningEvidence {
  evidence_id: string;
  kind: EvidenceKind;
  expression: string;
  occurred_at: string;
  confidence: number;
}

export interface MasteryUpdate {
  expression: string;
  from: MasteryState;
  to: MasteryState;
  evidence_ids: string[];
}

export interface WeeklyReport extends VersionedContract {
  period_start: string;
  period_end: string;
  spontaneous_speaking_count: number;
  prompted_speaking_count: number;
  new_spontaneous_words: string[];
  transferred_words: string[];
  current_focus: string;
  scaffold_trend: string;
  evidence: LearningEvidence[];
  mastery_updates: MasteryUpdate[];
  mock: boolean;
}

export interface DeviceSettings extends VersionedContract {
  device_id: string;
  name: string;
  online: boolean;
  battery_percent: number | null;
  volume: number;
  led_enabled: boolean;
  camera_enabled: boolean;
  raw_audio_upload_enabled: boolean;
  firmware_version: string;
  last_seen_at: string;
  mock: boolean;
}

export interface DeviceSettingsPatch {
  volume?: number;
  led_enabled?: boolean;
  camera_enabled?: boolean;
  raw_audio_upload_enabled?: boolean;
}

export interface ParentConstraints extends VersionedContract {
  session_budget_seconds: number;
  preferred_topics: string[];
  avoid_topics: string[];
  next_day_context: string;
  teaching_pressure: TeachingPressure;
  updated_at: string;
  mock: boolean;
}

export interface ParentConstraintsUpdate {
  session_budget_seconds: number;
  preferred_topics: string[];
  avoid_topics: string[];
  next_day_context: string;
  teaching_pressure: TeachingPressure;
}

export interface PrivacyOperation extends VersionedContract {
  operation: string;
  status: string;
  mock: boolean;
  store_mutated: boolean;
}

export type RpgDeliveryStatus = "planned" | "issuing" | "completed" | "failed" | "expired";
export type RpgNodeId = "collect_milk" | "find_red_cup" | "picnic_ready";
export type RpgPhase =
  | "seeking_object"
  | "confirming_object"
  | "presenting"
  | "awaiting_speech"
  | "resolving"
  | "paused"
  | "delivery_failed"
  | "completed";
export type RpgInventoryToken = "milk_token" | "red_cup_token";
export type RpgObject = "fridge" | "table" | "red_cup" | "blue_cup";
export type RpgWorldRole = "饮品保管员" | "杯子管理员" | "野餐向导";
export type RpgActionKind =
  | "ask"
  | "reinvite"
  | "prompt"
  | "recast"
  | "advance_story"
  | "explore"
  | "pause";
export type RpgPromptId =
  | `collect_milk_s${0 | 1 | 2 | 3 | 4 | 5 | 6}`
  | `find_red_cup_s${0 | 1 | 2 | 3 | 4 | 5 | 6}`
  | `picnic_ready_s${0 | 1 | 2 | 3 | 4 | 5 | 6}`;
export type RpgFeedbackId =
  | RpgPromptId
  | "milk_ready"
  | "milk_help"
  | "red_cup_ready"
  | "red_cup_help"
  | "picnic_complete"
  | "picnic_pause";

export interface RpgQuest {
  seed_id: "milk_picnic";
  seed_version: 1;
  node_id: RpgNodeId;
  phase: RpgPhase;
  world_revision: number;
  inventory: RpgInventoryToken[];
  completed_nodes: RpgNodeId[];
  confirmed_object: RpgObject | null;
  world_role: RpgWorldRole;
  action_kind: RpgActionKind;
  target_expression: string;
  prompt_id: RpgPromptId | null;
  feedback_id: RpgFeedbackId;
  next_quest_id: Exclude<RpgNodeId, "picnic_ready"> | null;
}

export interface RpgQuestSummary extends VersionedContract {
  contract_version: typeof SUPPORTED_CONTRACT_VERSION;
  learning_revision: number;
  turn_id: string | null;
  delivery_status: RpgDeliveryStatus | null;
  quest: RpgQuest | null;
}

export type AppApiErrorKind =
  | "offline"
  | "invalid_response"
  | "incompatible_contract"
  | "server";

export class AppApiError extends Error {
  readonly kind: AppApiErrorKind;
  readonly serverCode: string | null;

  constructor(kind: AppApiErrorKind, serverCode: string | null = null) {
    super(kind === "server" && serverCode ? `server: ${serverCode}` : kind);
    this.name = "AppApiError";
    this.kind = kind;
    this.serverCode = serverCode;
  }

  static equals(left: AppApiError | null, right: AppApiError | null): boolean {
    if (left === right) return true;
    if (!left || !right) return false;
    return left.kind === right.kind && left.serverCode === right.serverCode;
  }
}

const EVIDENCE_KINDS: ReadonlySet<string> = new Set([
  "prompted",
  "spontaneous",
  "transferred",
  "comprehension",
]);

const TEACHING_PRESSURES: ReadonlySet<string> = new Set(["low", "normal"]);

const RPG_DELIVERY_STATUSES: ReadonlySet<string> = new Set([
  "planned",
  "issuing",
  "completed",
  "failed",
  "expired",
]);
const RPG_NODE_IDS: ReadonlySet<string> = new Set([
  "collect_milk",
  "find_red_cup",
  "picnic_ready",
]);
const RPG_NEXT_QUEST_IDS: ReadonlySet<string> = new Set(["collect_milk", "find_red_cup"]);
const RPG_PHASES: ReadonlySet<string> = new Set([
  "seeking_object",
  "confirming_object",
  "presenting",
  "awaiting_speech",
  "resolving",
  "paused",
  "delivery_failed",
  "completed",
]);
const RPG_INVENTORY_TOKENS: ReadonlySet<string> = new Set(["milk_token", "red_cup_token"]);
const RPG_OBJECTS: ReadonlySet<string> = new Set(["fridge", "table", "red_cup", "blue_cup"]);
const RPG_WORLD_ROLES: ReadonlySet<string> = new Set(["饮品保管员", "杯子管理员", "野餐向导"]);
const RPG_ACTION_KINDS: ReadonlySet<string> = new Set([
  "ask",
  "reinvite",
  "prompt",
  "recast",
  "advance_story",
  "explore",
  "pause",
]);
const RPG_PROMPT_IDS: ReadonlySet<string> = new Set([
  "collect_milk_s0",
  "collect_milk_s1",
  "collect_milk_s2",
  "collect_milk_s3",
  "collect_milk_s4",
  "collect_milk_s5",
  "collect_milk_s6",
  "find_red_cup_s0",
  "find_red_cup_s1",
  "find_red_cup_s2",
  "find_red_cup_s3",
  "find_red_cup_s4",
  "find_red_cup_s5",
  "find_red_cup_s6",
  "picnic_ready_s0",
  "picnic_ready_s1",
  "picnic_ready_s2",
  "picnic_ready_s3",
  "picnic_ready_s4",
  "picnic_ready_s5",
  "picnic_ready_s6",
]);
const RPG_CONTENT_IDS: ReadonlySet<string> = new Set([
  ...RPG_PROMPT_IDS,
  "milk_ready",
  "milk_help",
  "red_cup_ready",
  "red_cup_help",
  "picnic_complete",
  "picnic_pause",
]);
const COLLECT_MILK_CONTENT_IDS: ReadonlySet<string> = new Set([
  "collect_milk_s0",
  "collect_milk_s1",
  "collect_milk_s2",
  "collect_milk_s3",
  "collect_milk_s4",
  "collect_milk_s5",
  "collect_milk_s6",
  "milk_help",
]);
const FIND_RED_CUP_CONTENT_IDS: ReadonlySet<string> = new Set([
  "find_red_cup_s0",
  "find_red_cup_s1",
  "find_red_cup_s2",
  "find_red_cup_s3",
  "find_red_cup_s4",
  "find_red_cup_s5",
  "find_red_cup_s6",
  "milk_ready",
  "red_cup_help",
]);
const PICNIC_READY_CONTENT_IDS: ReadonlySet<string> = new Set([
  "picnic_ready_s0",
  "picnic_ready_s1",
  "picnic_ready_s2",
  "picnic_ready_s3",
  "picnic_ready_s4",
  "picnic_ready_s5",
  "picnic_ready_s6",
  "red_cup_ready",
  "picnic_complete",
  "picnic_pause",
]);
const RPG_QUEST_KEYS = [
  "seed_id",
  "seed_version",
  "node_id",
  "phase",
  "world_revision",
  "inventory",
  "completed_nodes",
  "confirmed_object",
  "world_role",
  "action_kind",
  "target_expression",
  "prompt_id",
  "feedback_id",
  "next_quest_id",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertExactKeys(record: Record<string, unknown>, expected: readonly string[]): void {
  const expectedKeys = new Set(expected);
  const actual = Object.keys(record);
  if (actual.length !== expected.length || actual.some((key) => !expectedKeys.has(key))) {
    throw new AppApiError("invalid_response");
  }
}

function stringField(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (typeof value !== "string") throw new AppApiError("invalid_response");
  return value;
}

function numberField(record: Record<string, unknown>, key: string): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) throw new AppApiError("invalid_response");
  return value;
}

function nonNegativeIntegerField(record: Record<string, unknown>, key: string): number {
  const value = numberField(record, key);
  if (!Number.isInteger(value) || value < 0) throw new AppApiError("invalid_response");
  return value;
}

function booleanField(record: Record<string, unknown>, key: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") throw new AppApiError("invalid_response");
  return value;
}

function nullableNumberField(record: Record<string, unknown>, key: string): number | null {
  const value = record[key];
  if (value === null) return null;
  if (typeof value !== "number" || !Number.isFinite(value)) throw new AppApiError("invalid_response");
  return value;
}

function stringArrayField(record: Record<string, unknown>, key: string): string[] {
  const value = record[key];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new AppApiError("invalid_response");
  }
  return value as string[];
}

function enumStringField<T extends string>(
  record: Record<string, unknown>,
  key: string,
  values: ReadonlySet<string>,
): T {
  const value = stringField(record, key);
  if (!values.has(value)) throw new AppApiError("invalid_response");
  return value as T;
}

function nullableEnumStringField<T extends string>(
  record: Record<string, unknown>,
  key: string,
  values: ReadonlySet<string>,
): T | null {
  const value = record[key];
  if (value === null) return null;
  if (typeof value !== "string" || !values.has(value)) {
    throw new AppApiError("invalid_response");
  }
  return value as T;
}

function enumStringArrayField<T extends string>(
  record: Record<string, unknown>,
  key: string,
  values: ReadonlySet<string>,
  maxItems: number,
): T[] {
  const items = stringArrayField(record, key);
  if (items.length > maxItems || new Set(items).size !== items.length) {
    throw new AppApiError("invalid_response");
  }
  if (items.some((item) => !values.has(item))) throw new AppApiError("invalid_response");
  return items as T[];
}

function nullableIdField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  if (value === null) return null;
  if (typeof value !== "string" || !/^[A-Za-z0-9_.-]{1,120}$/.test(value)) {
    throw new AppApiError("invalid_response");
  }
  return value;
}

function sameItems(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

function requireRpg(condition: boolean): void {
  if (!condition) throw new AppApiError("invalid_response");
}

function recordField(record: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = record[key];
  if (!isRecord(value)) throw new AppApiError("invalid_response");
  return value;
}

function optionalBooleanPatch(
  record: Record<string, unknown>,
  key: string,
): boolean | undefined {
  const value = record[key];
  if (value === undefined) return undefined;
  if (typeof value !== "boolean") throw new AppApiError("invalid_response");
  return value;
}

/** Decode + validate one contract payload; throws AppApiError on any drift. */
function decodeVersioned(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new AppApiError("invalid_response");
  if (stringField(value, "contract_version") !== SUPPORTED_CONTRACT_VERSION) {
    throw new AppApiError("incompatible_contract");
  }
  return value;
}

export function decodeDashboardSnapshot(value: unknown): DashboardSnapshot {
  const root = decodeVersioned(value);
  const metrics = recordField(root, "metrics");
  const device = recordField(root, "device");
  const pet = recordField(root, "pet");
  const highlight = recordField(root, "highlight");
  const task = recordField(root, "task");
  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    generated_at: stringField(root, "generated_at"),
    greeting: stringField(root, "greeting"),
    pet: {
      name: stringField(pet, "name"),
      mood: stringField(pet, "mood"),
      accessibility_label: stringField(pet, "accessibility_label"),
    },
    highlight: {
      text: stringField(highlight, "text"),
      evidence_id: stringField(highlight, "evidence_id"),
    },
    task: {
      title: stringField(task, "title"),
      subtitle: stringField(task, "subtitle"),
      progress: numberField(task, "progress"),
      action_label: stringField(task, "action_label"),
    },
    metrics: {
      spontaneous_speaking_count: numberField(metrics, "spontaneous_speaking_count"),
      unprompted_output_count: numberField(metrics, "unprompted_output_count"),
      new_words: stringArrayField(metrics, "new_words"),
    },
    device: {
      device_id: stringField(device, "device_id"),
      name: stringField(device, "name"),
      online: booleanField(device, "online"),
      battery_percent: nullableNumberField(device, "battery_percent"),
    },
    mock: booleanField(root, "mock"),
  };
}

export function decodeWeeklyReport(value: unknown): WeeklyReport {
  const root = decodeVersioned(value);
  const evidence = root.evidence;
  const masteryUpdates = root.mastery_updates;
  if (!Array.isArray(evidence) || !Array.isArray(masteryUpdates)) {
    throw new AppApiError("invalid_response");
  }
  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    period_start: stringField(root, "period_start"),
    period_end: stringField(root, "period_end"),
    spontaneous_speaking_count: numberField(root, "spontaneous_speaking_count"),
    prompted_speaking_count: numberField(root, "prompted_speaking_count"),
    new_spontaneous_words: stringArrayField(root, "new_spontaneous_words"),
    transferred_words: stringArrayField(root, "transferred_words"),
    current_focus: stringField(root, "current_focus"),
    scaffold_trend: stringField(root, "scaffold_trend"),
    evidence: evidence.map((item) => {
      if (!isRecord(item)) throw new AppApiError("invalid_response");
      const kind = stringField(item, "kind");
      if (!EVIDENCE_KINDS.has(kind)) throw new AppApiError("invalid_response");
      return {
        evidence_id: stringField(item, "evidence_id"),
        kind: kind as EvidenceKind,
        expression: stringField(item, "expression"),
        occurred_at: stringField(item, "occurred_at"),
        confidence: numberField(item, "confidence"),
      };
    }),
    mastery_updates: masteryUpdates.map((item) => {
      if (!isRecord(item)) throw new AppApiError("invalid_response");
      return {
        expression: stringField(item, "expression"),
        from: stringField(item, "from") as MasteryState,
        to: stringField(item, "to") as MasteryState,
        evidence_ids: stringArrayField(item, "evidence_ids"),
      };
    }),
    mock: booleanField(root, "mock"),
  };
}

export function decodeDeviceSettings(value: unknown): DeviceSettings {
  const root = decodeVersioned(value);
  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    device_id: stringField(root, "device_id"),
    name: stringField(root, "name"),
    online: booleanField(root, "online"),
    battery_percent: nullableNumberField(root, "battery_percent"),
    volume: numberField(root, "volume"),
    led_enabled: booleanField(root, "led_enabled"),
    camera_enabled: booleanField(root, "camera_enabled"),
    raw_audio_upload_enabled: booleanField(root, "raw_audio_upload_enabled"),
    firmware_version: stringField(root, "firmware_version"),
    last_seen_at: stringField(root, "last_seen_at"),
    mock: booleanField(root, "mock"),
  };
}

export function decodeParentConstraints(value: unknown): ParentConstraints {
  const root = decodeVersioned(value);
  const pressure = stringField(root, "teaching_pressure");
  if (!TEACHING_PRESSURES.has(pressure)) throw new AppApiError("invalid_response");
  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    session_budget_seconds: numberField(root, "session_budget_seconds"),
    preferred_topics: stringArrayField(root, "preferred_topics"),
    avoid_topics: stringArrayField(root, "avoid_topics"),
    next_day_context: stringField(root, "next_day_context"),
    teaching_pressure: pressure as TeachingPressure,
    updated_at: stringField(root, "updated_at"),
    mock: booleanField(root, "mock"),
  };
}

export function decodePrivacyOperation(value: unknown): PrivacyOperation {
  const root = decodeVersioned(value);
  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    operation: stringField(root, "operation"),
    status: stringField(root, "status"),
    mock: booleanField(root, "mock"),
    store_mutated: booleanField(root, "store_mutated"),
  };
}

/**
 * Strictly decode the bounded milk_picnic quest projection. Unlike the older
 * parent-demo contracts, this client-boundary decoder rejects unknown keys and
 * impossible node snapshots instead of silently dropping response drift.
 */
export function decodeRpgQuestSummary(value: unknown): RpgQuestSummary {
  const root = decodeVersioned(value);
  assertExactKeys(root, [
    "contract_version",
    "learning_revision",
    "turn_id",
    "delivery_status",
    "quest",
  ]);
  const learningRevision = nonNegativeIntegerField(root, "learning_revision");
  const turnId = nullableIdField(root, "turn_id");
  const deliveryStatus = nullableEnumStringField<RpgDeliveryStatus>(
    root,
    "delivery_status",
    RPG_DELIVERY_STATUSES,
  );
  const questValue = root.quest;
  if (questValue === null) {
    return {
      contract_version: SUPPORTED_CONTRACT_VERSION,
      learning_revision: learningRevision,
      turn_id: turnId,
      delivery_status: deliveryStatus,
      quest: null,
    };
  }
  if (!isRecord(questValue)) throw new AppApiError("invalid_response");
  assertExactKeys(questValue, RPG_QUEST_KEYS);

  requireRpg(stringField(questValue, "seed_id") === "milk_picnic");
  requireRpg(nonNegativeIntegerField(questValue, "seed_version") === 1);
  const nodeId = enumStringField<RpgNodeId>(questValue, "node_id", RPG_NODE_IDS);
  const phase = enumStringField<RpgPhase>(questValue, "phase", RPG_PHASES);
  const worldRevision = nonNegativeIntegerField(questValue, "world_revision");
  const inventory = enumStringArrayField<RpgInventoryToken>(
    questValue,
    "inventory",
    RPG_INVENTORY_TOKENS,
    16,
  );
  const completedNodes = enumStringArrayField<RpgNodeId>(
    questValue,
    "completed_nodes",
    RPG_NODE_IDS,
    64,
  );
  const confirmedObject = nullableEnumStringField<RpgObject>(
    questValue,
    "confirmed_object",
    RPG_OBJECTS,
  );
  const worldRole = enumStringField<RpgWorldRole>(questValue, "world_role", RPG_WORLD_ROLES);
  const actionKind = enumStringField<RpgActionKind>(questValue, "action_kind", RPG_ACTION_KINDS);
  const targetExpression = stringField(questValue, "target_expression");
  requireRpg(targetExpression.length >= 1 && targetExpression.length <= 120);
  const promptId = nullableEnumStringField<RpgPromptId>(questValue, "prompt_id", RPG_PROMPT_IDS);
  const feedbackId = enumStringField<RpgFeedbackId>(questValue, "feedback_id", RPG_CONTENT_IDS);
  const nextQuestId = nullableEnumStringField<Exclude<RpgNodeId, "picnic_ready">>(
    questValue,
    "next_quest_id",
    RPG_NEXT_QUEST_IDS,
  );

  if (["presenting", "awaiting_speech", "resolving", "delivery_failed"].includes(phase)) {
    requireRpg(confirmedObject !== null);
  }
  if (["seeking_object", "confirming_object", "completed"].includes(phase)) {
    requireRpg(confirmedObject === null);
  }

  switch (nodeId) {
    case "collect_milk":
      requireRpg(phase !== "completed");
      requireRpg(worldRevision === 1);
      requireRpg(sameItems(inventory, []));
      requireRpg(sameItems(completedNodes, []));
      requireRpg(confirmedObject === null || confirmedObject === "fridge");
      requireRpg(worldRole === "饮品保管员");
      requireRpg(targetExpression === "I want milk.");
      requireRpg(COLLECT_MILK_CONTENT_IDS.has(feedbackId));
      requireRpg(nextQuestId === "collect_milk");
      break;
    case "find_red_cup":
      requireRpg(phase !== "completed");
      requireRpg(worldRevision === 2);
      requireRpg(sameItems(inventory, ["milk_token"]));
      requireRpg(sameItems(completedNodes, ["collect_milk"]));
      requireRpg(
        confirmedObject === null ||
          confirmedObject === "table" ||
          confirmedObject === "red_cup" ||
          confirmedObject === "blue_cup",
      );
      requireRpg(worldRole === "杯子管理员");
      requireRpg(targetExpression === "I choose the red cup.");
      requireRpg(FIND_RED_CUP_CONTENT_IDS.has(feedbackId));
      requireRpg(nextQuestId === "find_red_cup");
      break;
    case "picnic_ready":
      requireRpg(phase === "completed");
      requireRpg(worldRevision === 4);
      requireRpg(sameItems(inventory, ["milk_token", "red_cup_token"]));
      requireRpg(sameItems(completedNodes, ["collect_milk", "find_red_cup", "picnic_ready"]));
      requireRpg(confirmedObject === null);
      requireRpg(worldRole === "野餐向导");
      requireRpg(targetExpression === "Our picnic is ready.");
      requireRpg(PICNIC_READY_CONTENT_IDS.has(feedbackId));
      requireRpg(nextQuestId === null);
      break;
  }

  return {
    contract_version: SUPPORTED_CONTRACT_VERSION,
    learning_revision: learningRevision,
    turn_id: turnId,
    delivery_status: deliveryStatus,
    quest: {
      seed_id: "milk_picnic",
      seed_version: 1,
      node_id: nodeId,
      phase,
      world_revision: worldRevision,
      inventory,
      completed_nodes: completedNodes,
      confirmed_object: confirmedObject,
      world_role: worldRole,
      action_kind: actionKind,
      target_expression: targetExpression,
      prompt_id: promptId,
      feedback_id: feedbackId,
      next_quest_id: nextQuestId,
    },
  };
}

export function decodeDeviceSettingsPatch(value: unknown): DeviceSettingsPatch {
  if (!isRecord(value)) throw new AppApiError("invalid_response");
  const volume = value.volume;
  if (volume !== undefined && (typeof volume !== "number" || !Number.isFinite(volume))) {
    throw new AppApiError("invalid_response");
  }
  const patch: DeviceSettingsPatch = volume === undefined ? {} : { volume };
  for (const key of ["led_enabled", "camera_enabled", "raw_audio_upload_enabled"] as const) {
    const setting = optionalBooleanPatch(value, key);
    if (setting !== undefined) patch[key] = setting;
  }
  return patch;
}

export function encodeParentConstraintsUpdate(update: ParentConstraintsUpdate): string {
  return JSON.stringify(update);
}

export function encodeDeviceSettingsPatch(patch: DeviceSettingsPatch): string {
  return JSON.stringify(patch);
}
