import { createHash, randomUUID } from 'node:crypto';
import { loadStorySeed, type StoryNode, type StorySeed } from './story-seed.ts';
import { emptySpeechEvidence, resolveSpeechAct } from './speech-act.ts';
import type {
  DirectRequest,
  RpgDecision,
  RpgInputKind,
  RpgObject,
  RpgWorldEvent,
  ScaffoldLevel,
  TeachingAction,
} from './types.ts';

const RPG_OBJECTS = new Set(['fridge', 'table', 'red_cup', 'blue_cup']);

export interface RpgPrior {
  action: TeachingAction;
  rpg?: RpgDecision;
  failures: number;
}

export interface RpgInspection {
  seed: StorySeed;
  inputKind: RpgInputKind;
  currentNode: StoryNode;
  priorRpg: RpgDecision | null;
  sourceTurnId: string;
  speech: boolean;
  uncertain: boolean;
  questSatisfied: boolean;
  evidence: RpgDecision['speech_act_evidence'];
  failures: number;
  objectMatched: boolean;
  observedObject: RpgObject | null;
}

export interface RpgResolution {
  rpg: RpgDecision;
  node: StoryNode;
  actionKind: TeachingAction['teaching_action'];
  promptId?: string;
  feedbackId: string;
  storyAction: string;
}

function inputKind(req: DirectRequest): RpgInputKind {
  if (req.input_kind) return req.input_kind;
  if (req.utterance.trim()) return 'speech';
  return req.detected_object ? 'object_observed' : 'resume';
}

function boundedConfidence(req: DirectRequest): number {
  const value = typeof req.asr === 'number' ? req.asr : Number(req.asr?.conf ?? 0);
  return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
}

function stableId(prefix: string, ...parts: unknown[]): string {
  const value = parts.filter(part => part !== undefined && part !== null).join('\0');
  if (!value) return `${prefix}_${randomUUID()}`;
  const digest = createHash('sha256').update(value).digest('hex').slice(0, 20);
  return `${prefix}_${digest}`;
}

function node(seed: StorySeed, nodeId: string): StoryNode {
  const result = seed.nodes.find(candidate => candidate.node_id === nodeId);
  if (!result) throw new Error('invalid_rpg_node');
  return result;
}

function promptFor(storyNode: StoryNode, scaffold: ScaffoldLevel): string {
  return storyNode.prompts.find(prompt => prompt.scaffold_level === scaffold)?.prompt_id
    ?? storyNode.prompts.find(prompt => prompt.scaffold_level === 6)!.prompt_id;
}

export class EmbodiedRpg {
  readonly seed: StorySeed;

  constructor(seed = loadStorySeed()) {
    this.seed = seed;
  }

  applies(req: DirectRequest, prior?: RpgPrior): boolean {
    return !!req.input_kind || !!prior?.rpg || RPG_OBJECTS.has(req.detected_object ?? '');
  }

