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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
