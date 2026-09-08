import { useState } from "react";

import type { AppModel } from "@/state/appModel";

type GoalSaveState = "idle" | "saving" | "saved" | "failed";

const DEMO_PRIVACY_NOTICE =
  "当前为演示家庭；导出与删除只演示流程，不会修改真实学习存储。";

export function ProfileView({ model }: { model: AppModel }) {
  const [sessionMinutes, setSessionMinutes] = useState(10);
  const [nextDayContext, setNextDayContext] = useState("明天去动物园");
  const [goalSaveState, setGoalSaveState] = useState<GoalSaveState>("idle");
  const [privacyResult, setPrivacyResult] = useState<string | null>(null);

  async function saveParentGoals() {
    setGoalSaveState("saving");
    const saved = await model.updateParentConstraints({
      session_budget_seconds: sessionMinutes * 60,
      preferred_topics: ["animals", "food"],
      avoid_topics: [],
      next_day_context: nextDayContext,
      teaching_pressure: "low",
    });
    const ok =
      saved !== null &&
      saved.session_budget_seconds === sessionMinutes * 60 &&
      saved.next_day_context === nextDayContext;
    setGoalSaveState(ok ? "saved" : "failed");
    if (ok) {
      await new Promise((resolve) => setTimeout(resolve, 2400));
      setGoalSaveState((current) => (current === "saved" ? "idle" : current));
    }
  }

  async function performPrivacy(kind: "export" | "erase") {
    const confirmed = window.confirm(
      kind === "export" ? "确认导出演示数据？" : "确认删除演示数据？",
    );
    if (!confirmed) return;
    try {
      const result =
        kind === "export" ? await model.requestPrivacyExport() : await model.requestPrivacyErase();
      setPrivacyResult(
        result.mock && !result.store_mutated
          ? "演示请求已接收；真实学习存储没有改变。"
          : "请求状态需要人工确认。",
      );
    } catch {
      setPrivacyResult("暂时无法完成演示，请稍后再试。");
    }
  }

  return (
    <>
      <section className="glass-card settings-card" aria-label="家庭">
        <p className="card-caption">家庭</p>
        <div className="settings-row">
          <label>👥 苏家 · 演示家庭</label>
        </div>
        <p className="secondary-text" style={{ fontSize: 13, margin: 0 }}>
          无登录 · 单家庭演示资料 · Web 调试入口
        </p>
      </section>

      <section className="glass-card settings-card" aria-label="下一次互动">
        <p className="card-caption">下一次互动</p>
        <div className="settings-row">
          <label htmlFor="session-minutes">时长 {sessionMinutes} 分钟</label>
          <input
            id="session-minutes"
            type="range"
            min={5}
            max={30}
            step={5}
            value={sessionMinutes}
            onChange={(event) => setSessionMinutes(Number(event.target.value))}
          />
        </div>
        <label htmlFor="next-day-context" style={{ fontSize: 13 }}>
          明天的场景
        </label>
        <input
          id="next-day-context"
          className="text-field"
          value={nextDayContext}
          onChange={(event) => setNextDayContext(event.target.value)}
        />
        <button
          type="button"
          className="primary-button"
          disabled={goalSaveState === "saving"}
          onClick={() => void saveParentGoals()}
        >
          {goalSaveState === "idle" && "保存家长目标"}
          {goalSaveState === "saving" && "正在保存…"}
          {goalSaveState === "saved" && "✓ 已保存到家庭计划"}
          {goalSaveState === "failed" && "↺ 暂时没有保存成功"}
        </button>
      </section>

      <section className="glass-card settings-card" aria-label="隐私与数据">
        <p className="card-caption">隐私与数据</p>
        <p className="secondary-text" style={{ fontSize: 13, margin: 0 }}>
          {DEMO_PRIVACY_NOTICE}
        </p>
        <button type="button" className="secondary-button" onClick={() => void performPrivacy("export")}>
          导出演示数据
        </button>
        <button
          type="button"
          className="secondary-button destructive"
          onClick={() => void performPrivacy("erase")}
        >
          删除演示数据
        </button>
        {privacyResult ? <p className="secondary-text" style={{ fontSize: 13 }}>{privacyResult}</p> : null}
      </section>
    </>
  );
}
