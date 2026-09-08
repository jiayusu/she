// 应用容器与调度管线:把 FR-G01~G08 与会话/审计/埋点装配到一起。
// dispatch 全链路(路由 + 注入,不含 LLM 推理)预算 ≤100ms;系统钩子在管线内强制执行。

import { EventEmitter } from 'node:events';
import { join } from 'node:path';
import {
  MINISTERS,
  MINISTER_LABEL,
  MINISTER_STORE,
  type DispatchRequest,
  type DispatchResponse,
  type Emotion,
  type IntentResult,
  type MinisterId,
  type WriteAckItem,
  type DirectRequest,
  type DirectResponse,
} from './types.ts';
import { normalizeAsr, normalizeEmotion, newId } from './util.ts';
import { IntentClassifier, makeClarifyQuestion } from './intent.ts';
import { MinisterMapTable } from './mapping.ts';
import { ContextBuilder } from './context.ts';
import { SessionManager } from './session.ts';
import { AuditLog } from './audit.ts';
import { Metrics } from './metrics.ts';
import { LocalMemoryStore, NeverForgetWhitelist, StoreRegistry } from './stores/local.ts';
import { SemanticKG } from './stores/kg.ts';
import { SalienceEngine } from './salience.ts';
import { MemoryWriteScheduler } from './memory-write.ts';
import { ConsolidationService } from './consolidation.ts';
import { JobScheduler, createConsolidateJob, createPruneJob, createReviewJob } from './metacognition.ts';
import { ToolGateway } from './hooks.ts';
import { DEFAULT_LEXICON, loadConfigs, loadJson } from './config.ts';
import type { LexiconCfg } from './intent.ts';
import { LearningDirector } from './learning-director.ts';
import { LearningEventStore } from './learning-events.ts';

export interface AppOptions {
  dataDir: string;
  configDir?: string | null;
  storeFaults?: Partial<Record<'episodic' | 'semantic' | 'affective' | 'procedural' | 'working', { failureRate?: number; failEveryNth?: number }>>;
}

export interface MinisterStatus {
  id: MinisterId;
  label: string;
  store: string;
  degraded: boolean;
  on_duty_sessions: number;
}

export class App {
  readonly bus = new EventEmitter();
  readonly metrics = new Metrics();
  readonly audit: AuditLog;
  readonly stores = new StoreRegistry();
  readonly kg: SemanticKG;
  readonly whitelist: NeverForgetWhitelist;
  readonly salience: SalienceEngine;
  readonly writeScheduler: MemoryWriteScheduler;
  readonly mapTable: MinisterMapTable;
  readonly classifier: IntentClassifier;
  readonly contextBuilder: ContextBuilder;
  readonly sessions: SessionManager;
  readonly tools: ToolGateway;
  readonly consolidation: ConsolidationService;
  readonly jobs: JobScheduler;
  readonly dataDir: string;
  readonly learningDirector = new LearningDirector();
  readonly learningEvents: LearningEventStore;

  private degraded = new Set<MinisterId>();
  private mapFile: string | null;
  private lexiconFile: string | null;
  private startedAt = Date.now();

