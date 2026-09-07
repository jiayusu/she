#!/usr/bin/env python3
"""scheduler.py — 定时任务 (stdlib, 无外部依赖)。

  fetch     daily 02:00   问题池采集+结构化 (FR-I01/02/03)
  rerun     daily 02:30   隔日补跑队列 + kg_pending 重试 (FR-I07)
  purge     daily 03:30   原始归档 90 天清理 (FR-I08)
  sentiment every 30min   舆情轮询, 负面 2h SLA (FR-I06)
  digest    daily 18:30   日报汇总, 告警不风暴 (§5)
  radar     mon 09:00     家长语言雷达周报 (FR-I05)

水位记在 meta 表 (scheduler.<job>), 重启不重复跑。
启动: python scheduler.py
"""
import json
import time
import traceback

import archive
import config
import db
import notify
import pipeline
import quota
import radar
import sentiment

CHECK_EVERY_SEC = 20


def parse_cron(spec):
    """'daily 02:00' | 'mon 09:00' | 'every N min' → (kind, arg)。"""
    kind, _, rest = spec.strip().partition(" ")
    rest = rest.strip()
    if kind == "every":
        return ("interval", int(rest.split()[0]))
    hh, mm = rest.split(":")
    return (kind, f"{int(hh):02d}:{int(mm):02d}")


def due(conn, name, spec, now=None):
    """该任务现在该跑吗? (当天/本周未跑过且时间已到; interval 按 epoch 分钟)"""
    kind, arg = parse_cron(spec)
    now = now or time.localtime()
    last = db.get_meta(conn, f"scheduler.{name}")
    if kind == "interval":
        slot = int(time.time() // (arg * 60))
        return last != str(slot), str(slot)
    wday = time.strftime("%a", now).lower()
    if kind != "daily" and wday != kind:  # 'mon'..'sun'
        return False, None
    if time.strftime("%H:%M", now) < arg:
        return False, None
    slot = f"{time.strftime('%Y-%m-%d', now)} {arg}"
    return last != slot, slot


def mark(conn, name, slot):
    db.set_meta(conn, f"scheduler.{name}", slot)


def run_job(conn, name):
    log = lambda m: print(f"[{time.strftime('%m-%d %H:%M:%S')}] {name}: {m}", flush=True)  # noqa: E731
    try:
        if name == "fetch":
            out = pipeline.fetch_and_store(conn)
            out["structure"] = pipeline.structure_pending(conn)
            log(json.dumps(out, ensure_ascii=False, default=str)[:400])
        elif name == "rerun":
            for job in quota.due_jobs(conn, ("question_pool", "sentiment", "radar")):
                if job["kind"] == "question_pool":
                    out = pipeline.fetch_and_store(conn)
                    pipeline.structure_pending(conn)
                elif job["kind"] == "sentiment":
                    out = sentiment.poll(conn, force=True)
                elif job["kind"] == "radar":
                    out = radar.run(conn, force=True)
                else:
                    out = {}
                quota.finish_job(conn, job["id"], ok=not out.get("skipped"))
                log(f"补跑 job#{job['id']} {job['kind']} ok")
            kg = kg_retry(conn)
            log(f"kg_pending 重试 {len(kg)} 条")
        elif name == "purge":
            n = archive.purge()
            log(f"清理 {n} 个过期归档日目录 (保留 {config.RAW_RETENTION_DAYS} 天)")
        elif name == "sentiment":
            out = sentiment.poll(conn)
            log(json.dumps(out, ensure_ascii=False, default=str)[:300])
        elif name == "digest":
            out = notify.daily_digest(conn)
            log(f"日报 via {out.get('via')} ok={out.get('ok')}")
        elif name == "radar":
            out = radar.run(conn)
            log(f"周报 ok={out.get('ok')} week={out.get('week')} "
                f"samples={out.get('samples')}")
        else:
            log("unknown job")
    except Exception as e:  # noqa: BLE001 — 单任务失败不影响其他任务 (§5)
        log(f"FAILED: {e}\n{traceback.format_exc(limit=3)}")
        try:
            quota.alert(conn, name, "error", f"调度任务 {name} 失败: {e}", "job_fail")
        except Exception:  # noqa: BLE001
            pass


def kg_retry(conn):
    import kg_bridge
    return kg_bridge.retry_kg_pending(conn)


JOBS = {"fetch": config.FETCH_CRON, "rerun": "daily 02:30", "purge": config.PURGE_CRON,
        "sentiment": f"every {config.SENTIMENT_INTERVAL_MIN} min",
        "digest": config.DIGEST_CRON, "radar": config.RADAR_WEEKLY_CRON}


def main():
    config.ensure_dirs()
    conn = db.connect()
    print(f"[scheduler] start: {JOBS}")
    while True:
        for name, spec in JOBS.items():
            try:
                is_due, slot = due(conn, name, spec)
            except Exception:  # noqa: BLE001
                continue
            if is_due and slot:
                mark(conn, name, slot)  # 先记水位再跑: 失败由告警暴露, 不整日重试
                run_job(conn, name)
        time.sleep(CHECK_EVERY_SEC)


if __name__ == "__main__":
    main()
