import type { AppState } from "@/state/appModel";
const evidenceLabels = {
  spontaneous: "孩子自己主动说",
  prompted: "有提示时说出来",
  transferred: "换个场景也会用",
  comprehension: "听懂了这个表达",
};
export function ReportsView({ state }: { state: AppState }) {
  const report = state.weeklyReport;
  if (!report)
    return (
      <div className="status-placeholder">
        <h1>还没有成长记录</h1>
        <p>有了新的互动记录，我们再一起看看。没有记录不代表没有进步。</p>
      </div>
    );
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">看见尝试，而不是分数</p>
          <h1>每一点进步，都值得看见</h1>
          <p className="secondary-text">
            {report.period_start} — {report.period_end}
            {report.mock ? " · 示例周报" : ""}
          </p>
        </div>
      </header>
      <section className="glass-card">
        <p className="eyebrow">这周正在练习</p>
        <h2>{report.current_focus}</h2>
        <p className="secondary-text">
          关注孩子在什么情况下愿意表达，而不只是说了多少次。
        </p>
        <details>
          <summary>怎么看“提示变化”？</summary>
          <p>
            提示是小P给予的帮助，不是孩子的成绩。不同的提示方式适合不同情境，级别变化不等于能力升降。
          </p>
          <p className="helper-text">
            记录中的提示标记：{report.scaffold_trend}
          </p>
        </details>
      </section>
      <div className="report-grid">
        <section className="glass-card">
          <h2>这些表达出现过</h2>
          {report.evidence.length ? (
            report.evidence.map((item) => (
              <div className="evidence-item" key={item.evidence_id}>
                <span className="word-icon" aria-hidden="true">
                  ✦
                </span>
                <div>
                  <p className="evidence-expression">{item.expression}</p>
                  <p className="secondary-text">{evidenceLabels[item.kind]}</p>
                </div>
              </div>
            ))
          ) : (
            <p className="secondary-text">
              还没有足够的记录，继续按自己的节奏来。
            </p>
          )}
        </section>
        <section className="glass-card">
          <h2>换个场景，也用到了</h2>
          <div className="word-chips">
            {report.transferred_words.map((word) => (
              <span key={word}>{word}</span>
            ))}
          </div>
          <p className="secondary-text">
            {report.transferred_words.length
              ? "这些词在不同情境中再次出现，是值得留意的小发现。"
              : "暂时没有这类记录。熟悉一个表达需要时间。"}
          </p>
          <p className="helper-text">
            一次记录只是一个线索，不代表已经完全掌握。
          </p>
        </section>
      </div>
    </>
  );
}
