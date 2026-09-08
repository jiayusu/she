import type { AppState } from "@/state/appModel";

export function ReportsView({ state }: { state: AppState }) {
  const report = state.weeklyReport;
  if (!report) {
    return (
      <div className="status-placeholder">
        <h2>还没有周报</h2>
        <p>第一周的证据积累完成后，这里会展示有证据的成长。</p>
      </div>
    );
  }

  return (
    <>
      <section className="glass-card">
        <p className="card-caption">学习证据 · {report.period_start} 至 {report.period_end}</p>
        <h2 className="card-title">本周正在发生</h2>
        <p style={{ fontSize: 17, fontWeight: 600, margin: 0 }}>{report.current_focus}</p>
        <span style={{ color: "var(--so-mint)", fontWeight: 600, fontSize: 14 }}>
          ↘ 提示变化 {report.scaffold_trend}
        </span>
      </section>

      <section className="glass-card">
        <h3 className="card-title" style={{ fontSize: 17 }}>有证据的成长</h3>
        {report.evidence.length === 0 ? (
          <p className="secondary-text">本周还在积累证据。</p>
        ) : (
          report.evidence.map((item) => (
            <div className="evidence-item" key={item.evidence_id}>
              <span aria-hidden="true">{item.kind === "spontaneous" ? "🎙" : "✨"}</span>
              <div>
                <p className="evidence-expression">“{item.expression}”</p>
                <span className="evidence-kind">
                  {item.kind === "spontaneous" ? "主动出现" : "在支持下出现"}
                </span>
              </div>
            </div>
          ))
        )}
      </section>

      <section className="glass-card">
        <h3 className="card-title" style={{ fontSize: 17 }}>跨场景使用</h3>
        <p style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          {report.transferred_words.length === 0
            ? "还在积累证据"
            : report.transferred_words.join(" · ")}
        </p>
        <p className="secondary-text" style={{ fontSize: 13 }}>
          同一个表达在不同生活场景再次出现时，才算真正长进。
        </p>
      </section>
    </>
  );
}
