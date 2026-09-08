import { MetricTile } from "@/components/MetricTile";
import { PetOrb } from "@/components/PetOrb";
import type { AppState } from "@/state/appModel";

const METRIC_LABELS = ["主动开口", "无提示输出", "新词"] as const;

export function TodayView({
  state,
  onRefresh,
}: {
  state: AppState;
  onRefresh: () => void;
}) {
  if (state.phase === "idle" || state.phase === "loading") return <LoadingView />;
  if (state.phase === "offline") return <OfflineView onRefresh={onRefresh} />;
  if (!state.dashboard) return <EmptyView />;

  const { dashboard } = state;
  return (
    <>
      {state.refreshError ? (
        <div className="stale-banner" role="status">
          ⚠ 刚刚没有刷新成功，现在显示的是已保存的内容
        </div>
      ) : null}

      <header>
        <p className="card-caption">家庭学习台</p>
        <h1 className="hero-greeting">{dashboard.greeting}</h1>
        <span className={`device-status ${dashboard.device.online ? "online" : "offline"}`}>
          {dashboard.device.online ? "✓ 小P设备在线" : "💤 小P设备暂时离线"}
        </span>
      </header>

      <section className="glass-card" aria-label="小P的观察">
        <div className="pet-row">
          <PetOrb statusLabel={dashboard.pet.accessibility_label} />
          <div>
            <p className="card-caption">小P的观察</p>
            <p className="pet-observation">★ {dashboard.highlight.text}</p>
          </div>
        </div>
      </section>

      <section className="glass-card" aria-label="下一步">
        <p className="card-caption">下一步</p>
        <h2 className="card-title">{dashboard.task.title}</h2>
        <p className="secondary-text">{dashboard.task.subtitle}</p>
        <div
          className="task-progress-track"
          role="progressbar"
          aria-valuenow={Math.round(dashboard.task.progress * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="任务进度"
        >
          <div
            className="task-progress-fill"
            style={{ width: `${Math.round(dashboard.task.progress * 100)}%` }}
          />
        </div>
        <button type="button" className="primary-button">
          {dashboard.task.action_label}
        </button>
      </section>

      <section aria-label="今日三个学习指标" className="metric-grid">
        <MetricTile
          label={METRIC_LABELS[0]}
          value={String(dashboard.metrics.spontaneous_speaking_count)}
          detail="今天"
        />
        <MetricTile
          label={METRIC_LABELS[1]}
          value={String(dashboard.metrics.unprompted_output_count)}
          detail="无需提示"
        />
        <MetricTile
          label={METRIC_LABELS[2]}
          value={String(dashboard.metrics.new_words.length)}
          detail={dashboard.metrics.new_words.join(" · ") || "—"}
        />
      </section>
    </>
  );
}

function LoadingView() {
  return (
    <div className="skeleton-stack" aria-label="正在准备今天的家庭摘要" role="status">
      <div style={{ width: "100%", height: 58 }} className="skeleton-card" />
      <div className="skeleton-hero" />
      <div className="skeleton-card" style={{ width: "100%" }} />
      <div className="skeleton-card" style={{ width: "100%" }} />
    </div>
  );
}

function OfflineView({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="status-placeholder">
      <h2>小P正在休息</h2>
      <p>暂时没连上家庭服务。已有内容不会丢失，可以稍后再试。</p>
      <button type="button" className="primary-button" onClick={onRefresh}>
        重新连接
      </button>
    </div>
  );
}

function EmptyView() {
  return (
    <div className="status-placeholder">
      <h2>今天还没有新记录</h2>
      <p>小P会在下一次真实互动后带回新的发现。</p>
    </div>
  );
}
