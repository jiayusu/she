import { useState } from "react";

import type { AppModel } from "@/state/appModel";
import { useAppModel } from "@/state/useAppModel";
import { DeviceView } from "./DeviceView";
import { ProfileView } from "./ProfileView";
import { ReportsView } from "./ReportsView";
import { TodayView } from "./TodayView";

const TABS = [
  { key: "today", label: "今天", glyph: "✦" },
  { key: "reports", label: "成长", glyph: "📈" },
  { key: "device", label: "设备", glyph: "📡" },
  { key: "family", label: "家庭", glyph: "🏠" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function RootApp({ model }: { model: AppModel }) {
  const state = useAppModel(model);
  const [tab, setTab] = useState<TabKey>("today");

  return (
    <div className="page">
      <nav className="tabs" aria-label="主导航">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            className="tab-button"
            onClick={() => setTab(item.key)}
          >
            <span aria-hidden="true">{item.glyph}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {tab === "today" ? <TodayView state={state} onRefresh={() => void model.load()} /> : null}
      {tab === "reports" ? <ReportsView state={state} /> : null}
      {tab === "device" ? (
        <DeviceView state={state} onPatch={(patch) => void model.updateDeviceSettings(patch)} />
      ) : null}
      {tab === "family" ? <ProfileView model={model} /> : null}

      <footer className="footer-note">
        小P家长端 Web · 数据来自 Device Gateway · 演示家庭
        {state.dashboard?.mock ? " · mock 数据" : ""}
      </footer>
    </div>
  );
}
