import {
  AppApiError,
  type DashboardSnapshot,
  type DeviceSettings,
  type DeviceSettingsPatch,
  type ParentConstraints,
  type ParentConstraintsUpdate,
  type WeeklyReport,
} from "@/api/contracts";
import type { AppApi } from "@/api/appApi";

export type AppPhase = "idle" | "loading" | "ready" | "offline";

export interface AppState {
  phase: AppPhase;
  dashboard: DashboardSnapshot | null;
  weeklyReport: WeeklyReport | null;
  deviceSettings: DeviceSettings | null;
  parentConstraints: ParentConstraints | null;
  transientError: AppApiError | null;
  refreshError: AppApiError | null;
}

export const initialAppState: AppState = {
  phase: "idle",
  dashboard: null,
  weeklyReport: null,
  deviceSettings: null,
  parentConstraints: null,
  transientError: null,
  refreshError: null,
};

export type AppModelListener = (state: AppState) => void;

/**
 * Same view-model contract as the iOS `AppModel`: a failed refresh over
 * existing evidence keeps the saved content and surfaces a gentle refresh
 * error, and device-setting patches apply optimistically then roll back on
 * failure. The model exposes no mastery mutation of any kind.
 */
export class AppModel {
  private state: AppState = initialAppState;
  private readonly listeners = new Set<AppModelListener>();

  constructor(private readonly api: AppApi) {}

  getState(): AppState {
    return this.state;
  }

  subscribe(listener: AppModelListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private setState(patch: Partial<AppState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  }

  async load(): Promise<void> {
    const hasEvidence = this.state.dashboard !== null;
    if (!hasEvidence) this.setState({ phase: "loading" });
    this.setState({ refreshError: null });
    try {
      const dashboard = await this.api.dashboard();
      const weeklyReport = await this.api.weeklyReport();
      const deviceSettings = await this.api.deviceSettings(dashboard.device.device_id);
      this.setState({ dashboard, weeklyReport, deviceSettings, phase: "ready" });
    } catch (error) {
      const appError = error instanceof AppApiError ? error : new AppApiError("invalid_response");
      if (hasEvidence) {
        this.setState({ refreshError: appError });
      } else {
        this.setState({
          dashboard: null,
          weeklyReport: null,
          deviceSettings: null,
          transientError: appError,
          refreshError: appError,
          phase: "offline",
        });
      }
    }
  }

  async updateDeviceSettings(patch: DeviceSettingsPatch): Promise<void> {
    const current = this.state.deviceSettings;
    if (!current) return;
    const previous = current;
    const optimistic: DeviceSettings = {
      ...current,
      ...(patch.volume === undefined ? {} : { volume: patch.volume }),
      ...(patch.led_enabled === undefined ? {} : { led_enabled: patch.led_enabled }),
      ...(patch.camera_enabled === undefined ? {} : { camera_enabled: patch.camera_enabled }),
      ...(patch.raw_audio_upload_enabled === undefined
        ? {}
        : { raw_audio_upload_enabled: patch.raw_audio_upload_enabled }),
    };
    this.setState({ deviceSettings: optimistic, transientError: null });
    try {
      const saved = await this.api.updateDeviceSettings(current.device_id, patch);
      this.setState({ deviceSettings: saved });
    } catch (error) {
      const appError = error instanceof AppApiError ? error : new AppApiError("invalid_response");
      this.setState({ deviceSettings: previous, transientError: appError });
    }
  }

  async updateParentConstraints(update: ParentConstraintsUpdate): Promise<ParentConstraints | null> {
    try {
      const saved = await this.api.updateParentConstraints(update);
      this.setState({ parentConstraints: saved });
      return saved;
    } catch (error) {
      const appError = error instanceof AppApiError ? error : new AppApiError("invalid_response");
      this.setState({ transientError: appError });
      return null;
    }
  }

  async requestPrivacyExport() {
    return this.api.requestPrivacyExport();
  }

  async requestPrivacyErase() {
    return this.api.requestPrivacyErase();
  }
}