  constructor(opts: AppOptions) {
    this.dataDir = opts.dataDir;
    const cfgs = loadConfigs(opts.configDir ?? null);
    this.mapFile = cfgs.mapFile;
    this.lexiconFile = cfgs.lexiconFile;

    this.audit = new AuditLog(opts.dataDir);
    this.learningEvents = new LearningEventStore(opts.dataDir);
    this.kg = new SemanticKG(opts.dataDir);
    this.whitelist = new NeverForgetWhitelist(opts.dataDir);

    for (const storeId of ['episodic', 'semantic', 'affective', 'procedural', 'working'] as const) {
      this.stores.register(new LocalMemoryStore(storeId, opts.dataDir, opts.storeFaults?.[storeId]));
    }

    // 显著性引擎从情景库回放"首次行为"集合,重启后不会把旧行为当首次
    const seedBehaviors = this.stores
      .get('episodic')
      .all()
      .map((m) => (typeof m.payload.behavior === 'string' ? m.payload.behavior : null))
      .filter((b): b is string => !!b);
    this.salience = new SalienceEngine(cfgs.salience, seedBehaviors);

    this.writeScheduler = new MemoryWriteScheduler(
      this.stores, this.salience, this.whitelist, this.kg, this.audit, this.metrics, this.bus, opts.dataDir,
    );
    this.mapTable = cfgs.mapTable;
    this.classifier = new IntentClassifier(cfgs.lexicon);
    this.contextBuilder = new ContextBuilder(cfgs.budgets);
    this.sessions = new SessionManager(opts.dataDir);
    this.tools = new ToolGateway(this.kg, cfgs.lexicon, this.audit, this.bus);
    this.consolidation = new ConsolidationService(this.stores, this.kg, this.metrics, this.audit, this.bus, opts.dataDir);

    this.jobs = new JobScheduler(this.bus);
    this.jobs.register(createReviewJob({
      metrics: this.metrics, audit: this.audit, whitelist: this.whitelist,
      writeScheduler: this.writeScheduler, dataDir: opts.dataDir,
    }));
    this.jobs.register(createPruneJob({ stores: this.stores, salience: this.salience, whitelist: this.whitelist }));
    this.jobs.register(createConsolidateJob({ consolidation: this.consolidation }));

    if (this.mapFile) {
      try {
        this.mapTable.watchFile(this.mapFile, (cfg) => {
          this.classifierThresholdChanged(cfg.confidence_threshold);
          this.bus.emit('map_reloaded', { version: cfg.version });
        }, (e) => this.bus.emit('map_error', { error: e.message }));
      } catch {
        // watch 失败不影响启动,可用 /admin/map/reload 手动热加载
      }
    }
  }

  private classifierThresholdChanged(_threshold: number): void {
    // 阈值在 dispatch 时从映射表实时读取,无需额外处理
  }

  get threshold(): number {
    return this.mapTable.threshold();
  }

  /** 崩溃恢复:重建全部会话(非功能要求 ≤2s)。返回恢复耗时 ms 与恢复的会话数。 */
  recover(): { restored: number; elapsed_ms: number } {
    const t0 = performance.now();
    const restored = this.sessions.rebuildAll().length;
    return { restored, elapsed_ms: performance.now() - t0 };
  }

  rebuildSession(id: string): { found: boolean } {
    const state = this.sessions.rebuild(id);
    this.audit.append({ ts: Date.now(), type: 'session_rebuild', session_id: id, detail: { found: !!state } });
    return { found: !!state };
  }

