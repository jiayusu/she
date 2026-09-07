import SwiftUI

struct ReportsView: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationStack {
            ScrollView {
                if let report = model.weeklyReport {
                    VStack(spacing: SoftOrbit.Spacing.large) {
                        GlassCard {
                            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                                Text("本周正在发生")
                                    .font(.title2.bold())
                                Text(report.currentFocus)
                                    .font(.headline)
                                Label("提示变化 \(report.scaffoldTrend)", systemImage: "arrow.down.right.circle")
                                    .foregroundStyle(SoftOrbit.mint)
                            }
                        }

                        GlassCard {
                            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.medium) {
                                Text("有证据的成长")
                                    .font(.headline)
                                ForEach(report.evidence) { evidence in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("“\(evidence.expression)”")
                                            .font(.title3.bold())
                                        Text(evidence.kind == .spontaneous ? "主动出现" : "在支持下出现")
                                            .foregroundStyle(.secondary)
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            }
                        }

                        GlassCard {
                            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                                Text("跨场景使用")
                                    .font(.headline)
                                Text(report.transferredWords.isEmpty ? "还在积累证据" : report.transferredWords.joined(separator: " · "))
                                    .font(.title3.weight(.semibold))
                            }
                        }
                    }
                    .padding(SoftOrbit.Spacing.large)
                } else {
                    ContentUnavailableView("还没有周报", systemImage: "chart.line.uptrend.xyaxis")
                }
            }
            .navigationTitle("成长")
        }
        .softOrbitPage()
    }
}
