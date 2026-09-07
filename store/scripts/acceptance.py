#!/usr/bin/env python3
"""acceptance.py — 04 记忆存储验收红线实测(自包含, 无需外部服务)。

覆盖 README §3/§4/§8 全部验收口径, 实测打分:
  FR-M01 五库物理分离 / FR-M02 写入≤20ms 检索≤50ms / FR-M03 时间查询≥80% /
  FR-M04 巩固走 KG 热更新+发音闸门 / FR-M05 白名单 3 年零丢失 / FR-M06 再巩固 /
  FR-M07 20:30 准时率 100% / FR-M08 快照回滚≤1min / FR-M09 溢出策略 /
  非功能 审计 3 年 / 崩溃恢复≤2s / 72h 删除。

运行: python scripts/acceptance.py
"""
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memstore import Config, MemoryService  # noqa: E402
from memstore.temporal import parse  # noqa: E402

RESULTS = []
DAY = 86400.0
NOW0 = time.mktime(time.strptime("2026-09-01 10:00:00", "%Y-%m-%d %H:%M:%S"))


def check(name, ok, evidence):
    RESULTS.append((name, ok, evidence))
    print(f"  {'✅' if ok else '❌'} {name}  {evidence}")


def section(title):
    print(f"\n== {title} ==")


def fresh(tmp, name=None, **kw):
    d = Path(tmp) / (name or f"acc-{time.time_ns()}")
    cfg = Config(data_dir=d, auto_jobs=False, port=0, **kw)
    return MemoryService(cfg)


