import { useEffect, useRef, useState } from "react";
import type { AppModel } from "@/state/appModel";
import { useAppModel } from "@/state/useAppModel";
import { PetOrb } from "@/components/PetOrb";
import { DeviceView } from "./DeviceView";
import { ProfileView } from "./ProfileView";
import { ReportsView } from "./ReportsView";
import { TodayView } from "./TodayView";

const TABS = [
  { key: "today", label: "今天", glyph: "☀" },
  { key: "reports", label: "成长记录", glyph: "✿" },
  { key: "device", label: "我的设备", glyph: "◉" },
  { key: "family", label: "家庭计划", glyph: "⌂" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export function RootApp({ model }: { model: AppModel }) {
  const state = useAppModel(model);
  const [tab, setTab] = useState<TabKey>("today");
  const [childPreview, setChildPreview] = useState(false);
  const main = useRef<HTMLElement>(null);
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    main.current?.focus();
  }, [tab, childPreview]);
  const unavailable =
    state.phase === "idle" ||
    state.phase === "loading" ||
    state.phase === "offline";
  return (
    <div className={`page ${childPreview ? "child-page" : ""}`}>
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <header className="brand-bar">
        <div className="brand">
          <span aria-hidden="true">✦</span> 小P{" "}
          <small>陪伴每一次小小的开口</small>
        </div>
        <span className="audience-badge">
          {childPreview ? "亲子共看" : "家长空间"}
        </span>
      </header>
      {state.dashboard?.mock && (
        <aside className="demo-notice">
          <strong>体验版</strong>{" "}
          这里是示例家庭，记录不是孩子的真实学习结果。设置会在服务重启后恢复。
        </aside>
      )}
      {!childPreview && (
        <nav className="tabs" aria-label="家长导航">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-current={tab === item.key ? "page" : undefined}
              className="tab-button"
              onClick={() => setTab(item.key)}
            >
              <span aria-hidden="true">{item.glyph}</span>
              {item.label}
            </button>
          ))}
        </nav>
      )}
      <main id="main-content" ref={main} tabIndex={-1}>
        {childPreview && state.dashboard ? (
          <section className="child-preview" data-child-preview>
            <p className="eyebrow">和家长一起，看看今天的小发现</p>
            <PetOrb statusLabel="小P，陪你探索的伙伴" />
            <h1>今天，和小P一起看看</h1>
            <div className="child-task">
              <span aria-hidden="true">✦</span>
              <h2>{state.dashboard.task.subtitle}</h2>
              <p>{state.dashboard.task.title}</p>
            </div>
            <p className="secondary-text">
              这是任务预览，还没有开始语音互动。现在不需要回答，也没有考试。
            </p>
            <button
              className="primary-button"
              onClick={() => setChildPreview(false)}
            >
              返回家长首页
            </button>
          </section>
        ) : (
          <>
            {state.refreshError && !unavailable && (
              <div className="stale-banner" role="alert">
                刷新失败，显示上次读取的内容。
                <button
                  className="text-button"
                  onClick={() => void model.load()}
                >
                  重新加载
                </button>
              </div>
            )}
            {unavailable ? (
              <TodayView
                state={state}
                onRefresh={() => void model.load()}
                onPreview={() => setChildPreview(true)}
                onDevice={() => setTab("device")}
              />
            ) : (
              <>
                {tab === "today" && (
                  <TodayView
                    state={state}
                    onRefresh={() => void model.load()}
                    onPreview={() => setChildPreview(true)}
                    onDevice={() => setTab("device")}
                  />
                )}
                {tab === "reports" && <ReportsView state={state} />}
                {tab === "device" && (
                  <DeviceView
                    state={state}
                    onPatch={(patch) => model.updateDeviceSettings(patch)}
                  />
                )}
                <div hidden={tab !== "family"}>
                  <ProfileView model={model} state={state} />
                </div>
              </>
            )}
          </>
        )}
      </main>
      <footer className="footer-note">
        {childPreview
          ? "由家长陪同使用 · 任务预览"
          : "不用追赶进度，愿意尝试就是好的开始。"}
      </footer>
    </div>
  );
}
