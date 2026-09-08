import { appendFileSync, existsSync, readFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { DirectRequest, DirectResponse } from './types.ts';

export interface LearningEventRecord {
  contract_version: '1.0';
  event_id: string;
  session_id: string;
  occurred_at: string;
  event_kind: 'raw_observation' | 'candidate_evidence' | 'confirmed_mastery';
  evidence_status: 'OBSERVED_ONCE' | 'REPEATED' | 'CONFIRMED';
  learning_goal: string;
  target_expression: string;
  child_utterance: string;
  language_level: number;
  scaffold_level: number;
  assessment: DirectResponse['assessment'];
}

function id(): string {
  return `learning-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Shared-state adapter. The JSONL sink is local development fallback; production points it at memory service. */
export class LearningEventStore {
  private readonly path: string;
  private readonly evidence = new Map<string, number>();

  constructor(dataDir: string) {
    this.path = join(dataDir, 'learning-events.jsonl');
    mkdirSync(dirname(this.path), { recursive: true });
    if (!existsSync(this.path)) return;
    const contents = readFileSync(this.path, 'utf8');
    for (const line of contents.split(/\r?\n/)) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line) as Partial<LearningEventRecord>;
        if (event.target_expression && event.assessment?.target_reached) this.evidence.set(event.target_expression, (this.evidence.get(event.target_expression) ?? 0) + 1);
      } catch { /* one corrupt line must not prevent session recovery */ }
    }
  }

  record(req: DirectRequest, response: DirectResponse): LearningEventRecord {
    const key = response.target_expression;
    const prior = this.evidence.get(key) ?? 0;
    const reached = response.assessment.target_reached;
    const count = prior + (reached ? 1 : 0);
    if (reached) this.evidence.set(key, count);
    const confirmed = reached && count >= 2 && response.assessment.spontaneous && response.assessment.assessment_confidence >= 0.8;
    const status = confirmed ? 'CONFIRMED' : count > 1 ? 'REPEATED' : 'OBSERVED_ONCE';
    const event: LearningEventRecord = {
      contract_version: '1.0',
      event_id: id(),
      session_id: req.session_id,
      occurred_at: new Date().toISOString(),
      event_kind: confirmed ? 'confirmed_mastery' : reached ? 'candidate_evidence' : 'raw_observation',
      evidence_status: status,
      learning_goal: response.learning_goal,
      target_expression: response.target_expression,
      child_utterance: req.utterance,
      language_level: response.teaching_action.language_level,
      scaffold_level: response.teaching_action.scaffold_level,
      assessment: response.assessment,
    };
    appendFileSync(this.path, `${JSON.stringify(event)}\n`, 'utf8');
    return event;
  }
}