# ---------------------------------------------------------------- FR-M01
def acc_m01(tmp):
    section("FR-M01 五库 Schema: 物理分离")
    svc = fresh(tmp)
    try:
        tables = {r["name"] for r in svc.db.q(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        need = {"working_turns", "episodes", "episodes_cold", "salience_buffer",
                "whitelist", "procedural"}
        h = svc.health()
        check("五库表物理分离 + semantic=KG 衔接",
              need <= tables and set(h["stores"]) == {
                  "working", "episodic", "semantic", "salience", "procedural"},
              f"tables={sorted(need)} semantic→{h['stores']['semantic']['url']}")
        check("容量约定 10/1000/500",
              (svc.working.cap, svc.salience.cap, svc.procedural.cap) == (10, 1000, 500),
              "working=10 salience=1000 procedural=500")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M02
def acc_m02(tmp):
    section("FR-M02 情景写入: ≤20ms / top-k ≤50ms")
    svc = fresh(tmp)
    try:
        wl, rl = [], []
        for i in range(500):
            t0 = time.perf_counter()
            svc.write_episode(utterance=f"we learn word number {i}",
                              scene="class", session_id="perf")
            wl.append((time.perf_counter() - t0) * 1000)
        for i in range(300):
            t0 = time.perf_counter()
            svc.recall("learn word", k=5)
            rl.append((time.perf_counter() - t0) * 1000)
        wp95 = statistics.quantiles(wl, n=20)[-1]
        rp95 = statistics.quantiles(rl, n=20)[-1]
        check("写入 p95 ≤ 20ms", wp95 < 20, f"p95={wp95:.2f}ms (n=500)")
        check("召回 p95 ≤ 50ms", rp95 < 50, f"p95={rp95:.2f}ms (n=300, 500 库存)")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M03
def acc_m03(tmp):
    section("FR-M03 StoryArc 时间查询: 准确率 ≥80%")
    cases = [
        ("今天学了什么", {"day_from": "2026-09-04", "day_to": "2026-09-04"}),
        ("昨天的朝会", {"day_from": "2026-09-03", "day_to": "2026-09-03"}),
        ("前天吃的什么", {"day_from": "2026-09-02", "day_to": "2026-09-02"}),
        ("大前天唱歌", {"day_from": "2026-09-01", "day_to": "2026-09-01"}),
        ("3天前浇花", {"day_from": "2026-09-01", "day_to": "2026-09-01"}),
        ("最近画的画", {"day_from": "2026-09-02", "day_to": "2026-09-04"}),
        ("本周学的词", {"day_from": "2026-08-29", "day_to": "2026-09-04"}),
        ("上周的故事", {"day_from": "2026-08-22", "day_to": "2026-08-28"}),
        ("上个月的旅行", {"day_from": "2026-07-06", "day_to": "2026-08-05"}),
        ("第3章的冒险", {"chapter": 3}),
        ("第 2 话", {"chapter": 2}),
        ("第一次见小熊", {"first": True}),
        ("我第一次教它说话", {"first": True}),
        ("今天第一次举手", {"first": True, "day_from": "2026-09-04"}),
        ("上周第一次得小星星", {"first": True, "day_from": "2026-08-22"}),
        ("7天前种的苹果树", {"day_from": "2026-08-28", "day_to": "2026-08-28"}),
        ("这几天学的歌", {"day_from": "2026-09-02", "day_to": "2026-09-04"}),
        ("昨天的第1章", {"day_from": "2026-09-03", "chapter": 1}),
        ("无时间词普通查询", {"day_from": None, "chapter": None, "first": False}),
        ("最近一周", {"day_from": "2026-09-02"}),
    ]
    ok = sum(all(parse(q, now=NOW0 + 3 * DAY)[k] == v for k, v in exp.items())
             for q, exp in cases)
    acc = ok / len(cases)
    check(f"时间查询准确率 ≥80%", acc >= 0.8, f"{ok}/{len(cases)} = {acc:.0%}")
    # 章节组织与"第一次"端到端
    svc = fresh(tmp)
    try:
        svc.write_episode(utterance="forest adventure begins", chapter=2,
                          ts=NOW0 - 2 * DAY)
        svc.write_episode(utterance="第一次骑自行车", ts=NOW0 - 30 * DAY)
        svc.write_episode(utterance="又骑自行车了", ts=NOW0)
        r1 = svc.recall("第2章 冒险", k=3)
        r2 = svc.recall("第一次骑自行车", k=3)
        check("章节过滤 + '第一次'最早命中端到端",
              r1["results"] and r1["results"][0]["chapter"] == 2
              and r2["results"][0]["utterance"] == "第一次骑自行车",
              f"ch2={bool(r1['results'])} first={r2['results'][0]['day']}")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M04
def acc_m04(tmp):
    section("FR-M04 巩固管线: KG 热更新衔接(发音闸门)")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from conftest import KGStub
    kg = KGStub().start()
    svc = fresh(tmp, kg_url=kg.url)
    try:
        out = svc.consolidate({"memories": [
            {"scene": "breakfast", "words": ["milk", "cup"], "assess": 88},
            {"scene": "breakfast", "words": ["milk", "cup"], "assess": 91}],
            "threshold": 2})
        v1 = kg.version
        out2 = svc.consolidate({"edges": [{"head": "apple", "rel": "IsA",
                                           "tail": "fruit", "assess": 92}]})
        bad = svc.consolidate({"edges": [{"head": "wong", "rel": "IsA",
                                          "tail": "fruit", "assess": 55}]})
        check("巩固批次走 KG 热更新接口(版本+1)",
              out["promoted"] >= 1 and out2["kg_versions"] and kg.version > v1,
              f"promoted={out['promoted']}+{out2['promoted']} kg_version={kg.version}")
        check("发音评估 <阈值不入 KG(防错误固化)",
              out2["promoted"] == 1 and bad["promoted"] == 0
              and bad["rejected"][0]["reason"] == "assess_below_gate",
              "assess=55 被 assess_below_gate 拦截")
        kg.conflicts_to_return = [{"id": 1, "head": "a", "rel": "IsA", "tail": "b",
                                   "kind": "contradiction", "detail": "demo"}]
        out3 = svc.consolidate({"edges": [{"head": "a", "rel": "IsA", "tail": "b",
                                           "assess": 95}]})
        check("冲突边进待审队列",
              len(out3["conflicts"]) == 1
              and len(svc.consolidator.conflicts("open")) == 1,
              "pending_conflicts 镜像 1 条")
        kg.stop()
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M05
def acc_m05(tmp):
    section("FR-M05 遗忘剪枝: EMA 衰减 + 白名单 3 年零丢失")
    svc = fresh(tmp)
    try:
        svc.write_episode(utterance="milestone first sentence", salience=1.0,
                          kind="milestone", ref_id="mw-acc", ts=NOW0)
        svc.write_episode(utterance="small talk about weather", salience=0.5,
                          ts=NOW0)
        pruned_at = None
        for d in range(1, 3 * 365 + 1):  # 3 年逐日模拟
            out = svc.lifecycle.decay_pass(ts=NOW0 + d * DAY)
            if out["pruned"] and pruned_at is None:
                pruned_at = d
        counts = svc.episodic.counts()
        logs = svc.audit.query(action="prune")
        check("白名单 3 年模拟零丢失", counts["active"] == 1 and counts["cold"] == 1,
              f"1095 步后 active={counts['active']} cold={counts['cold']}")
        check("低显著性被剪除且日志可审计",
              pruned_at is not None and len(logs) == 1
              and "episode:2" in logs[0]["target"],
              f"day={pruned_at} 剪除, audit 1 条, prune_count="
              f"{svc.metrics.snapshot()['counters']['prune_count']}")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M06
def acc_m06(tmp):
    section("FR-M06 再巩固: 冷存储恢复并加权")
    svc = fresh(tmp)
    try:
        svc.write_episode(utterance="we made a paper boat", salience=0.5, ts=NOW0)
        svc.lifecycle.decay_pass(ts=NOW0 + 90 * DAY)
        assert svc.episodic.counts()["cold"] == 1
        out = svc.recall("paper boat", k=3)
        row = svc.episodic.get(out["restored"][0]["id"])
        check("已剪记忆重新提及 → 自动恢复加权",
              out["restored"] and row["reconsolidated"] == 1
              and row["salience"] > 0.5,
              f"salience 0.5→{row['salience']:.3f}, reconsolidated=1")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M07
def acc_m07(tmp):
    section("FR-M07 程序性库: 20:30 提醒准时率 100%")
    svc = fresh(tmp)
    try:
        svc.procedural.add("朝会提醒",
                           {"type": "time", "time": "20:30", "repeat": "daily"},
                           {"type": "remind", "text": "朝会开始啦"})
        T = lambda s: datetime.fromisoformat(s).timestamp()  # noqa: E731
        hits = misses = 0
        for d in range(30):  # 30 天逐分钟采样
            base = T("2026-09-04T00:00:00") + d * DAY
            for m in range(0, 24 * 60, 5):
                ts = base + m * 60
                due = svc.procedural.due(ts=ts)
                hhmm = time.strftime("%H:%M", time.localtime(ts))
                already = svc.db.q1("SELECT last_fired FROM procedural")["last_fired"]
                fired_today = already and time.strftime(
                    "%Y-%m-%d", time.localtime(already)) == time.strftime(
                    "%Y-%m-%d", time.localtime(ts))
                expect = hhmm >= "20:30" and not fired_today
                if bool(due) == expect:
                    hits += 1
                else:
                    misses += 1
                if due and not fired_today:
                    svc.procedural.mark_fired(due[0]["id"], ts=ts)
        check("30 天逐 5 分钟采样准时率 100%, 无重复触发", misses == 0,
              f"{hits}/{hits + misses} 采样点判定正确")
    finally:
        svc.close()


# ---------------------------------------------------------------- FR-M08
def acc_m08(tmp):
    section("FR-M08 快照与回滚: ≤1 分钟恢复")
    svc = fresh(tmp)
    try:
        svc.write_episode(utterance="keep me", salience=0.4, ts=NOW0)
        snap = svc.snapshot(note="acceptance")
        for i in range(5):
            svc.write_episode(utterance=f"bad write {i}", salience=0.4,
                              ts=NOW0 + i)
        out = svc.rollback(snap["version"])
        check("任意版本回滚 ≤1 分钟, 数据一致",
              "error" not in out and out["duration_ms"] < 60_000
              and svc.episodic.counts()["active"] == 1,
              f"v{snap['version']} 恢复 {out['duration_ms']}ms, "
              f"reindexed={out['reindexed']}")
        # FAISS 损坏自愈
        svc.close()
        svc.cfg.vector_path().write_bytes(b"CORRUPT")
        svc2 = MemoryService(svc.cfg)
        try:
            c = svc2.episodic.counts()
            check("FAISS 损坏 → 启动自检从 SQLite 重建索引",
                  c["indexed"] == c["active"] + c["cold"],
                  f"indexed={c['indexed']} (重建自愈)")
        finally:
            svc2.close()
    finally:
        if svc.db.conn is not None:
            try:
                svc.db.conn.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------- FR-M09
def acc_m09(tmp):
    section("FR-M09 容量管理: LRU 溢出 / 缓冲降级")
    svc = fresh(tmp)
    try:
        now = time.time()
        for i in range(12):
            svc.working_push("s-acc", f"turn-{i}", ts=now + i)
        overflows = [r for r in svc.episodic.all_rows() if r["kind"] == "overflow"]
        check("工作记忆满 10 → LRU 溢出到情景库",
              len(svc.working.items("s-acc")) == 10 and len(overflows) == 2,
              f"内存 10 条 + overflow {len(overflows)} 条(turn-0/1)")
        small = fresh(tmp, salience_cap=3)
        try:
            for i in range(5):
                small.write_episode(utterance=f"sb-{i}", salience=0.9 - i * 0.1,
                                    mirror_salience=True)
            contents = {r["utterance"] for r in small.episodic.all_rows()}
            check("显著性缓冲满 → 最低分降入情景库(不清除)",
                  small.salience.count() == 3 and
                  {f"sb-{i}" for i in range(5)} <= contents,
                  f"buffer=3, 5/5 内容保留在情景库")
        finally:
            small.close()
    finally:
        try:
            svc.db.conn.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- 非功能
def acc_nfr(tmp):
    section("非功能: 审计 / 崩溃恢复 / 删除合规")
    svc = fresh(tmp, name="recover")
    try:
        now = time.time()
        for i in range(3000):
            svc.write_episode(utterance=f"turn {i}", session_id=f"s-{i % 30}",
                              ts=now - (3000 - i) * 0.1)
    finally:
        svc.close()
    svc2 = fresh(tmp, name="recover")
    try:
        state = svc2.session_recover("s-7")
        check("崩溃恢复: session 从情景库重建 ≤2s",
              state["rebuilt"] == 10 and state["recovered_ms"] < 2000,
              f"3000 条库存, 恢复 {state['recovered_ms']}ms")
    finally:
        svc2.close()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from conftest import KGStub
    kg = KGStub().start()
    svc = fresh(tmp, kg_url=kg.url)
    try:
        svc.write_episode(utterance="erase me", child_id="child-x", salience=0.9)
        svc.consolidate({"child_id": "child-x",
                         "edges": [{"head": "dog", "rel": "IsA", "tail": "animal",
                                    "assess": 90}]})
        out = svc.erase("child-x", requested_by="parent")
        manifest_lines = Path(out["manifest"]).read_text(encoding="utf-8").splitlines()
        check("家长删除 → 五库+回流数据物理清除 + 微调剔除清单",
              out["status"] == "completed" and not svc.episodic.all_rows(
                  child_id="child-x")
              and out["deadline_ts"] > time.time()
              and all('fine_tune_dataset_removal' in l for l in manifest_lines),
              f"{out['stats']}, manifest {len(manifest_lines)} 行, 72h 红线留痕")
        check("审计留痕(删除/巩固/白名单)",
              {e["action"] for e in svc.audit.query(limit=100)} >=
              {"erase", "consolidate", "whitelist_add", "ep_write"},
              f"actions={sorted({e['action'] for e in svc.audit.query(limit=100)})}")
        kg.stop()
    finally:
        try:
            svc.db.conn.close()
        except Exception:  # noqa: BLE001
            pass


def main():
    print("04 记忆存储 · 验收红线实测")
    tmp = tempfile.mkdtemp(prefix="memstore-acc-")
    for fn in (acc_m01, acc_m02, acc_m03, acc_m04, acc_m05, acc_m06,
               acc_m07, acc_m08, acc_m09, acc_nfr):
        try:
            fn(tmp)
        except Exception as e:  # noqa: BLE001
            check(fn.__name, False, f"异常中断: {type(e).__name__}: {e}")
    ok = sum(1 for _, passed, _ in RESULTS if passed)
    print(f"\n===== 验收结果: {ok}/{len(RESULTS)} 通过 =====")
    for name, passed, ev in RESULTS:
        if not passed:
            print(f"  ❌ {name}: {ev}")
    sys.exit(0 if ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
