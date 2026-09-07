// 五大臣调度 · 共享类型

export const INTENTS = ['court', 'memory', 'word', 'comfort', 'object', 'chitchat'] as const;
export type Intent = (typeof INTENTS)[number];

export const MINISTERS = ['xiaop', 'ahai', 'laonie', 'xingxing', 'xiaonao'] as const;
export type MinisterId = (typeof MINISTERS)[number];

export const MINISTER_LABEL: Record<MinisterId, string> = {
  xiaop: '小P',
  ahai: '阿海',
  laonie: '老颞',
  xingxing: '杏杏',
  xiaonao: '小脑',
};

// 小P=前额叶(调度/闲聊/澄清), 阿海=海马体(情景记忆), 老颞=颞叶(语义/KG),
// 杏杏=杏仁核(情绪/安抚), 小脑=小脑(朝会仪式/程序技能)
export const MINISTER_STORE: Record<MinisterId, StoreId> = {
  xiaop: 'working',
  ahai: 'episodic',
  laonie: 'semantic',
  xingxing: 'affective',
  xiaonao: 'procedural',
};

export const STORES = ['episodic', 'semantic', 'affective', 'procedural', 'working'] as const;
export type StoreId = (typeof STORES)[number];

export interface Emotion {
  valence: number; // -1..1 负面..正面
  arousal: number; // 0..1 平静..激动
  label?: string;  // ASR 声学情绪标签,如 sad / calm / excited
}

export interface AsrMeta {
  conf?: number; // ASR 识别置信度 0..1
  lang?: string;
}

export type MemoryWriteKind =
  | 'milestone'
  | 'first_behavior'
  | 'word_learned'
  | 'fact'
  | 'dialogue'
  | 'affect_event'
  | 'ritual_result'
  | 'script_state'
  | (string & {});

export interface MemoryWriteEntry {
  id?: string;
  store?: StoreId;       // 缺省时按 minister 归属推导
  minister?: MinisterId;
  kind: MemoryWriteKind;
  payload: Record<string, unknown>;
  ts?: number;
}

export interface WriteAckItem {
  id: string;
  store: StoreId;
  ok: boolean;
  attempts: number;
  salience: number;
  whitelisted: boolean;
  pending_review?: boolean; // 与 KG 冲突,标待审走 04 冲突接口
  dead_letter?: boolean;
  error?: string;
}

export interface Turn {
  ts: number;
  role: 'child' | 'minister';
  minister?: MinisterId;
  text: string;
  intent?: Intent;
}

export interface ScriptState {
  [k: string]: unknown; // 如 { plot: '朝会', scene: '金銮殿', role: '小皇上', act: 3 }
}

export interface CtxBundle {
  intent: Intent;
  minister: MinisterId;
  budget: number;
  tokens_used: number;
  script_state: ScriptState;
  recent_turns: Turn[];     // 按时间升序,最多 max_recent_turns 轮
  today_words: string[];
  emotion: Emotion;
  notes: string[];          // 注入提示:澄清提示 / 安全标记 / 预算裁剪说明
}

export interface DispatchRequest {
  session_id: string;
  utterance: string;
  asr?: AsrMeta | number;             // number 视为 asr.conf
  emotion?: number | Partial<Emotion>; // number 视为 valence
  memory_write?: MemoryWriteEntry[];   // 剧情引擎(01)随消息提交的写库请求
  assistant_reply?: string;            // 下游大臣 LLM 的回复,记录为对话轮并过输出钩子
  script_state?: ScriptState;          // 剧情引擎推送的剧本状态更新(merge)
}

export interface DispatchSafety {
  input_filtered: boolean;
  injection_suspected: boolean;
  output_filtered: boolean;
}

export interface DispatchResponse {
  route_id: string;
  session_id: string;
  intent: Intent;
  confidence: number;
  need_clarify: boolean;
  clarify_question?: string;
  minister: MinisterId;
  minister_label: string;
  fallback_used: boolean;
  route_reason: string;
  ctx_bundle: CtxBundle;
  memory_write_ack: WriteAckItem[];
  latency_ms: number;
  safety: DispatchSafety;
}

/** Learning-first contracts. These replace minister selection on new callers. */
export interface CurriculumProposal {
  primary_target: string;
  review_targets: string[];
  i_plus_1_target: string;
  language_level: number;
  priority: number;
}

export interface ScaffoldProposal {
  scaffold_level: number;
  prompt_pattern: string;
  fallback_pattern: string;
  max_attempts: number;
}

export interface StoryProposal {
  story_action: string;
  world_role: string;
  success_feedback: string;
  state_patch: Record<string, unknown>;
}

export interface TeachingAction {
  learning_goal: string;
  target_expression: string;
  language_level: number;
  scaffold_level: number;
  teaching_action: 'ask' | 'reinvite' | 'prompt' | 'recast' | 'advance_story' | 'explore' | 'pause';
  correction_policy: 'recast' | 'ignore' | 'explicit_later';
  story_action: string;
  success_condition: Record<string, unknown>;
  memory_policy: 'no_write' | 'candidate' | 'confirmed';
}

export interface DirectRequest {
  session_id: string;
  utterance: string;
  asr?: AsrMeta | number;
  emotion?: number | Partial<Emotion>;
  detected_object?: string | null;
  story_state?: Record<string, unknown>;
  learner_state?: Record<string, unknown>;
  recent_attempts?: Array<{ success?: boolean; scaffold_level?: number }>;
}

export interface DirectResponse {
  contract_version: '1.0';
  session_id: string;
  learning_goal: string;
  target_expression: string;
  curriculum: CurriculumProposal;
  scaffold: ScaffoldProposal;
  story: StoryProposal;
  teaching_action: TeachingAction;
  /** Flattened aliases keep the migration contract convenient for thin clients. */
  scaffold_level: number;
  story_action: string;
  success_condition: Record<string, unknown>;
  ctx_bundle: { session_state: Record<string, unknown>; story_state: Record<string, unknown>; learner_state: Record<string, unknown> };
  safety: { emotion_priority: boolean; input_filtered: boolean; injection_suspected: boolean };
}

export interface IntentResult {
  intent: Intent;
  confidence: number;
  scores: Record<Intent, number>;
  need_clarify: boolean;
  top2: [Intent, Intent];
}
