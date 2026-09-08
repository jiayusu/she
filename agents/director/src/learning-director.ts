import type { DirectRequest, DirectResponse, TeachingAction } from './types.ts';
import { AssessmentAgent } from './assessment.ts';
import { CurriculumAgent } from './curriculum.ts';
import { LearnerModelAgent } from './learner-model.ts';
import { ScaffoldAgent } from './scaffold.ts';
import { StoryWorldAgent } from './story.ts';

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function emotionValue(emotion: DirectRequest['emotion']): number {
  if (typeof emotion === 'number') return clamp(emotion, -1, 1);
  return clamp(Number(emotion?.valence ?? 0), -1, 1);
}

export class LearningDirector {
  private readonly curriculumAgent = new CurriculumAgent();
  private readonly scaffoldAgent = new ScaffoldAgent();
  private readonly storyAgent = new StoryWorldAgent();
  private readonly assessmentAgent = new AssessmentAgent();
  private readonly learnerAgent = new LearnerModelAgent();

  direct(req: DirectRequest): DirectResponse {
    const curriculum = this.curriculumAgent.propose(req);
    const distressed = emotionValue(req.emotion) < -0.45;
    const scaffold = this.scaffoldAgent.propose(req, distressed, curriculum.primary_target);
    const story = this.storyAgent.propose(req, curriculum.primary_target, curriculum.learning_goal, distressed);
    const assessment = this.assessmentAgent.assess({ request: req, targetExpression: curriculum.primary_target, scaffoldLevel: scaffold.scaffold_level });
    const learner = this.learnerAgent.update(req.learner_state, curriculum.primary_target, assessment);
    const successToken = (req.detected_object ?? '').trim().toLowerCase() || curriculum.primary_target.replace(/[^A-Za-z ]/g, '').trim().split(/\s+/).filter((word) => word.toLowerCase() !== 'please').pop() || curriculum.primary_target;
    const teachingAction: TeachingAction = {
      learning_goal: curriculum.learning_goal,
      target_expression: curriculum.primary_target,
      language_level: curriculum.language_level,
      scaffold_level: scaffold.scaffold_level,
      teaching_action: distressed ? 'pause' : (req.recent_attempts ?? []).some((a) => a.success === false) ? 'prompt' : 'ask',
      correction_policy: 'recast',
      story_action: story.story_action,
      success_condition: { contains: successToken, intelligible: true },
      memory_policy: learner.evidence_status === 'CONFIRMED' ? 'confirmed' : assessment.target_reached ? 'candidate' : 'no_write',
    };
    return {
      contract_version: '1.0',
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
      evidence_status: learner.evidence_status,
      ctx_bundle: {
        session_state: { session_id: req.session_id },
        story_state: req.story_state ?? {},
        learner_state: learner.state as unknown as Record<string, unknown>,
      },
      safety: { emotion_priority: distressed, input_filtered: false, injection_suspected: false },
    };
  }
}
