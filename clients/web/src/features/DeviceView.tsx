import { useEffect, useState } from "react";

import { Toggle } from "@/components/Toggle";
import type { DeviceSettingsPatch } from "@/api/contracts";
import type { AppState } from "@/state/appModel";

export function DeviceView({
  state,
  onPatch,
}: {
  state: AppState;
  onPatch: (patch: DeviceSettingsPatch) => void;
}) {
  const [volumeDraft, setVolumeDraft] = useState<number | null>(null);
  const settings = state.deviceSettings;

  // Keep the committed draft visible until the saved settings catch up, so the
  // slider never snaps back mid-round-trip; a failed patch rolls the draft away.
  useEffect(() => {
    if (volumeDraft !== null && settings && Math.round(settings.volume) === volumeDraft) {
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
        <p>等小P设备回到在线状态后，这里会恢复。</p>
      </div>
    );
  }

  const effectiveVolume = volumeDraft ?? settings.volume;

  return (
    <>
      <section className="glass-card settings-card" aria-label="小P设备">
        <p className="card-caption">小P设备</p>
        <div className="settings-row">
          <label>状态</label>
          <span className="settings-value">{settings.online ? "在线" : "离线"}</span>
        </div>
        <div className="settings-row">
          <label>电量</label>
          <span className="settings-value">
            {settings.battery_percent === null ? "未知" : `${settings.battery_percent}%`}
          </span>
        </div>
        <div className="settings-row">
          <label>固件</label>
          <span className="settings-value">{settings.firmware_version}</span>
        </div>
      </section>

      <section className="glass-card settings-card" aria-label="声音与灯光">
        <p className="card-caption">声音与灯光</p>
        <label htmlFor="device-volume">音量 {Math.round(effectiveVolume)}</label>
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
            onChange={(value) => onPatch({ led_enabled: value })}
          />
        </div>
      </section>

      <section className="glass-card settings-card" aria-label="感知与隐私">
        <p className="card-caption">感知与隐私</p>
        <div className="settings-row">
          <label>允许短时指向识别摄像头</label>
          <Toggle
            label="允许短时指向识别摄像头"
            checked={settings.camera_enabled}
            onChange={(value) => onPatch({ camera_enabled: value })}
          />
        </div>
        <div className="settings-row">
          <label>允许上传原始音频</label>
          <Toggle
            label="允许上传原始音频"
            checked={settings.raw_audio_upload_enabled}
            onChange={(value) => onPatch({ raw_audio_upload_enabled: value })}
          />
        </div>
        <p className="secondary-text" style={{ fontSize: 13 }}>
          摄像头只在明确触发的短窗口内开启；原始画面默认不落盘。
        </p>
      </section>

      {state.transientError ? (
        <div className="stale-banner" role="alert">
          ↺ 设置没有保存，已恢复原值。
        </div>
      ) : null}
    </>
  );

  // Commit one patch on release instead of per drag step, mirroring the iOS slider.
  // The draft stays visible until the effects above see the saved value or an error.
  function commitVolume() {
    if (volumeDraft === null || volumeDraft === Math.round(settings?.volume ?? -1)) return;
    onPatch({ volume: volumeDraft });
  }
}
