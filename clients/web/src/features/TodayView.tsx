import { MetricTile } from "@/components/MetricTile";
import { PetOrb } from "@/components/PetOrb";
import type {
  RpgDeliveryStatus,
  RpgInventoryToken,
  RpgNodeId,
  RpgPhase,
} from "@/api/contracts";
import type { AppState } from "@/state/appModel";

const PHASE_LABELS: Record<RpgPhase, string> = {
  seeking_object: "正在寻找现实线索",
  confirming_object: "正在确认找到的物品",
  presenting: "提示正在准备播放",
  awaiting_speech: "设备正在等待孩子表达",
  resolving: "正在理解这次表达",
  paused: "任务已暂停",
  delivery_failed: "设备提示未成功播放",
  completed: "任务已完成",
};

const DELIVERY_LABELS: Record<RpgDeliveryStatus, string> = {
  planned: "等待发送到设备",
  issuing: "正在发送到设备",
  completed: "设备已完成播放",
  failed: "设备播放失败",
  expired: "设备指令已过期",
};

const INVENTORY_LABELS: Record<RpgInventoryToken, string> = {
  milk_token: "牛奶",
  red_cup_token: "红杯子",
};

const QUEST_LABELS: Record<RpgNodeId, string> = {
  collect_milk: "向饮品保管员取得牛奶",
  find_red_cup: "在房间里找到红杯子",
  picnic_ready: "完成野餐准备",
};

export function TodayView({
  state,
  onRefresh,
  onPreview,
  onDevice,
}: {
  state: AppState;
  onRefresh: () => void;
  onPreview: () => void;
  onDevice: () => void;
}) {
  if (state.phase === "idle" || state.phase === "loading")
    return (
      <div className="status-placeholder" role="status">
        <PetOrb statusLabel="正在加载" />
        <h1>正在准备你的家庭空间…</h1>
      </div>
    );
  if (state.phase === "offline")
    return (
      <div className="status-placeholder" role="alert">
        <h1>暂时连不上家庭服务</h1>
        <p>请检查网络，然后重新加载。此时无法读取或保存设置。</p>
        <button className="primary-button" onClick={onRefresh}>
          重新加载
        </button>
      </div>
    );
  if (!state.dashboard)
    return (
      <div className="status-placeholder">
        <h1>还没有学习记录</h1>
        <p>等有新的互动记录后，再来看看。</p>
        <button className="secondary-button" onClick={onRefresh}>
          刷新记录
        </button>
      </div>
    );
  const { dashboard } = state;
  const quest = state.questSummary?.quest ?? null;
  const deliveryStatus = state.questSummary?.delivery_status ?? null;
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">每天一点点，一起慢慢来</p>
          <h1>今天，陪孩子轻松开口</h1>
          <p className="secondary-text">看看小发现，再一起预览下一次探险。</p>
        </div>
        <button className="text-button" onClick={onRefresh}>
          刷新记录 ↻
        </button>
      </header>
      <div className="home-grid">
        <section className="welcome-card">
          <div>
            <p className="eyebrow">小P带回的小发现</p>
            <h2>{dashboard.highlight.text}</h2>
            <p>记录一次尝试，不给孩子打分。</p>
          </div>
          <PetOrb statusLabel={dashboard.pet.accessibility_label} />
        </section>
        <section className="glass-card next-task">
          <p className="eyebrow">接下来 · 亲子共看</p>
          <h2>{dashboard.task.subtitle}</h2>
          <p className="secondary-text">{dashboard.task.title}</p>
          <button className="primary-button" onClick={onPreview}>
            和孩子一起看 <span aria-hidden="true">→</span>
          </button>
          <p className="helper-text">
            打开简单的任务预览，不会开启摄像头或录音。
          </p>
        </section>
      </div>
      {quest && (
        <section className="rpg-quest-card" data-rpg-quest aria-labelledby="rpg-quest-title">
          <header className="rpg-quest-heading">
            <div>
              <p className="eyebrow">当前现实语言任务 · 家长只读</p>
              <h2 id="rpg-quest-title">{QUEST_LABELS[quest.node_id]}</h2>
            </div>
            <span className="quest-phase">{PHASE_LABELS[quest.phase]}</span>
          </header>
          <dl className="quest-facts">
            <div>
              <dt>故事角色</dt>
              <dd>{quest.world_role}</dd>
            </div>
            <div>
              <dt>语言目标</dt>
              <dd lang="en">{quest.target_expression}</dd>
            </div>
            <div>
              <dt>下一任务</dt>
              <dd>
                {quest.next_quest_id === null
                  ? "本次有限任务已完成"
                  : QUEST_LABELS[quest.next_quest_id]}
              </dd>
            </div>
            <div>
              <dt>设备状态</dt>
              <dd>
                {deliveryStatus === null
                  ? "暂无设备动作"
                  : DELIVERY_LABELS[deliveryStatus]}
              </dd>
            </div>
          </dl>
          <div className="virtual-inventory">
            <h3>故事中的虚拟道具</h3>
            {quest.inventory.length === 0 ? (
              <p className="secondary-text">暂时还没有虚拟道具。</p>
            ) : (
              <ul aria-label="虚拟道具清单">
                {quest.inventory.map((token) => (
                  <li key={token}>{INVENTORY_LABELS[token]}（虚拟）</li>
                ))}
              </ul>
            )}
          </div>
          <p className="helper-text">
            这里只展示服务端任务摘要，不能在网页中修改剧情、道具或学习状态。
            {state.questError ? " 本次刷新未成功，当前显示的是上次读取结果。" : ""}
          </p>
        </section>
      )}
      <section aria-label="学习记录">
        <div className="section-heading">
          <h2>{dashboard.mock ? "示例中的小进步" : "这次记录的小进步"}</h2>
          <span className="helper-text">
            记录日期 {dashboard.generated_at.slice(0, 10)}
          </span>
        </div>
        <div className="metric-grid">
          <MetricTile
            label="自己主动说"
            value={`${dashboard.metrics.spontaneous_speaking_count} 次`}
            detail="孩子自己发起的表达"
          />
          <MetricTile
            label="不用提示也能说"
            value={`${dashboard.metrics.unprompted_output_count} 次`}
            detail="没有额外提示的表达"
          />
          <MetricTile
            label="新出现的词"
            value={`${dashboard.metrics.new_words.length} 个`}
            detail={
              dashboard.metrics.new_words.join(" · ") || "还在积累，不着急"
            }
          />
        </div>
        <p className="helper-text">
          不同记录可能重叠，不需要把次数相加，也不必和其他孩子比较。
        </p>
      </section>
      <aside className="device-note">
        <div>
          <strong>
            {dashboard.device.online ? "设备已连接" : "设备尚未连接"}
          </strong>
          <p>
            {dashboard.mock
              ? "体验版无需连接设备，也能查看所有示例页面。"
              : "你仍可查看记录；设备连接后才能开始设备互动。"}
          </p>
        </div>
        <button className="secondary-button" onClick={onDevice}>
          查看设备
        </button>
      </aside>
    </>
  );
}