  inspect(req: DirectRequest, prior: RpgPrior | undefined, executionConfirmed: boolean,
          distressed: boolean): RpgInspection {
    const kind = inputKind(req);
    const priorRpg = prior?.rpg ?? null;
    const currentNode = node(this.seed, priorRpg?.node_id ?? this.seed.start_node_id);
    const sourceTurnId = req.turn_id ?? stableId('turn', req.session_id, req.utterance,
      req.perception_event_id, currentNode.node_id);
    const speech = kind === 'speech';
    const confidence = boundedConfidence(req);
    const uncertain = speech && confidence < 0.8;
    const confirmedObject = priorRpg?.confirmed_object;
    const objectContextReady = (priorRpg?.phase === 'presenting'
      || priorRpg?.phase === 'awaiting_speech')
      && confirmedObject !== null
      && confirmedObject !== undefined
      && currentNode.required_objects.includes(confirmedObject);
    // A legacy prompt cannot elicit an RPG transition: the prior reviewed RPG
    // action, confirmed object context, and its delivery record are all required.
    const canResolve = speech && objectContextReady && !!currentNode.criterion && !distressed;
    const evidence = canResolve
      ? resolveSpeechAct({
          utterance: req.utterance,
          asrConfidence: confidence,
          criterion: currentNode.criterion!,
          sourceTurnId,
          elicitingActionId: prior.action.action_id ?? 'legacy_action',
          elicitingPromptId: prior.action.prompt_id ?? priorRpg?.feedback_id ?? null,
          scaffoldLevel: prior.action.scaffold_level,
          executionConfirmed,
        })
      : emptySpeechEvidence({
          sourceTurnId,
          elicitingActionId: priorRpg ? prior?.action.action_id ?? 'legacy_action' : 'no_action',
          criterionId: currentNode.criterion?.criterion_id ?? 'none.v1',
          scaffoldLevel: priorRpg ? prior?.action.scaffold_level ?? 2 : 2,
          errorType: speech ? 'no_completed_prompt' : 'unmatched',
        });
    const questSatisfied = evidence.quest_satisfied;
    const failedSpeech = canResolve && executionConfirmed && !uncertain && !questSatisfied;
    const failures = questSatisfied
      ? 0
      : failedSpeech
        ? Math.min(2, (priorRpg ? prior?.failures ?? 0 : 0) + 1)
        : kind === 'resume'
          ? 0
          : (priorRpg ? prior?.failures ?? 0 : 0);
    return {
      seed: this.seed,
      inputKind: kind,
      currentNode,
      priorRpg,
      sourceTurnId,
      speech,
      uncertain,
      questSatisfied,
      evidence,
      failures,
      objectMatched: kind === 'object_observed'
        && currentNode.required_objects.includes(req.detected_object ?? ''),
      observedObject: kind === 'object_observed' && RPG_OBJECTS.has(req.detected_object ?? '')
        ? req.detected_object as RpgObject
        : null,
    };
  }

