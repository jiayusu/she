import type { DeviceSessionRegistry } from './device-sessions.js';
import type { DeviceEvent } from './types.js';

export class ServiceError extends Error {
  constructor(message: string, readonly status=503) { super(message); }
}
export async function service(url: string, body?: unknown): Promise<any> {
  let response: Response;
  const init: RequestInit = {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'content-type': 'application/json' },
    signal: AbortSignal.timeout(3000),
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  try { response = await fetch(url, init); }
  catch { throw new ServiceError('learning_service_unavailable'); }
  const value = await response.json() as any;
  if (!response.ok) throw new ServiceError(typeof value.error==='string'?value.error:value.error?.code ?? 'learning_service_error',response.status);
  return value;
}
export class LearningDelivery {
  constructor(private memory: string, private interaction: string, private sessions: DeviceSessionRegistry) {}
  async deliver(b: Record<string,unknown>): Promise<unknown> {
    if (Object.keys(b).some(k=>!['child_id','session_id','turn_id'].includes(k))) throw new ServiceError('invalid_delivery',400);
    for (const key of ['child_id','session_id','turn_id']) if (typeof b[key]!=='string' || !/^[A-Za-z0-9_-]{1,80}$/.test(b[key] as string)) throw new ServiceError('invalid_identity',400);
    const state = await service(`${this.memory}/memory/learning/state?${new URLSearchParams(b as Record<string,string>)}`);
    const turn = state.replay;
    if (!turn || state.latest.turn_id !== b.turn_id) throw new ServiceError('stale_turn',409);
    if (turn.delivery.status !== 'planned') return turn.delivery;
    const session = this.sessions.snapshot(turn.device_id);
    if (!session?.online) throw new ServiceError('device_offline',409);
    // Interaction owns wording and invokes its existing output safety filter.
    const rendered = await service(`${this.interaction}/interaction/render`, turn.response.teaching_action);
    const claim = await service(`${this.memory}/memory/learning/claim`, {...b,device_session:session.sessionId});
    if (!claim.claimed) return claim;
    try {
      if (this.sessions.snapshot(turn.device_id)?.sessionId !== session.sessionId) throw new Error('session_changed');
      this.sessions.sendCommand(turn.device_id,{commandId:claim.command_id,type:'speak',payload:{text:rendered.text}});
    } catch {
      await service(`${this.memory}/memory/learning/ack`,{command_id:claim.command_id,device_id:turn.device_id,device_session:session.sessionId,status:'failed'});
      throw new ServiceError('delivery_failed',409);
    }
    return {command_id:claim.command_id,status:'issuing'};
  }
  async acknowledge(event: DeviceEvent): Promise<void> {
    if(event.type !== 'command_ack') return;
    // Bounded retries, retaining only metadata. Ambiguous/lost ACK fails closed.
    for(let attempt=0;attempt<3;attempt++) {
      try {
        await service(`${this.memory}/memory/learning/ack`,{command_id:event.payload.command_id,
          device_id:event.device_id,device_session:event.session_id,status:event.payload.status});
        return;
      } catch(error) {
        if(error instanceof ServiceError && error.status < 500) return;
      }
    }
  }
}
