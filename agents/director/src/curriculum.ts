import type { CurriculumProposal, DirectRequest, LanguageLevel } from './types.ts';

const fallback = { expression: 'Open, please.', goal: 'make a polite request' };

export class CurriculumAgent {
  propose(req: DirectRequest): CurriculumProposal {
    const object = (req.detected_object ?? '').trim().toLowerCase();
    const table: Record<string, { expression: string; goal: string }> = {
      milk: { expression: 'I want milk.', goal: 'request a familiar object' },
      water: { expression: 'I want water.', goal: 'request a familiar object' },
      open: fallback,
      apple: { expression: 'I like apples.', goal: 'express a preference' },
    };
    const target = table[object] ?? Object.entries(table).find(([key]) => req.utterance.toLowerCase().includes(key))?.[1] ?? fallback;
    const level = Math.max(0, Math.min(5, Number(req.learner_state?.language_level ?? 1))) as LanguageLevel;
    const review = Array.isArray(req.learner_state?.candidate_weaknesses) ? req.learner_state?.candidate_weaknesses.filter((v): v is string => typeof v === 'string').slice(0, 2) : [];
    return { learning_goal: target.goal, primary_target: target.expression, review_targets: review, i_plus_1_target: target.expression, language_level: level, priority: review.length ? 0.95 : 0.8 };
  }
}
