import { randomUUID } from "node:crypto";

export const LEARNING_STAGES = [
  "input",
  "assessment",
  "curriculum",
  "scaffold",
  "story",
  "decision",
] as const;
export type LearningStage = (typeof LEARNING_STAGES)[number];
export type LoopReason =
  | "first_contact"
  | "reply_observed"
  | "uncertain_input"
  | "attempt_limit"
  | "emotion_pause"
  | "listening"
  | "voluntary_resume";
export interface LearningLoopTrace {
  version: "1.0";
  trace_id: string;
  assessed_target: string | null;
  failed_attempts: number;
  reason: LoopReason;
  stages: LearningStage[];
  state_scope: "session_only";
  memory_write: "not_performed";
}

/** Internal lifecycle hooks: observe stage boundaries, never rewrite decisions or permissions. */
export class LearningLoopHooks {
  private readonly stages: LearningStage[] = [];
  readonly traceId = randomUUID();

  run<T>(stage: LearningStage, action: () => T): T {
    if (LEARNING_STAGES[this.stages.length] !== stage)
      throw new Error("invalid_learning_stage_order");
    const result = action();
    this.stages.push(stage);
    return result;
  }

  finish(
    details: Pick<
      LearningLoopTrace,
      "assessed_target" | "failed_attempts" | "reason"
    >,
  ): LearningLoopTrace {
    if (this.stages.length !== LEARNING_STAGES.length)
      throw new Error("incomplete_learning_loop");
    return {
      version: "1.0",
      trace_id: this.traceId,
      ...details,
      stages: [...this.stages],
      state_scope: "session_only",
      memory_write: "not_performed",
    };
  }
}