  async dispatch(req: DispatchRequest): Promise<DispatchResponse> {
    if (!req || typeof req !== 'object') throw new DispatchError('请求体必须是 JSON 对象');
    if (!req.session_id || typeof req.session_id !== 'string') throw new DispatchError('缺少 session_id');
    if (typeof req.utterance !== 'string') throw new DispatchError('缺少 utterance');

    const t0 = performance.now();
    const routeId = newId('rt_');
    const emotion = normalizeEmotion(req.emotion);
    const asr = normalizeAsr(req.asr);

    // FR-G08:系统钩子链强制执行(不受请求参数影响)
    const hookRes = this.tools.runInputHooks(req.utterance, emotion);
    const effectiveEmotion = hookRes.emotion ?? emotion;

    // FR-G01 意图分类
    const intentRes: IntentResult = this.classifier.classify({
      utterance: hookRes.text,
      emotion: effectiveEmotion,
      asr,
      threshold: this.threshold,
    });

    // FR-G02 大臣映射(+ 低置信度走小P 反问澄清)
    let minister: MinisterId;
    let fallbackUsed = false;
    let reason: string;
    let needClarify = intentRes.need_clarify;
    let clarifyQuestion: string | undefined;
    if (needClarify) {
      minister = this.mapTable.config.clarify_minister;
      reason = `置信度 ${intentRes.confidence.toFixed(2)} 低于阈值 ${this.threshold},转小P反问澄清`;
      clarifyQuestion = makeClarifyQuestion(intentRes.top2);
    } else {
      const resolved = this.mapTable.resolve(intentRes.intent, { degraded: this.degraded });
      minister = resolved.minister;
      fallbackUsed = resolved.fallback_used;
      reason = resolved.reason;
    }

    // FR-G03 上下文注入包(反映本次消息之前的状态)
    const session = this.sessions.get(req.session_id);
    this.sessions.rolloverDayIfNeeded(req.session_id);
    const safetyNotes: string[] = [];
    if (hookRes.injection_suspected) safetyNotes.push('输入疑似提示词注入,已标记安全态,大臣回答需走内容过滤');
    if (hookRes.filtered) safetyNotes.push('输入已过内容过滤');
    const ctxRes = this.contextBuilder.build(session, needClarify ? 'chitchat' : intentRes.intent, {
      needClarify,
      safetyNotes,
      minister,
    });
    if (needClarify) ctxRes.bundle.notes.push('小P反问澄清:禁止编造记忆,只做意图确认');

    // FR-G04 记忆写调度
    let acks: WriteAckItem[] = [];
    if (Array.isArray(req.memory_write) && req.memory_write.length > 0) {
      acks = await this.writeScheduler.submit(req.memory_write, {
        emotion: effectiveEmotion,
        session_id: req.session_id,
      });
      // acks 与入参 entries 按提交顺序一一对应
      acks.forEach((ack, i) => {
        const entry = req.memory_write![i]!;
        if (ack.ok && entry.kind === 'word_learned' && typeof entry.payload.word === 'string') {
          this.sessions.addTodayWord(req.session_id, entry.payload.word);
        }
      });
    }

    // 会话状态更新(切换大臣 / 对话轮 / 剧本状态 / 情绪)
    const prevMinister = session.minister_on_duty;
    this.sessions.setMinister(req.session_id, minister);
    this.sessions.setEmotion(req.session_id, effectiveEmotion);
    this.sessions.mergeScriptState(req.session_id, req.script_state);
    this.sessions.appendTurn(req.session_id, {
      ts: Date.now(),
      role: 'child',
      text: req.utterance,
      intent: intentRes.intent,
      minister,
    });
    let outputFiltered = false;
    if (typeof req.assistant_reply === 'string' && req.assistant_reply.length > 0) {
      const out = this.tools.runOutputHooks(req.assistant_reply); // FR-G08 输出强制过滤
      outputFiltered = out.filtered;
      this.sessions.appendTurn(req.session_id, {
        ts: Date.now(),
        role: 'minister',
        minister,
        text: out.text,
      });
    }
    if (prevMinister !== minister) {
      this.bus.emit('minister_change', {
        session_id: req.session_id,
        from: prevMinister,
        to: minister,
        intent: intentRes.intent,
        route_id: routeId,
      });
    }

    const latencyMs = performance.now() - t0;

    // 埋点(§8)
    this.metrics.routeDone(intentRes.intent, minister, intentRes.confidence);
    this.metrics.ctxBuilt(ctxRes.bundle.tokens_used, ctxRes.bundle.budget);
    this.metrics.observe('route_latency_ms', latencyMs);
    this.metrics.observe('ctx_build_ms', ctxRes.elapsed_ms);

    // 审计:路由理由 / 注入内容摘要 / 写库结果
    this.audit.append({
      ts: Date.now(),
      type: 'dispatch',
      route_id: routeId,
      session_id: req.session_id,
      route: {
        intent: intentRes.intent,
        minister,
        confidence: intentRes.confidence,
        reason,
        fallback_used: fallbackUsed,
        need_clarify: needClarify,
      },
      ctx_summary: {
        budget: ctxRes.bundle.budget,
        tokens_used: ctxRes.bundle.tokens_used,
        turns: ctxRes.bundle.recent_turns.length,
        today_words: ctxRes.bundle.today_words.length,
        notes: ctxRes.bundle.notes,
      },
      write_results: acks.map((a) => ({
        id: a.id, store: a.store, ok: a.ok, attempts: a.attempts,
        dead_letter: a.dead_letter, pending_review: a.pending_review,
      })),
      detail: { latency_ms: latencyMs, safety: { injection: hookRes.injection_suspected, input_filtered: hookRes.filtered, output_filtered: outputFiltered } },
    });

    this.bus.emit('dispatch_done', {
      session_id: req.session_id,
      intent: intentRes.intent,
      minister,
      confidence: intentRes.confidence,
      latency_ms: latencyMs,
      route_id: routeId,
    });

    return {
      route_id: routeId,
      session_id: req.session_id,
      intent: intentRes.intent,
      confidence: intentRes.confidence,
      need_clarify: needClarify,
      clarify_question: clarifyQuestion,
      minister,
      minister_label: MINISTER_LABEL[minister],
      fallback_used: fallbackUsed,
      route_reason: reason,
      ctx_bundle: ctxRes.bundle,
      memory_write_ack: acks,
      latency_ms: latencyMs,
      safety: {
        input_filtered: hookRes.filtered,
        injection_suspected: hookRes.injection_suspected,
        output_filtered: outputFiltered,
      },
    };
  }

