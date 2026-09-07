import type {
  CurriculumProposal,
  DirectRequest,
  DirectResponse,
  ScaffoldProposal,
  StoryProposal,
  TeachingAction,
} from './types.ts';

const TARGETS: Record<string, { expression: string; goal: string }> = {
  milk: { expression: 'I want milk.', goal: 'request a familiar object' },
  water: { expression: 'I want water.', goal: 'request a familiar object' },
  open: { expression: 'Open, please.', goal: 'make a polite request' },
  apple: { expression: 'I like apples.', goal: 'express a preference' },
};

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function chooseTarget(req: DirectRequest): { expression: string; goal: string } {
  const object = (req.detected_object ?? '').trim().toLowerCase();
  if (TARGETS[object]) return TARGETS[object];
  const text = req.utterance.toLowerCase();
  for (const [key, target] of Object.entries(TARGETS)) {
    if (text.includes(key)) return target;
  }
  return TARGETS.open!;
}

function emotionValue(emotion: DirectRequest['emotion']): number {
  if (typeof emotion === 'number') return clamp(emotion, -1, 1);
  return clamp(Number(emotion?.valence ?? 0), -1, 1);
}

export class LearningDirector {
  direct(req: DirectRequest): DirectResponse {
    const target = chooseTarget(req);
    const attempts = req.recent_attempts ?? [];
    const failures = attempts.filter((a) => a.success === false).length;
    const successes = attempts.filter((a) => a.success === true).length;
    const distressed = emotionValue(req.emotion) < -0.45;
    const scaffoldLevel = distressed ? 6 : clamp(2 + failures - Math.min(successes, 2), 0, 5);
    const languageLevel = clamp(Number(req.learner_state?.language_level ?? 1), 0, 5);
    const curriculum: CurriculumProposal = {
      primary_target: target.expression,
      review_targets: [],
      i_plus_1_target: target.expression,
      language_level: languageLevel,
      priority: distressed ? 0.1 : 0.8,
    };
    const scaffold: ScaffoldProposal = {
      scaffold_level: scaffoldLevel,
      prompt_pattern: scaffoldLevel >= 5 ? `Say: ${target.expression}` : scaffoldLevel === 4 ? target.expression.replace(/\.$/, ' ___ .') : scaffoldLevel === 3 ? target.expression.split(' ')[0] + ' ...' : scaffoldLevel === 2 ? 'Milk or water?' : 'What do you want?',
      fallback_pattern: distressed ? 'You can just listen.' : `Let’s try: ${target.expression}`,
      max_attempts: distressed ? 1 : 2,
    };
    const story: StoryProposal = {
      story_action: distressed ? 'pause_and_offer_comfort' : `world_waits_for_${target.expression.split(' ')[1]?.replace(/\W/g, '') ?? 'words'}`,
      world_role: '小P',
      success_feedback: `The world heard “${target.expression.replace(/\.$/, '')}”!`,
      state_patch: { objective: target.goal },
    };
    const successToken = (req.detected_object ?? '').trim().toLowerCase() ||
      target.expression.replace(/[^A-Za-z ]/g, '').trim().split(/\s+/).filter((word) => word.toLowerCase() !== 'please').pop() ||
      target.expression;
    const teachingAction: TeachingAction = {
      learning_goal: target.goal,
      target_expression: target.expression,
      language_level: languageLevel,
      scaffold_level: scaffoldLevel,
      teaching_action: distressed ? 'pause' : failures > 0 ? 'prompt' : 'ask',
      correction_policy: 'recast',
      story_action: story.story_action,
      success_condition: { contains: successToken, intelligible: true },
      memory_policy: 'candidate',
    };
    return {
      contract_version: '1.0',
      session_id: req.session_id,
      learning_goal: target.goal,
      target_expression: target.expression,
      curriculum,
      scaffold,
      story,
      teaching_action: teachingAction,
      scaffold_level: teachingAction.scaffold_level,
      story_action: teachingAction.story_action,
      success_condition: teachingAction.success_condition,
      ctx_bundle: {
        session_state: { session_id: req.session_id },
        story_state: req.story_state ?? {},
        learner_state: req.learner_state ?? {},
      },
      safety: { emotion_priority: distressed, input_filtered: false, injection_suspected: false },
    };
  }
}
