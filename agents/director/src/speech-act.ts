import { createHash } from 'node:crypto';
import type { SpeechCriterion } from './story-seed.ts';
import type { ScaffoldLevel, SpeechActEvidence } from './types.ts';

const normalize = (value: string): string => value
  .toLowerCase()
  .replace(/[^a-z ]/g, ' ')
  .trim()
  .replace(/\s+/g, ' ');

function evidenceId(sourceTurnId: string, utterance: string, actionId: string): string {
  const digest = createHash('sha256')
    .update(`${sourceTurnId}\0${utterance}\0${actionId}`)
    .digest('hex')
    .slice(0, 20);
  return `se_${digest}`;
}

function parsedAct(text: string): Pick<SpeechActEvidence, 'act' | 'slots'> {
  const tokens = new Set(text.split(' ').filter(Boolean));
  const drink = tokens.has('milk') ? 'milk' : tokens.has('water') ? 'water' : null;
  if (drink) return { act: 'request_item', slots: { item: drink } };
  const color = tokens.has('red') ? 'red' : tokens.has('blue') ? 'blue' : null;
  if (color) return { act: 'select_item', slots: { item: 'cup', color } };
  return { act: 'none', slots: {} };
}

function slotsMatch(actual: SpeechActEvidence['slots'], expected: SpeechCriterion['slots']): boolean {
  return Object.entries(expected).every(([key, value]) => actual[key as keyof typeof actual] === value);
}

export interface SpeechActInput {
  utterance: string;
  asrConfidence: number;
  criterion: SpeechCriterion;
  sourceTurnId: string;
  elicitingActionId: string;
  elicitingPromptId: string | null;
  scaffoldLevel: ScaffoldLevel;
  executionConfirmed: boolean;
}

/** Resolve only reviewed forms and slots. This function never mutates world or learner state. */
export function resolveSpeechAct(input: SpeechActInput): SpeechActEvidence {
  const base = {
    evidence_id: evidenceId(input.sourceTurnId, input.utterance, input.elicitingActionId),
    source_turn_id: input.sourceTurnId,
    eliciting_action_id: input.elicitingActionId,
    criterion_id: input.criterion.criterion_id,
    confidence: Math.max(0, Math.min(1, input.asrConfidence)),
    scaffold_level_used: input.scaffoldLevel,
  } as const;
  if (!input.executionConfirmed) return {
    ...base, act: 'none', slots: {}, context_supported: false,
    quest_satisfied: false, error_type: 'no_completed_prompt',
  };
  if (base.confidence < 0.8) return {
    ...base, act: 'none', slots: {}, context_supported: false,
    quest_satisfied: false, error_type: 'low_confidence',
  };

  const normalized = normalize(input.utterance);
  const parsed = parsedAct(normalized);
  const form = input.criterion.accepted_forms.find(candidate => normalize(candidate.text) === normalized);
  const contextSupported = !!form && (
    form.requires_prompt_id === null || form.requires_prompt_id === input.elicitingPromptId
  );
  const questSatisfied = contextSupported
    && parsed.act === input.criterion.act
    && slotsMatch(parsed.slots, input.criterion.slots);
  const sameAct = parsed.act === input.criterion.act;
  return {
    ...base,
    ...parsed,
    context_supported: contextSupported,
    quest_satisfied: questSatisfied,
    error_type: questSatisfied ? null : sameAct ? 'wrong_slot' : 'unmatched',
  };
}

export function emptySpeechEvidence(input: {
  sourceTurnId: string;
  elicitingActionId: string;
  criterionId: string;
  scaffoldLevel: ScaffoldLevel;
  errorType?: SpeechActEvidence['error_type'];
}): SpeechActEvidence {
  return {
    evidence_id: evidenceId(input.sourceTurnId, '', input.elicitingActionId),
    source_turn_id: input.sourceTurnId,
    eliciting_action_id: input.elicitingActionId,
    criterion_id: input.criterionId,
    act: 'none',
    slots: {},
    confidence: 0,
    context_supported: false,
    scaffold_level_used: input.scaffoldLevel,
    quest_satisfied: false,
    error_type: input.errorType ?? 'no_completed_prompt',
  };
}
