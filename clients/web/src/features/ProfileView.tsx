import { useState } from "react";
import type { AppModel, AppState } from "@/state/appModel";
const topics = (text: string) => [
  ...new Set(
    text
      .split(/[,，]/)
      .map((value) => value.trim())
      .filter(Boolean),
  ),
];
export function ProfileView({
  model,
  state,
}: {
  model: AppModel;
  state: AppState;
}) {
  const saved = state.parentConstraints;
  const [sessionMinutes, setSessionMinutes] = useState(
    (saved?.session_budget_seconds ?? 600) / 60,
  );
  const [nextDayContext, setNextDayContext] = useState(
    saved?.next_day_context ?? "",
  );
  const [interests, setInterests] = useState(
    saved?.preferred_topics.join("，") ?? "",
  );
  const [avoids, setAvoids] = useState(saved?.avoid_topics.join("，") ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [privacyResult, setPrivacyResult] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState(false);
  async function save() {
    if (saving) return;
    const preferred = topics(interests),
      avoided = topics(avoids);
    if (
      [preferred, avoided].some(
        (values) =>
          values.length > 10 || values.some((value) => value.length > 40),
      )
    ) {
      setMessage("每类最多填写 10 个主题，每个不超过 40 个字。");
      return;
    }
    setSaving(true);
    setMessage("");
    const result = await model.updateParentConstraints({
      session_budget_seconds: Math.round(sessionMinutes * 60),
      preferred_topics: preferred,
      avoid_topics: avoided,
      next_day_context: nextDayContext.trim(),
      teaching_pressure: saved?.teaching_pressure ?? "low",
    });
    setSaving(false);
    setMessage(
      result
        ? "计划已保存。体验版设置会在服务重启后恢复。"
        : "这次没有保存成功，你填写的内容还在，请再试一次。",
    );
  }
  async function privacy(kind: "export" | "erase") {
    if (
      !window.confirm(
        kind === "erase"
          ? "演示删除流程？这不会删除真实数据。"
          : "演示导出流程？这不会生成真实数据文件。",
      )
    )
      return;
    setPrivacyBusy(true);
    try {
      const result = await (kind === "erase"
        ? model.requestPrivacyErase()
        : model.requestPrivacyExport());
      setPrivacyResult(
        result.mock && !result.store_mutated
          ? "演示完成，没有导出文件，也没有删除真实数据。"
          : "请求已返回，请联系管理员确认处理结果。",
      );
    } catch {
      setPrivacyResult("暂时无法完成，请稍后重试。");
    } finally {
      setPrivacyBusy(false);
    }
  }
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">跟着孩子的节奏来</p>
          <h1>安排一点轻松的陪伴</h1>
          <p className="secondary-text">
            这些是家长的偏好，不是孩子必须完成的作业。
          </p>
        </div>
      </header>
      <form
        className="glass-card settings-card"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
        onChange={() => setMessage("")}
      >
        <fieldset disabled={saving || !saved}>
          <legend>下一次互动计划</legend>
          <label htmlFor="session-minutes">
            最多玩多久？ <strong>{sessionMinutes} 分钟</strong>
          </label>
          <input
            id="session-minutes"
            type="range"
            min="1"
            max="60"
            step="1"
            value={sessionMinutes}
            onChange={(event) => setSessionMinutes(Number(event.target.value))}
          />
          <p className="helper-text">
            这是时间上限，不是目标；孩子累了，随时可以停。
          </p>
          <label htmlFor="next-day-context">
            接下来有什么生活安排？ <span className="helper-text">选填</span>
          </label>
          <input
            id="next-day-context"
            className="text-field"
            value={nextDayContext}
            maxLength={200}
            placeholder="例如：周末去公园"
            onChange={(event) => setNextDayContext(event.target.value)}
          />
          <p className="helper-text">
            简单描述场景即可，不必填写姓名、地址等私人信息。
          </p>
          <label htmlFor="interests">
            最近喜欢什么？ <span className="helper-text">选填</span>
          </label>
          <input
            id="interests"
            className="text-field"
            value={interests}
            placeholder="例如：恐龙，水果"
            onChange={(event) => setInterests(event.target.value)}
          />
          <label htmlFor="avoids">
            暂时不聊什么？ <span className="helper-text">选填</span>
          </label>
          <input
            id="avoids"
            className="text-field"
            value={avoids}
            placeholder="例如：让孩子害怕的主题"
            onChange={(event) => setAvoids(event.target.value)}
          />
          <p className="helper-text">多个主题用逗号分开，每类最多 10 个。</p>
          <button className="primary-button" type="submit">
            {saving ? "正在保存…" : "保存计划"}
          </button>
        </fieldset>
        <p className="save-message" role="status">
          {message}
        </p>
      </form>
      <section className="glass-card">
        <h2>你的数据，你来决定</h2>
        <p className="secondary-text">
          当前是示例家庭。这里可以了解操作流程，暂不支持真实数据导出与删除。
        </p>
        <details>
          <summary>查看演示操作</summary>
          <div className="button-row">
            <button
              disabled={privacyBusy}
              className="secondary-button"
              onClick={() => void privacy("export")}
            >
              体验导出流程
            </button>
            <button
              disabled={privacyBusy}
              className="secondary-button"
              onClick={() => void privacy("erase")}
            >
              体验删除流程
            </button>
          </div>
          <p role="status">{privacyResult}</p>
        </details>
      </section>
    </>
  );
}