  resolve(inspection: RpgInspection, scaffold: ScaffoldLevel, distressed: boolean): RpgResolution {
    const { seed, currentNode, priorRpg, sourceTurnId, evidence } = inspection;
    let worldRevision = priorRpg?.world_revision ?? 1;
    let inventory = [...(priorRpg?.inventory ?? [])];
    let completedNodes = [...(priorRpg?.completed_nodes ?? [])];
    let confirmedObject = priorRpg?.confirmed_object ?? null;
    let outputNode = currentNode;
    let phase: RpgDecision['phase'];
    let feedbackId: string;
    let actionKind: TeachingAction['teaching_action'];
    let promptId: string | undefined;
    const worldEvents: RpgWorldEvent[] = [];

    if (inspection.inputKind === 'object_observed') {
      confirmedObject = inspection.objectMatched ? inspection.observedObject : null;
    }

    if (priorRpg?.phase === 'completed' || currentNode.terminal) {
      phase = 'completed';
      feedbackId = currentNode.success_feedback_id;
      actionKind = 'pause';
    } else if (distressed || inspection.failures >= 2) {
      phase = 'paused';
      feedbackId = currentNode.failure_feedback_id;
      actionKind = 'pause';
    } else if (inspection.questSatisfied) {
      const nextNode = node(seed, currentNode.next_node_id);
      const grantEvent: RpgWorldEvent = {
        event_id: stableId('we', sourceTurnId, currentNode.node_id, worldRevision, 'grant'),
        kind: 'virtual_item_granted',
        base_revision: worldRevision,
        resulting_revision: worldRevision + 1,
        source_evidence_id: evidence.evidence_id,
        from_node_id: currentNode.node_id,
        to_node_id: nextNode.node_id,
        item_id: currentNode.success_event.item_id as 'milk_token' | 'red_cup_token',
      };
      worldEvents.push(grantEvent);
      worldRevision += 1;
      if (!inventory.includes(grantEvent.item_id!)) inventory.push(grantEvent.item_id!);
      if (!completedNodes.includes(currentNode.node_id as never))
        completedNodes.push(currentNode.node_id as never);
      outputNode = nextNode;
      confirmedObject = null;
      feedbackId = currentNode.success_feedback_id;
      actionKind = 'advance_story';
      if (nextNode.terminal) {
        const completionEvent: RpgWorldEvent = {
          event_id: stableId('we', sourceTurnId, nextNode.node_id, worldRevision, 'complete'),
          kind: 'quest_completed',
          base_revision: worldRevision,
          resulting_revision: worldRevision + 1,
          source_evidence_id: evidence.evidence_id,
          from_node_id: nextNode.node_id,
          to_node_id: nextNode.node_id,
          quest_id: 'milk_picnic',
        };
        worldEvents.push(completionEvent);
        worldRevision += 1;
        if (!completedNodes.includes(nextNode.node_id as never))
          completedNodes.push(nextNode.node_id as never);
        phase = 'completed';
      } else {
        phase = 'seeking_object';
      }
    } else if (inspection.inputKind === 'object_observed') {
      if (inspection.objectMatched) {
        phase = 'presenting';
        promptId = promptFor(currentNode, scaffold);
        feedbackId = promptId;
        actionKind = 'ask';
      } else {
        phase = reqPhaseForMissingObject(inspection);
        feedbackId = currentNode.failure_feedback_id;
        actionKind = 'explore';
      }
    } else if (inspection.inputKind === 'resume') {
      const canReplayPrompt = priorRpg?.phase === 'paused'
        || priorRpg?.phase === 'presenting'
        || priorRpg?.phase === 'awaiting_speech';
      const hasRequiredObject = confirmedObject !== null
        && currentNode.required_objects.includes(confirmedObject);
      if (canReplayPrompt && hasRequiredObject) {
        phase = 'presenting';
        promptId = promptFor(currentNode, scaffold);
        feedbackId = promptId;
        actionKind = 'ask';
      } else {
        phase = priorRpg?.phase === 'confirming_object'
          ? 'confirming_object'
          : 'seeking_object';
        feedbackId = currentNode.failure_feedback_id;
        actionKind = 'explore';
      }
    } else if (inspection.speech
      && (confirmedObject === null
        || !currentNode.required_objects.includes(confirmedObject))) {
      // Speech cannot skip the embodied part of the quest. Until a required
      // object has been observed, keep looking and do not issue a language prompt.
      phase = priorRpg?.phase === 'confirming_object'
        ? 'confirming_object'
        : 'seeking_object';
      feedbackId = currentNode.failure_feedback_id;
      actionKind = 'explore';
    } else if (inspection.uncertain || evidence.error_type === 'no_completed_prompt') {
      phase = 'presenting';
      promptId = promptFor(currentNode, scaffold);
      feedbackId = promptId;
      actionKind = 'reinvite';
    } else {
      phase = 'presenting';
      promptId = promptFor(currentNode, scaffold);
      feedbackId = promptId;
      actionKind = 'prompt';
    }

    const rpg: RpgDecision = {
      contract_version: '1.0',
      seed_id: 'milk_picnic',
      seed_version: 1,
      node_id: outputNode.node_id as RpgDecision['node_id'],
      phase,
      world_revision: worldRevision,
      inventory,
      completed_nodes: completedNodes,
      confirmed_object: confirmedObject,
      world_role: outputNode.world_role,
      feedback_id: feedbackId,
      next_quest_id: phase === 'completed' ? null : outputNode.node_id as Exclude<RpgDecision['next_quest_id'], null>,
      speech_act_evidence: evidence,
      world_events: worldEvents,
    };
    return { rpg, node: outputNode, actionKind, promptId, feedbackId,
      storyAction: `rpg:${feedbackId}` };
  }
}

function reqPhaseForMissingObject(inspection: RpgInspection): RpgDecision['phase'] {
  return inspection.priorRpg ? 'confirming_object' : 'seeking_object';
}

export function actionId(req: DirectRequest): string {
  return req.turn_id ? `action_${req.turn_id}` : `action_${randomUUID()}`;
}
