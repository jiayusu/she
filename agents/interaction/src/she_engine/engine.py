"""Engine —— LLM 剧情引擎主编排（PRD 01）。

一次 handle_turn 的完整链路::

    入参(PRD §6) → 卡壳判定(FR-E09) → 路由(FR-E02) → Recast指令(FR-E04)
      → 上下文注入(FR-E08) → KG事实(万物) → 人格渲染(FR-E01) → LLM
      → Schema解析(失败重试1次, FR-E06) → 级别收敛(FR-E05) → 安全过滤(05)
      → 兜底模板(FR-E07) → 状态机推进+持久化(FR-E03) → memory_write 落库(04)
      → 埋点(PRD §8) → 出参 {speaker,text,emotion_tag,memory_write[]}

铁律：**任何输入、任何故障（LLM挂/解析烂/安全拦）都必有非空回应**（拔网线 100%）。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .context import ContextBlock, build_ctx_block
from .events import EventBus, EventSink, InMemorySink
from .levels import fit_text_to_level, get_level_rules
from .llm import CachedProvider, LLMProvider
from .memory import InMemoryStore, MemoryStore
from .prompts import MinisterRegistry, MinisterSpec
from .recast import RecastDirective, build_recast_directive, detect_error_pointing, template_recast
from .router import (
    INTENT_EMOTION_COMFORT,
    INTENT_THINGS,
    INTENT_WORD_LEARNING,
    CHITCHAT_STATE_MINISTER,
    INTENT_MINISTER,
    Router,
)
from .safety import LocalSafetyFilter, SafetyFilter
from .schema import SCHEMA_INSTRUCTION, parse_llm_output, repair_user_prompt
from .state_machine import (
    ScriptState,
    day_seed,
    plan_tasks,
    STATE_ADVENTURE,
    STATE_BEDTIME,
    STATE_DAY_ENDED,
    STATE_MORNING_COURT,
)
from .stuck import StuckTracker
from .templates import TemplateLibrary
from .types import (
    AssessResult,
    MemoryWrite,
    TurnRequest,
    TurnResponse,
)

# 意图 → 兜底模板场景
_FALLBACK_SCENE_BY_INTENT = {
    INTENT_THINGS: "things",
    INTENT_EMOTION_COMFORT: "comfort",
    INTENT_WORD_LEARNING: "learn",
}
_STATE_FALLBACK_SCENE = {
    STATE_MORNING_COURT: "court",
    STATE_ADVENTURE: "adventure",
    STATE_BEDTIME: "bedtime",
    STATE_DAY_ENDED: "bedtime",
}

_DEFAULT_INVITE_WORD = "apple"


@dataclass
class EngineConfig:
    """组装点：所有外部依赖（LLM/记忆/安全/埋点/路由模型/KG）从这里注入。"""

    provider: LLMProvider
    assets_dir: str = field(default_factory=lambda: os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "assets")))
    memory: Optional[MemoryStore] = None
    safety: Optional[SafetyFilter] = None
    event_sink: Optional[EventSink] = None
    classifier: Optional[Any] = None            # 传给 Router；None 用纯规则
    prompt_versions: Optional[Dict[str, int]] = None   # pin 任意历史版本（可回滚）
    kg_lookup: Optional[Callable[[str], List[str]]] = None  # kb 模块 kg.facts
    session_level: int = 1                      # 会话初始级别 L0-L5
    follow_request_level: bool = False          # True 时上游 level 覆盖会话级别
    session_cost_budget_yuan: float = 0.02      # 非功能：LLM 成本 ≤0.02 元/会话
    use_cache: bool = True                      # 精确 prompt 缓存（压成本/延迟）
    route_overrides: Optional[Dict[str, str]] = None  # FR-E10：意图→大臣改配（DLC 接管）


class Engine:
    """一个 Engine 实例 = 一台设备上的一个孩子会话（状态在实例内 + 记忆存储持久化）。"""

    def __init__(self, config: EngineConfig) -> None:
        self._cfg = config
        self._bus = EventBus(config.event_sink if config.event_sink is not None else InMemorySink())
        self._registry = MinisterRegistry(os.path.join(config.assets_dir, "ministers"))
        for mid, ver in (config.prompt_versions or {}).items():
            self._registry.pin(mid, ver)
        self._templates = TemplateLibrary()
        self._templates.load_dir(os.path.join(config.assets_dir, "templates"))
        self._router = Router(config.classifier)
        self._safety = config.safety or LocalSafetyFilter()
        self._memory = config.memory or InMemoryStore()
        self._provider: LLMProvider = (
            CachedProvider(config.provider) if config.use_cache else config.provider
        )

        # ---- 会话状态 ------------------------------------------------------
        self._level = max(0, min(5, int(config.session_level)))
        self._scaffold_level = 0
        self._level_locked = False
        self._stuck = StuckTracker(self._level)
        self._session_cost_yuan = 0.0
        self._cost_warned = False
        self._recap_pending: str = ""

        # ---- 剧本状态恢复（FR-E03 跨天续剧情） ------------------------------
        raw_state = self._memory.load_script_state()
        self._state = ScriptState.from_dict(raw_state)
        recap = self._state.resume_for_today()   # 关机重开 → 接续"昨天讲到哪"
        if recap:
            self._recap_pending = recap
        if not self._state.tasks_planned:
            self._state.tasks_planned = plan_tasks(day_seed(self._state.date))
        self._persist_state()

    # ------------------------------------------------------------------ 公共 API
    @property
    def events(self) -> EventBus:
        return self._bus

    @property
    def script_state(self) -> ScriptState:
        return self._state

    @property
    def level(self) -> int:
        return self._level

    @property
    def scaffold_level(self) -> int:
        """Current output support level (S0-S6), separate from language level."""
        return self._scaffold_level

    @property
    def registry(self) -> MinisterRegistry:
        return self._registry

    def turn(self, request: Dict[str, Any] | TurnRequest) -> TurnResponse:
        """PRD §6 in → out。dict 或 TurnRequest 均可；返回 .to_dict() 为严格 Schema。"""
        req = request if isinstance(request, TurnRequest) else TurnRequest.from_dict(request)
        return self.handle_turn(req)

    # ------------------------------------------------------------------ 主链路
    def handle_turn(self, req: TurnRequest) -> TurnResponse:
        t0 = time.perf_counter()

        # 跨天检查（长驻进程过午夜也能正确开新一天）
        recap_now = self._state.resume_for_today()
        if recap_now:
            self._recap_pending = recap_now

        requested_language = req.language_level if req.language_level is not None else req.level
        explicit_scaffold = req.scaffold_level is not None
        if self._cfg.follow_request_level and requested_language:
            self._level = max(0, min(5, int(requested_language)))
            self._stuck.level = self._level
        if explicit_scaffold:
            self._scaffold_level = max(0, min(6, int(req.scaffold_level or 0)))

        utterance = (req.child_utterance or req.asr_result.text or "").strip()

        # ---- 卡壳 / 沉默（不推进剧情，走小P重邀，FR-E09 + 用户故事2） ----------
        if not utterance:
            verdict = self._stuck.observe("")
            self._bus.stuck(verdict.streak, self._level, verdict.downgraded)
            if verdict.downgraded:
                if explicit_scaffold:
                    self._scaffold_level = min(6, self._scaffold_level + 1)
                else:
                    self._level = verdict.new_level
                    self._level_locked = True   # legacy adapter behavior
            return self._invite_turn(req, t0, reason="silence",
                                     parent_note=self._stuck.parent_note(verdict))

        verdict = self._stuck.observe(
            utterance,
            asr_confidence=req.asr_result.confidence if req.asr_result.confidence else -1.0,
            assess_passed=(not req.assess_result.has_error) if req.assess_result else True,
        )
        if verdict.downgraded:
            if explicit_scaffold:
                self._scaffold_level = min(6, self._scaffold_level + 1)
            else:
                self._level = verdict.new_level
        self._bus.stuck(verdict.streak, self._level, verdict.downgraded)
        if verdict.stuck:
            return self._invite_turn(req, t0, reason=verdict.reason,
                                     parent_note=self._stuck.parent_note(verdict))

        # 实质开口：会话级别策略。engine-owned（默认）：只在首轮采纳上游 level，
        # 之后由引擎管理（FR-E09 降级不被上游陈旧值顶回）；follow_request_level=True
        # 时上游完全主导。
        if self._cfg.follow_request_level:
            self._level = max(0, min(5, int(requested_language)))
        elif not self._level_locked and requested_language:
            self._level = max(0, min(5, int(requested_language)))
            self._level_locked = True
        self._stuck.level = self._level

        # ---- 路由（FR-E02） --------------------------------------------------
        state_name = self._state.state
        assess_present = bool(req.assess_result and (req.assess_result.has_error or req.assess_result.word))
        decision = self._router.route(
            utterance, route_intent=req.route_intent, script_state=state_name,
            assess_present=assess_present,
        )
        if self._cfg.route_overrides and decision.intent in self._cfg.route_overrides:
            decision = decision.__class__(
                decision.intent, self._cfg.route_overrides[decision.intent],
                decision.confidence, decision.matched + ("override",), by="override",
            )
        self._bus.routed(decision.intent, decision.minister, decision.confidence)

        # ---- Recast 决策（FR-E04） ------------------------------------------
        recast_directive = build_recast_directive(req.assess_result if assess_present else None)
        if recast_directive:
            self._bus.recast(assess_used=True, error_type=req.assess_result.error_type)
        else:
            self._bus.recast(assess_used=bool(req.assess_result))

        # ---- 剧本推进（开口是唯一推进条件，FR-E03） ---------------------------
        state_events: Dict[str, Any] = self._state.advance(
            task_hit=req.assess_result.word or ""
        )
        self._persist_state()

        # ---- 上下文（FR-E08） ------------------------------------------------
        ctx = self._build_context(req, decision, recast_directive)

        # ---- 人格 + LLM（FR-E01/E06） ----------------------------------------
        spec = self._registry.get(decision.minister)
        response, meta = self._generate(
            spec=spec, req=req, decision=decision, ctx=ctx,
            recast=recast_directive, t0=t0,
        )
        if response is None:
            # LLM 两次尝试全败 → 模板兜底（FR-E07，拔网线仍 100% 回应）
            response = self._template_fallback_after_llm_failure(
                decision.minister, decision.intent, req)
            meta["fallback_used"] = True
            meta["template_id"] = response.meta.get("template_id")

        # ---- 后置：级别收敛（FR-E05） ----------------------------------------
        fit_ok = True
        if response:
            fixed, trimmed = fit_text_to_level(response.text, self._level)
            if trimmed:
                response.text = fixed
                fit_ok = False

        # ---- 安全过滤（05 模块挂钩） -----------------------------------------
        final = self._safe_or_template(response, minister=decision.minister, intent=decision.intent,
                                       req=req, mode="recast" if recast_directive else "normal")

        # ---- 记忆写入（04 模块接口） -----------------------------------------
        writes = self._collect_writes(response, req, state_events, decision, parent_note=None)
        self._memory.write_memory(writes)
        self._memory.append_turn("child", utterance)
        self._memory.append_turn(final.speaker, final.text)
        final.memory_write = writes

        # ---- 埋点 + 成本 -----------------------------------------------------
        total_ms = (time.perf_counter() - t0) * 1000
        self._bus.latency(meta.get("ttft_ms", 0.0), total_ms)
        self._check_cost()

        final.meta.update({
            "intent": decision.intent,
            "minister": final.speaker,
            "minister_version": spec.version,
            "voice_id": spec.voice_id,
            "light_color": spec.light_color,
            "mode": "recast" if recast_directive else "normal",
            "level": self._level,
            "fallback_used": meta.get("fallback_used", False)
                             or response.meta.get("fallback_used", False),
            "template_id": response.meta.get("template_id") or meta.get("template_id"),
            "ctx_tokens": ctx.stats.tokens,
            "state": self._state.to_dict(),
            "route_by": decision.by,
            "schema_repaired": meta.get("repaired", False),
            "level_fit": fit_ok,
            "latency_ms": {"ttft": round(meta.get("ttft_ms", 0.0), 1), "total": round(total_ms, 1)},
            "session_cost_yuan": round(self._session_cost_yuan, 5),
            "recap": self._recap_pending or None,
        })
        self._recap_pending = ""   # recap 只注入一次
        return final

    # ------------------------------------------------------------------ 沉默/卡壳重邀
    def handle_silence(self, invite_word: str = "") -> TurnResponse:
        """孩子 10 秒没说话：小P 用更低一级句式重邀（用户故事 2）。

        静默同样计入 FR-E09 连续卡壳；连续 2 次自动降级并写 parent_note。
        """
        verdict = self._stuck.observe("")
        self._bus.stuck(verdict.streak, self._level, verdict.downgraded)
        if verdict.downgraded:
            self._level = verdict.new_level
            self._level_locked = True
        return self._invite_turn(
            TurnRequest(child_utterance=""), time.perf_counter(),
            reason="silence_timeout", invite_word=invite_word,
            parent_note=self._stuck.parent_note(verdict),
        )

    def _invite_turn(self, req: TurnRequest, t0: float, reason: str,
                     parent_note=None, invite_word: str = "") -> TurnResponse:
        minister_id = "xiaop"
        spec = self._registry.get(minister_id)
        word = (invite_word or req.assess_result.word
                or (self._state.tasks_planned[self._state.tasks_done]
                    if self._state.tasks_done < len(self._state.tasks_planned) else "")
                or _DEFAULT_INVITE_WORD)

        # 小P人格 + 降级后的级别，渲染一条重邀（走 LLM，挂了用 invite 模板）
        level_rules = get_level_rules(self._level).to_prompt()
        scene = self._state.scene_directive()
        system = spec.render_system(level_rules, scene, output_format=SCHEMA_INSTRUCTION)
        user = self._meta_line({
            "minister": minister_id, "mode": "invite", "level": self._level,
            "child_utterance": "", "invite_word": word, "emotion_hint": "gentle",
            "scene": self._state.state,
        }) + f"\nThe child has been silent. Re-invite with the word '{word}' at a LOWER level than before."
        response, meta = self._complete_with_retry(system, user, minister_id,
                                                   recast_assess=None)
        if response is None:
            tpl = self._templates.pick(minister_id, "invite", word=word)
            fallback = tpl.render(word=word) if tpl else f"Say with me — {word}."
            response = TurnResponse(speaker=minister_id, text=fallback, emotion_tag="gentle")
            meta["fallback_used"], meta["template_id"] = True, (tpl.id if tpl else None)
            self._bus.fallback(template_hit=True, minister=minister_id, scene="invite")

        fixed, _ = fit_text_to_level(response.text, max(0, self._level))
        response.text = fixed
        final = self._safe_or_template(response, minister=minister_id, intent="", req=req,
                                       mode="invite")

        writes: List[MemoryWrite] = []
        if parent_note:
            writes.append(MemoryWrite(*parent_note))
        self._memory.write_memory(writes)
        self._memory.append_turn("child", "(silence)")
        self._memory.append_turn(final.speaker, final.text)
        final.memory_write = writes

        total_ms = (time.perf_counter() - t0) * 1000
        self._bus.latency(meta.get("ttft_ms", 0.0), total_ms)
        self._check_cost()
        final.meta.update({
            "intent": "reinvite", "minister": minister_id, "mode": "invite",
            "level": self._level, "stuck_reason": reason,
            "invite_word": word, "fallback_used": meta.get("fallback_used", False),
            "template_id": meta.get("template_id"),
            "latency_ms": {"ttft": round(meta.get("ttft_ms", 0.0), 1), "total": round(total_ms, 1)},
            "state": self._state.to_dict(),
            "session_cost_yuan": round(self._session_cost_yuan, 5),
        })
        self._recap_pending = ""
        return final

    # ------------------------------------------------------------------ 生成与重试
    def _generate(self, spec: MinisterSpec, req: TurnRequest, decision, ctx: ContextBlock,
                  recast: RecastDirective, t0: float):
        level_rules = get_level_rules(self._level).to_prompt()
        scene = self._state.scene_directive(recap=self._recap_pending)
        system = spec.render_system(
            level_rules=level_rules,
            scene_directive=scene,
            recast_directive=recast.text,
            ctx_block=ctx.text,
            output_format=SCHEMA_INSTRUCTION,
        )
        meta_payload = {
            "minister": spec.id,
            "mode": "recast" if recast else "normal",
            "level": self._level,
            "scene": self._state.state,
            "child_utterance": (req.child_utterance or req.asr_result.text or "").strip(),
            "emotion_hint": self._emotion_hint(decision.intent, self._state.state),
            "recast_corrected": req.assess_result.corrected if recast else "",
            "recast_word": req.assess_result.word if recast else "",
        }
        facts = ""
        if decision.intent == INTENT_THINGS and self._cfg.kg_lookup:
            thing = self._extract_thing(meta_payload["child_utterance"])
            facts_list = self._cfg.kg_lookup(thing) if thing else []
            if facts_list:
                facts = "KG FACTS (you may use ONLY these facts about the world): " \
                        + "; ".join(facts_list[:6])
        user = self._meta_line(meta_payload)
        user += f'\n\nCHILD SAID: "{meta_payload["child_utterance"]}"'
        if req.assess_result.score:
            user += f"\n(ASR assess score: {req.assess_result.score:.0f}/100)"
        if facts:
            user += "\n" + facts
        user += "\nReply now as the JSON object specified in the system prompt."

        response, meta = self._complete_with_retry(system, user, spec.id, recast_assess=req.assess_result if recast else None)
        return response, meta

    def _complete_with_retry(self, system: str, user: str, minister_id: str,
                             recast_assess: Optional[AssessResult]):
        """FR-E06：解析失败自动重试 1 次，再失败走模板（返回 response=None）。"""
        meta: Dict[str, Any] = {"fallback_used": False, "template_id": None, "repaired": False,
                                "ttft_ms": 0.0}
        bad_raw = ""
        for attempt in (1, 2):
            prompt = user if attempt == 1 else repair_user_prompt(user, bad_raw)
            result = self._provider.complete(system, prompt)
            self._session_cost_yuan += result.cost_yuan if result.ok else 0.0
            if result.ttft_ms:
                meta["ttft_ms"] = max(meta["ttft_ms"], result.ttft_ms)
            if not result.ok:
                bad_raw = result.error
                continue
            outcome = parse_llm_output(result.text, expected_speaker=minister_id)
            if not outcome.ok:
                bad_raw = result.text
                continue
            resp = outcome.response
            # Recast 铁律后置校验：打断式纠错的输出视同无效（重试→模板）
            if recast_assess is not None and detect_error_pointing(resp.text):
                bad_raw = result.text
                if attempt == 1:
                    continue
                resp = TurnResponse(
                    speaker=minister_id,
                    text=template_recast(recast_assess, minister_id),
                    emotion_tag="happy",
                )
                meta["fallback_used"], meta["template_id"] = True, "recast:template"
                self._bus.fallback(template_hit=True, minister=minister_id, scene="recast")
                return resp, meta
            if outcome.repaired:
                meta["repaired"] = True
            return resp, meta
        # 两次都失败 → 模板兜底（FR-E07）
        return None, meta

    # ------------------------------------------------------------------ 兜底与安全
    def _slot_vars(self, req: TurnRequest) -> Dict[str, str]:
        """兜底模板的插槽值（word/thing/task/count/feeling），杜绝 ?slot 泄漏。"""
        word = (req.assess_result.word if req.assess_result and req.assess_result.word
                else _DEFAULT_INVITE_WORD)
        planned = (self._state.tasks_planned[self._state.tasks_done]
                   if self._state.tasks_done < len(self._state.tasks_planned) else "")
        return {
            "word": word, "thing": word, "task": planned or word,
            "count": str(self._state.tasks_total), "feeling": "sad",
        }

    def _safe_or_template(self, response: TurnResponse, minister: str, intent: str,
                          req: TurnRequest, mode: str = "normal") -> TurnResponse:
        ok, text = self._safety.filter(response.text, context=mode)
        if ok:
            response.text = text
            return response
        # 安全拦截 → 场景模板兜底
        scene = _FALLBACK_SCENE_BY_INTENT.get(intent) or _STATE_FALLBACK_SCENE.get(
            self._state.state, "generic")
        tpl = self._templates.pick(minister, scene, **self._slot_vars(req))
        fallback = tpl.render(**self._slot_vars(req)) if tpl else "Hello! | 你好呀！"
        response.text = fallback
        response.meta["fallback_used"] = True
        response.meta["template_id"] = tpl.id if tpl else "hardcoded"
        self._bus.fallback(template_hit=True, minister=minister, scene=scene)
        return response

    def _template_fallback_after_llm_failure(self, minister: str, intent: str,
                                             req: TurnRequest) -> TurnResponse:
        scene = _FALLBACK_SCENE_BY_INTENT.get(intent) or _STATE_FALLBACK_SCENE.get(
            self._state.state, "generic")
        tpl = self._templates.pick(minister, scene, **self._slot_vars(req))
        text = tpl.render(**self._slot_vars(req)) if tpl else "Hello! | 你好呀！"
        self._bus.fallback(template_hit=True, minister=minister, scene=scene)
        return TurnResponse(speaker=minister, text=text, emotion_tag="happy",
                            meta={"fallback_used": True, "template_id": tpl.id if tpl else "hardcoded"})

    # ------------------------------------------------------------------ 上下文
    def _build_context(self, req: TurnRequest, decision, recast: RecastDirective) -> ContextBlock:
        if req.ctx_bundle is not None:
            turns = req.ctx_bundle.recent_turns
            words = req.ctx_bundle.learned_words_today
        else:
            turns = self._memory.recent_turns(10)
            words = self._memory.learned_words_today()
        state_line = json.dumps(self._state.to_dict(), ensure_ascii=False)
        return build_ctx_block(turns, words, state_line)

    # ------------------------------------------------------------------ 杂项
    def _collect_writes(self, response: Optional[TurnResponse], req: TurnRequest,
                        state_events: Dict[str, Any], decision, parent_note) -> List[MemoryWrite]:
        writes: List[MemoryWrite] = []
        if response:
            writes.extend(response.memory_write)
        if req.assess_result and req.assess_result.word:
            # Assessment evidence is deliberately candidate-level here. A
            # shared-state promotion step must confirm mastery across evidence.
            writes.append(MemoryWrite("learned_word", "word", req.assess_result.word,
                                      evidence_status="candidate"))
        if state_events.get("state_change"):
            writes.append(MemoryWrite("story_progress", "state_change", str(state_events["state_change"])))
        if state_events.get("day_completed"):
            writes.append(MemoryWrite("story_progress", "day_completed", self._state.date))
        if parent_note:
            writes.append(MemoryWrite(*parent_note))
        # 去重（同 key+value 只留一条）
        seen = set()
        uniq: List[MemoryWrite] = []
        for w in writes:
            k = (w.type, w.key, w.value)
            if k not in seen:
                seen.add(k)
                uniq.append(w)
        return uniq[:8]

    def _persist_state(self) -> None:
        self._memory.save_script_state(self._state.to_dict())

    def _check_cost(self) -> None:
        if (not self._cost_warned
                and self._session_cost_yuan > self._cfg.session_cost_budget_yuan):
            self._cost_warned = True
            self._bus.cost_warn(self._session_cost_yuan)

    @staticmethod
    def _meta_line(payload: Dict[str, Any]) -> str:
        return "__ENGINE_META__ " + json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_thing(utterance: str) -> str:
        """从万物类问句里抠目标名词的轻量尝试（真实 NER 属视觉/ASR 上游职责）。"""
        import re
        m = re.search(r"[a-zA-Z]{3,}", utterance)
        return m.group(0).lower() if m else ""

    @staticmethod
    def _emotion_hint(intent: str, state: str) -> str:
        if intent == INTENT_EMOTION_COMFORT:
            return "gentle"
        if state == STATE_BEDTIME:
            return "sleepy"
        if intent == INTENT_THINGS:
            return "curious"
        if state == STATE_ADVENTURE:
            return "excited"
        return "happy"
