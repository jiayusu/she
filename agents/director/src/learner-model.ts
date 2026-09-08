import type { LanguageLevel, ScaffoldLevel } from './types.ts';
import type { AssessmentResult } from './assessment.ts';

export type MasteryState = 'UNSEEN' | 'HEARD' | 'COMPREHENDED' | 'IMITATED' | 'PROMPTED_OUTPUT' | 'SPONTANEOUS_OUTPUT' | 'TRANSFERRED';

export interface LearnerState {
  language_level: LanguageLevel;
  mastery: Record<string, MasteryState>;
  candidate_weaknesses: string[];
  confirmed_weaknesses: string[];
  evidence_count: Record<string, number>;
  preferred_scaffold: ScaffoldLevel;
}

export interface LearnerUpdate {
  state: LearnerState;
  evidence_status: 'OBSERVED_ONCE' | 'REPEATED' | 'CONFIRMED';
}

const rank: Record<MasteryState, number> = { UNSEEN: 0, HEARD: 1, COMPREHENDED: 2, IMITATED: 3, PROMPTED_OUTPUT: 4, SPONTANEOUS_OUTPUT: 5, TRANSFERRED: 6 };

export class LearnerModelAgent {
  update(current: Record<string, unknown> | undefined, expression: string, assessment: AssessmentResult): LearnerUpdate {
    const previous = (current ?? {}) as Partial<LearnerState>;
    const mastery = { ...(previous.mastery ?? {}) } as Record<string, MasteryState>;
    const evidenceCount = { ...(previous.evidence_count ?? {}) } as Record<string, number>;
    const count = (evidenceCount[expression] ?? 0) + (assessment.target_reached ? 1 : 0);
    evidenceCount[expression] = count;
    const oldState = mastery[expression] ?? 'UNSEEN';
    const candidate = assessment.target_reached ? (assessment.spontaneous ? 'SPONTANEOUS_OUTPUT' : 'PROMPTED_OUTPUT') as MasteryState : oldState;
    if (rank[candidate] > rank[oldState]) mastery[expression] = candidate;
    const confirmed = count >= 2 && assessment.assessment_confidence >= 0.8 && assessment.spontaneous;
    const candidates = new Set(previous.candidate_weaknesses ?? []);
    const confirmedWeaknesses = new Set(previous.confirmed_weaknesses ?? []);
    if (!assessment.target_reached) candidates.add(expression);
    if (confirmed) { candidates.delete(expression); confirmedWeaknesses.delete(expression); }
    return {
      state: {
        language_level: (previous.language_level ?? 1) as LanguageLevel,
        mastery,
        candidate_weaknesses: [...candidates],
        confirmed_weaknesses: [...confirmedWeaknesses],
        evidence_count: evidenceCount,
        preferred_scaffold: Math.max(0, Math.min(6, previous.preferred_scaffold ?? 2)) as ScaffoldLevel,
      },
      evidence_status: confirmed ? 'CONFIRMED' : count > 1 ? 'REPEATED' : 'OBSERVED_ONCE',
    };
  }
}
