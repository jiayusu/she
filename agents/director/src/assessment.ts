import type { DirectRequest, ScaffoldLevel } from './types.ts';

export interface AssessmentResult {
  target_reached: boolean;
  semantic_correctness: number;
  spontaneous: boolean;
  prompt_level_used: ScaffoldLevel;
  pronunciation_intelligibility: number | null;
  response_latency_ms: number;
  error_type: string | null;
  assessment_confidence: number;
  learning_evidence: string[];
}

export interface AssessmentInput {
  request: DirectRequest;
  targetExpression: string;
  scaffoldLevel: ScaffoldLevel;
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

export class AssessmentAgent {
  assess(input: AssessmentInput): AssessmentResult {
    const utterance = input.request.utterance.trim();
    const targetWords = input.targetExpression.toLowerCase().replace(/[^a-z ]/g, '').split(/\s+/).filter(Boolean);
    const normalized = utterance.toLowerCase().replace(/[^a-z ]/g, ' ');
    const matched = targetWords.filter((word) => normalized.split(/\s+/).includes(word)).length;
    const semantic = targetWords.length === 0 ? 0 : clamp(matched / targetWords.length);
    // Full-expression evidence is deliberately stricter than RPG quest success.
    // A context-supported "Milk!" may advance a quest, while a different object
    // such as "I want water" must never count as mastery evidence for milk.
    const targetReached = targetWords.length > 0 && matched === targetWords.length && utterance.length > 0;
    const spontaneous = targetReached && input.scaffoldLevel <= 1;
    const asrConfidence = typeof input.request.asr === 'number'
      ? input.request.asr
      : Number(input.request.asr?.conf ?? 1);
    const confidence = clamp(Math.min(asrConfidence || 0, targetReached ? 0.98 : 0.7));
    return {
      target_reached: targetReached,
      semantic_correctness: semantic,
      spontaneous,
      prompt_level_used: input.scaffoldLevel,
      // ASR confidence measures transcript certainty, not pronunciation.
      // Keep this unknown until a dedicated evaluator supplies evidence.
      pronunciation_intelligibility: null,
      response_latency_ms: 0,
      error_type: targetReached ? null : 'target_not_observed',
      assessment_confidence: confidence,
      learning_evidence: targetReached ? [`target:${input.targetExpression}`] : [],
    };
  }
}
