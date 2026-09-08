import type { DirectRequest, StoryProposal } from './types.ts';

export class StoryWorldAgent {
  propose(req: DirectRequest, target: string, goal: string, distressed: boolean): StoryProposal {
    const token = target.replace(/[^A-Za-z ]/g, '').trim().split(/\s+/).at(-1) ?? 'words';
    return {
      story_action: distressed ? 'pause_and_offer_comfort' : `world_waits_for_${token.toLowerCase()}`,
      world_role: '小P',
      success_feedback: `The world heard “${target.replace(/\.$/, '')}”!`,
      state_patch: { ...(req.story_state ?? {}), objective: goal, scene: req.detected_object ?? 'home' },
    };
  }
}
