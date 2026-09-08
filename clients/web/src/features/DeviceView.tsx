import { useEffect, useState } from "react";

import { Toggle } from "@/components/Toggle";
import type { DeviceSettingsPatch } from "@/api/contracts";
import type { AppState } from "@/state/appModel";

export function DeviceView({
  state,
  onPatch,
}: {
  state: AppState;
  onPatch: (patch: DeviceSettingsPatch) => Promise<void>;
}) {
  const [volumeDraft, setVolumeDraft] = useState<number | null>(null);
  const settings = state.deviceSettings;
  const [saving, setSaving] = useState(false);
  const [attempted, setAttempted] = useState(false);
  async function save(patch: DeviceSettingsPatch) {
    if (saving) return;
    setSaving(true);
    setAttempted(true);
    try {
      await onPatch(patch);
    } finally {
      setSaving(false);
    }
  }

  // Keep the committed draft visible until the saved settings catch up, so the
  // slider never snaps back mid-round-trip; a failed patch rolls the draft away.
  useEffect(() => {
    if (
      volumeDraft !== null &&
      settings &&
      Math.round(settings.volume) === volumeDraft
    ) {
      setVolumeDraft(null);
    }
  }, [settings, volumeDraft]);

  useEffect(() => {
    if (state.transientError !== null) setVolumeDraft(null);
  }, [state.transientError]);

  if (!settings) {
    return (
      <div className="status-placeholder">
        <h2>设备信息暂不可用</h2>
        <p>请返回首页重新加载家庭服务。设备离线与服务加载失败是不同的状态。</p>
      </div>
    );
  }

  const effectiveVolume = volumeDraft ?? settings.volume;

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">安心使用，简单照看</p>
          <h1>照看你的小P</h1>
          <p className="secondary-text">调整声音与灯光，了解设备现在的状态。</p>
        </div>
      </header>
      <aside className="device-note">
        <p>
          {settings.mock
            ? "当前未连接真实设备。下面的设置只在体验版中保存，不会操作硬件。"
            : "设置保存到服务不代表已送达设备，请留意设备的连接状态。"}
        </p>
      </aside>
      <section className="glass-card settings-card" aria-label="小P设备">
        <p className="card-caption">小P设备</p>
        <div className="settings-row">
          <label>状态</label>
          <span className="settings-value">
            {settings.online ? "在线" : "离线"}
          </span>
        </div>
        <div className="settings-row">
          <label>电量</label>
          <span className="settings-value">
            {settings.battery_percent === null
              ? "未知"
              : `${settings.battery_percent}%`}
          </span>
        </div>
        <details>
          <summary>设备详细信息</summary>
          <p>软件版本：{settings.firmware_version}</p>
          <p>最近记录：{settings.last_seen_at}</p>
        </details>
      </section>

      <fieldset
        disabled={saving}
        className="glass-card settings-card"
        aria-label="声音与灯光"
      >
        <p className="card-caption">声音与灯光</p>
        <label htmlFor="device-volume">
          音量 {Math.round(effectiveVolume)}
        </label>
        <input
          id="device-volume"
          type="range"
          min={0}
          max={100}
          step={1}
          value={effectiveVolume}
          onChange={(event) => setVolumeDraft(Number(event.target.value))}
          onPointerUp={() => commitVolume()}
          onKeyUp={() => commitVolume()}
          onBlur={() => commitVolume()}
        />
        <div className="settings-row">
          <label>启用陪伴灯</label>
          <Toggle
            label="启用陪伴灯"
            checked={settings.led_enabled}
            onChange={(value) => void save({ led_enabled: value })}
          />
        </div>
      </fieldset>

      <fieldset
        disabled={saving}
        className="glass-card settings-card"
        aria-label="感知与隐私"
      >
        <p className="card-caption">感知与隐私</p>
        <div className="settings-row">
          <label>允许按需使用摄像头</label>
          <Toggle
            label="允许按需使用摄像头"
            checked={settings.camera_enabled}
            onChange={(value) => void save({ camera_enabled: value })}
          />
        </div>
        <div className="settings-row">
          <label>允许上传原始音频</label>
          <Toggle
            label="允许上传原始音频"
            checked={settings.raw_audio_upload_enabled}
            onChange={(value) => void save({ raw_audio_upload_enabled: value })}
          />
        </div>
        <p className="secondary-text" style={{ fontSize: 13 }}>
          摄像头只在明确触发的短窗口内开启；原始画面默认不落盘。
        </p>
      </fieldset>

      <p role="status">
        {saving
          ? "正在保存设置…"
          : attempted && !state.transientError
            ? settings.mock
              ? "设置已保存到体验版；未发送到真实设备。"
              : "设置已保存到服务，请留意设备状态。"
            : ""}
      </p>
      {state.transientError ? (
        <div className="stale-banner" role="alert">
          设置没有保存，已恢复原值。请检查网络后重试。
        </div>
      ) : null}
    </>
  );

  // Commit one patch on release instead of per drag step, mirroring the iOS slider.
  // The draft stays visible until the effects above see the saved value or an error.
  function commitVolume() {
    if (
      volumeDraft === null ||
      volumeDraft === Math.round(settings?.volume ?? -1)
    )
      return;
    void save({ volume: volumeDraft });
  }
}