  /** New learning-first decision API. It never selects or exposes a minister. */
  direct(req: DirectRequest): DirectResponse {
    if (!req || typeof req !== 'object' || typeof req.session_id !== 'string' || !req.session_id) {
      throw new DispatchError('缺少 session_id');
    }
    if (typeof req.utterance !== 'string') throw new DispatchError('缺少 utterance');
    const hook = this.tools.runInputHooks(req.utterance, normalizeEmotion(req.emotion));
    const response = this.learningDirector.direct({ ...req, utterance: hook.text });
    const event = this.learningEvents.record({ ...req, utterance: hook.text }, response);
    response.learning_event_id = event.event_id;
    response.evidence_status = event.evidence_status;
    response.teaching_action.memory_policy = event.event_kind === 'confirmed_mastery' ? 'confirmed' : event.event_kind === 'candidate_evidence' ? 'candidate' : 'no_write';
    response.safety.input_filtered = hook.filtered;
    response.safety.injection_suspected = hook.injection_suspected;
    return response;
  }

  // ---- 运维 ----

  listMinisters(): MinisterStatus[] {
    return MINISTERS.map((id) => ({
      id,
      label: MINISTER_LABEL[id],
      store: MINISTER_STORE[id],
      degraded: this.degraded.has(id),
      on_duty_sessions: this.sessions.list().filter((s) => s.minister_on_duty === id).length,
    }));
  }

  setDegraded(id: MinisterId, on: boolean): void {
    if (on) this.degraded.add(id);
    else this.degraded.delete(id);
  }

  async reloadMap(): Promise<{ version: number; source: string }> {
    const cfg = this.mapTable.reload(this.mapFile ?? undefined);
    this.audit.append({ ts: Date.now(), type: 'map_reload', detail: { version: cfg.version, source: this.mapFile ?? 'default' } });
    this.bus.emit('map_reloaded', { version: cfg.version });
    return { version: cfg.version, source: this.mapFile ?? 'default' };
  }

  reloadLexicon(): void {
    if (!this.lexiconFile) return;
    const cfg = loadJson<LexiconCfg>(this.lexiconFile, DEFAULT_LEXICON);
    this.classifier.reload(cfg);
    this.tools.reloadLexicon(cfg);
  }

  stats(): { uptime_ms: number; sessions: number; dlq_open: number; whitelist: number } {
    return {
      uptime_ms: Date.now() - this.startedAt,
      sessions: this.sessions.list().length,
      dlq_open: this.writeScheduler.openDlqCount(),
      whitelist: this.whitelist.list().length,
    };
  }

  shutdown(): void {
    this.sessions.flushSync();
    this.jobs.stop();
    this.mapTable.stopWatch();
  }
}

export class DispatchError extends Error {
  status = 400;
}

export { join };
