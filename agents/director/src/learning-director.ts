import type {
  DirectRequest,
  DirectResponse,
  TeachingAction,
  ScaffoldLevel,
} from "./types.ts";
import { AssessmentAgent, type AssessmentResult } from "./assessment.ts";
import { CurriculumAgent } from "./curriculum.ts";
import { ScaffoldAgent } from "./scaffold.ts";
import { StoryWorldAgent } from "./story.ts";
import { LearningLoopHooks, type LoopReason } from "./learning-loop.ts";

interface SessionTurn {
  action: TeachingAction;
  failures: number;
  touched: number;
}
interface DirectorOptions {
  now?: () => number;
  sessionTtlMs?: number;
  maxSessions?: number;
}
const clamp = (n: number, min: number, max: number) =>
  Math.max(min, Math.min(max, n));
function emotionValue(emotion: DirectRequest["emotion"]): number {
  const value =
    typeof emotion === "number" ? emotion : Number(emotion?.valence ?? 0);
  return Number.isFinite(value) ? clamp(value, -1, 1) : 0;
}
function confidence(req: DirectRequest): number {
  const value =
    typeof req.asr === "number" ? req.asr : Number(req.asr?.conf ?? 0);
  return Number.isFinite(value) ? clamp(value, 0, 1) : 0;
}
function notAssessed(level: ScaffoldLevel, reason: string): AssessmentResult {
  return {
    target_reached: false,
    semantic_correctness: 0,
    spontaneous: false,
    prompt_level_used: level,
    pronunciation_intelligibility: 0,
    response_latency_ms: 0,
    error_type: reason,
    assessment_confidence: 0,
    learning_evidence: [],
  };
}

export class LearningDirector {
  private readonly curriculumAgent = new CurriculumAgent();
  private readonly scaffoldAgent = new ScaffoldAgent();
  private readonly storyAgent = new StoryWorldAgent();
  private readonly assessmentAgent = new AssessmentAgent();
  private readonly turns = new Map<string, SessionTurn>();
  private readonly now: () => number;
  private readonly ttl: number;
  private readonly capacity: number;

  constructor(options: DirectorOptions = {}) {
    this.now = options.now ?? Date.now;
    this.ttl = options.sessionTtlMs ?? 15 * 60 * 1000;
    this.capacity = options.maxSessions ?? 1000;
    if (
      !(this.ttl > 0) ||
      !Number.isFinite(this.ttl) ||
      !Number.isInteger(this.capacity) ||
      this.capacity < 1
    )
      throw new Error("invalid_learning_session_limits");
  }

  direct(req: DirectRequest): DirectResponse {
    const hooks = new LearningLoopHooks();
    const now = this.now();
    const prior = hooks.run("input", () => {
      for (const [id, turn] of this.turns)
        if (now - turn.touched >= this.ttl) this.turns.delete(id);
      return this.turns.get(req.session_id);
    });
    const distressed = emotionValue(req.emotion) < -0.45;
    const uncertain = confidence(req) < 0.8;
    const wasPaused = prior?.action.teaching_action === "pause";
    const voluntaryResume =
      wasPaused && req.utterance.trim().length > 0 && !uncertain && !distressed;
    const listening = wasPaused && !voluntaryResume;
    const canAssess = !!prior && !wasPaused && !uncertain && !distressed;
    const assessment = hooks.run("assessment", () =>
      canAssess
        ? this.assessmentAgent.assess({
            request: req,
            targetExpression: prior.action.target_expression,
            scaffoldLevel: prior.action.scaffold_level,
          })
        : notAssessed(
            prior?.action.scaffold_level ?? 0,
            !prior ? "no_previous_action" : "not_assessed",
          ),
    );
    let failures = canAssess
      ? assessment.target_reached
        ? 0
        : Math.min(2, (prior?.failures ?? 0) + 1)
      : voluntaryResume
        ? 0
        : (prior?.failures ?? 0);
    const curriculum = hooks.run("curriculum", () => {
      const proposal = this.curriculumAgent.propose(req);
      // A missed/uncertain reply is not a request to silently switch the teaching target.
      if (
        prior &&
        !voluntaryResume &&
        (!assessment.target_reached || uncertain)
      ) {
        return {
          ...proposal,
          primary_target: prior.action.target_expression,
          learning_goal: prior.action.learning_goal,
          i_plus_1_target: prior.action.target_expression,
          language_level: prior.action.language_level,
        };
      }
      return proposal;
    });
    if (prior && curriculum.primary_target !== prior.action.target_expression)
      failures = 0;
    const pause = distressed || listening || failures >= 2;
    const reason: LoopReason = distressed
      ? "emotion_pause"
      : listening
        ? "listening"
        : failures >= 2
          ? "attempt_limit"
          : !prior
            ? "first_contact"
            : voluntaryResume
              ? "voluntary_resume"
              : uncertain
                ? "uncertain_input"
                : "reply_observed";
    const scaffold = hooks.run("scaffold", () => {
      const attempts = Array.from({ length: failures }, () => ({
        success: false,
      }));
      const proposal = this.scaffoldAgent.propose(
        { ...req, recent_attempts: attempts },
        pause,
        curriculum.primary_target,
      );
      if (uncertain && prior && !pause)
        return {
          ...proposal,
          scaffold_level: prior.action.scaffold_level,
          prompt_pattern: "Invite clarification without judging the response.",
          max_attempts: 1,
        };
      return proposal;
    });
    const story = hooks.run("story", () =>
      this.storyAgent.propose(
        req,
        curriculum.primary_target,
        curriculum.learning_goal,
        pause,
      ),
    );
    const teachingAction = hooks.run(
      "decision",
      (): TeachingAction => ({
        learning_goal: curriculum.learning_goal,
        target_expression: curriculum.primary_target,
        language_level: curriculum.language_level,
        scaffold_level: scaffold.scaffold_level,
        teaching_action: pause
          ? "pause"
          : uncertain && prior
            ? "reinvite"
            : assessment.target_reached
              ? "advance_story"
              : failures
                ? "prompt"
                : "ask",
        correction_policy: "recast",
        story_action: story.story_action,
        success_condition: {
          contains: curriculum.primary_target,
          intelligible: true,
        },
        // This is a candidate policy only. Durable evidence belongs to Shared State APIs.
        memory_policy:
          canAssess && assessment.target_reached ? "candidate" : "no_write",
      }),
    );
    this.turns.delete(req.session_id);
    if (this.turns.size >= this.capacity)
      this.turns.delete(this.turns.keys().next().value!);
    this.turns.set(req.session_id, {
      action: structuredClone(teachingAction),
      failures,
      touched: now,
    });
    return {
      contract_version: "1.0",
      session_id: req.session_id,
      learning_goal: curriculum.learning_goal,
      target_expression: curriculum.primary_target,
      curriculum,
      scaffold,
      story,
      teaching_action: teachingAction,
      scaffold_level: teachingAction.scaffold_level,
      story_action: teachingAction.story_action,
      success_condition: teachingAction.success_condition,
      assessment,
      evidence_status: "OBSERVED_ONCE",
      learning_loop: hooks.finish({
        assessed_target: canAssess ? prior.action.target_expression : null,
        failed_attempts: failures,
        reason,
      }),
      ctx_bundle: {
        session_state: { session_id: req.session_id },
        story_state: req.story_state ?? {},
        learner_state: structuredClone(req.learner_state ?? {}),
      },
      safety: {
        emotion_priority: distressed,
        input_filtered: false,
        injection_suspected: false,
      },
    };
  }
}
