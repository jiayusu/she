import { createHash } from 'node:crypto';
import { LearningDirector } from './learning-director.ts';
import type { DirectRequest, DirectResponse } from './types.ts';

export interface DurableRequest extends DirectRequest {
  child_id: string; turn_id: string; previous_turn_id: string | null; device_id: string;
}
export class LearningError extends Error {
  constructor(message: string, readonly status = 409) { super(message); }
}
export async function jsonService(url: string, body?: unknown): Promise<any> {
  let response: Response;
  try {
    response = await fetch(url, {method:body === undefined ? 'GET' : 'POST',
      headers:{'content-type':'application/json'}, body:body === undefined ? undefined : JSON.stringify(body),
      signal:AbortSignal.timeout(2500)});
  } catch { throw new LearningError('learning_service_unavailable', 503); }
  const value = await response.json() as any;
  if (!response.ok) throw new LearningError(typeof value.error === 'string' ? value.error : value.error?.code ?? 'learning_service_error', response.status);
  return value;
}
function canonical(value: any): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
}
export function validateTurn(req: any): asserts req is DurableRequest {
  if (!req || typeof req !== 'object' || Array.isArray(req)) throw new LearningError('invalid_turn', 400);
  const allowed = new Set(['child_id','session_id','turn_id','previous_turn_id','device_id','utterance','asr','emotion','detected_object']);
  if (Object.keys(req).some(k=>!allowed.has(k))) throw new LearningError('unknown_turn_field',400);
  for (const k of ['child_id','session_id','turn_id','device_id'])
    if (typeof req[k] !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(req[k])) throw new LearningError('invalid_identity',400);
  if (req.previous_turn_id !== null && (typeof req.previous_turn_id !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(req.previous_turn_id))) throw new LearningError('invalid_previous_turn',400);
  if (typeof req.utterance !== 'string' || req.utterance.length > 2000) throw new LearningError('invalid_utterance',400);
  for (const k of ['asr','emotion']) if (req[k] !== undefined && (typeof req[k] !== 'number' || !Number.isFinite(req[k]) || req[k] > 1 || req[k] < (k==='asr'?0:-1))) throw new LearningError('invalid_confidence',400);
  if (req.detected_object !== undefined && ![null,'milk','water','apple','open'].includes(req.detected_object)) throw new LearningError('invalid_object',400);
}
export class DurableLearning {
  constructor(private readonly memoryUrl: string,
    private readonly filter: (text:string, emotion:DirectRequest['emotion'])=>{text:string;filtered:boolean;injection_suspected:boolean}) {}

  async direct(req: DurableRequest): Promise<DirectResponse> {
    validateTurn(req);
    const request_hash = createHash('sha256').update(canonical(req)).digest('hex');
    const state = await jsonService(`${this.memoryUrl}/memory/learning/state?${new URLSearchParams({child_id:req.child_id,session_id:req.session_id,turn_id:req.turn_id})}`);
    if (state.replay) {
      if (state.replay.request_hash !== request_hash) throw new LearningError('idempotency_conflict');
      return state.replay.response;
    }
    const prior = state.latest;
    if ((prior?.turn_id ?? null) !== req.previous_turn_id) throw new LearningError('stale_turn');
    if (prior?.delivery.status === 'issuing') throw new LearningError('delivery_pending');
    const hook = this.filter(req.utterance, req.emotion);
    // Profile is fetched from Shared State. Client-supplied mastery is forbidden.
    const response = new LearningDirector().plan({...req,utterance:hook.text,
      learner_state:{review_targets:state.profile.review_targets}}, prior ? {
        action:prior.response.teaching_action,
        failures:prior.response.learning_loop.failed_attempts, touched:prior.created*1000,
      } : undefined, prior?.delivery.status === 'completed');
    response.safety.input_filtered = hook.filtered;
    response.safety.injection_suspected = hook.injection_suspected;
    return jsonService(`${this.memoryUrl}/memory/learning/commit`, {
      child_id:req.child_id,session_id:req.session_id,turn_id:req.turn_id,device_id:req.device_id,
      previous_turn_id:req.previous_turn_id,revision:state.revision,request_hash,response,
    });
  }
}
