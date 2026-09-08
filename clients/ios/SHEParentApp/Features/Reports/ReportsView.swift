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
                                Text("学习证据")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(SoftOrbit.lavender)
                                Text("本周正在发生")
                                    .font(.title2.bold())
                                Text(report.currentFocus)
                                    .font(.headline)
                                Label("提示变化 \(report.scaffoldTrend)", systemImage: "arrow.down.right.circle")
                                    .foregroundStyle(SoftOrbit.mint)
                            }
                        }
                        .softOrbitEntrance(index: 0)

                        GlassCard {
                            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.medium) {
                                Text("有证据的成长")
                                    .font(.headline)
                                ForEach(report.evidence) { evidence in
                                    HStack(alignment: .firstTextBaseline, spacing: SoftOrbit.Spacing.small) {
                                        Image(systemName: evidence.kind == .spontaneous ? "mic.fill" : "sparkles")
                                            .foregroundStyle(evidence.kind == .spontaneous ? SoftOrbit.mint : SoftOrbit.warm)
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text("“\(evidence.expression)”")
                                                .font(.title3.bold())
                                            Text(evidence.kind == .spontaneous ? "主动出现" : "在支持下出现")
                                                .font(.subheadline)
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            }
                        }
                        .softOrbitEntrance(index: 1)

                        GlassCard {
                            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                                Text("跨场景使用")
                                    .font(.headline)
                                Text(report.transferredWords.isEmpty ? "还在积累证据" : report.transferredWords.joined(separator: " · "))
                                    .font(.title3.weight(.semibold))
                                Text("同一个表达在不同生活场景再次出现时，才算真正长进。")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .softOrbitEntrance(index: 2)
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
