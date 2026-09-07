import SwiftUI

struct TodayView: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationStack {
            Group {
                switch model.phase {
                case .idle, .loading:
                    loadingView
                case .offline:
                    offlineView
                case .ready:
                    if let dashboard = model.dashboard {
                        dashboardView(dashboard)
                    } else {
                        emptyView
                    }
                }
            }
            .navigationTitle("今天")
            .navigationBarTitleDisplayMode(.inline)
        }
        .softOrbitPage()
    }

    private func dashboardView(_ dashboard: DashboardSnapshot) -> some View {
        ScrollView {
            VStack(spacing: SoftOrbit.Spacing.large) {
                VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                    Text(dashboard.greeting)
                        .font(.largeTitle.bold())
                    Label(
                        dashboard.device.online ? "小P设备在线" : "小P设备暂时离线",
                        systemImage: dashboard.device.online ? "checkmark.circle.fill" : "moon.zzz.fill"
                    )
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(dashboard.device.online ? SoftOrbit.mint : .secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)

                VStack(spacing: SoftOrbit.Spacing.medium) {
                    PetOrbView(statusLabel: dashboard.pet.accessibilityLabel)
                    GlassCard {
                        Label(dashboard.highlight.text, systemImage: "star.fill")
                            .font(.headline)
                            .foregroundStyle(SoftOrbit.ink)
                            .accessibilityLabel("今日发现，\(dashboard.highlight.text)")
                    }
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: SoftOrbit.Spacing.medium) {
                        Text("接下来")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(SoftOrbit.lavender)
                        Text(dashboard.task.title)
                            .font(.title3.bold())
                        Text(dashboard.task.subtitle)
                            .foregroundStyle(.secondary)
                        ProgressView(value: dashboard.task.progress)
                            .tint(SoftOrbit.lavender)
                        Button(dashboard.task.actionLabel) {}
                            .buttonStyle(.borderedProminent)
                            .controlSize(.large)
                            .frame(minHeight: 44)
                    }
                }

                metrics(dashboard.metrics)
            }
            .padding(SoftOrbit.Spacing.large)
        }
        .refreshable { await model.load() }
    }

    private func metrics(_ metrics: DashboardMetrics) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: SoftOrbit.Spacing.small) {
                metricTiles(metrics)
            }
            VStack(spacing: SoftOrbit.Spacing.small) {
                metricTiles(metrics)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("今日三个学习指标")
    }

    @ViewBuilder
    private func metricTiles(_ metrics: DashboardMetrics) -> some View {
        MetricTile(label: AccessibilityCopy.todayMetricLabels[0], value: "\(metrics.spontaneousSpeakingCount)", detail: "今天")
        MetricTile(label: AccessibilityCopy.todayMetricLabels[1], value: "\(metrics.unpromptedOutputCount)", detail: "无需提示")
        MetricTile(label: AccessibilityCopy.todayMetricLabels[2], value: "\(metrics.newWords.count)", detail: metrics.newWords.joined(separator: " · "))
    }

    private var loadingView: some View {
        ScrollView {
            VStack(spacing: SoftOrbit.Spacing.large) {
                RoundedRectangle(cornerRadius: SoftOrbit.Radius.small).fill(.quaternary).frame(height: 58)
                Circle().fill(SoftOrbit.lavender.opacity(0.16)).frame(width: 210, height: 210)
                ForEach(0..<3, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: SoftOrbit.Radius.card).fill(.quaternary).frame(height: 120)
                }
            }
            .padding(SoftOrbit.Spacing.large)
            .redacted(reason: .placeholder)
            .accessibilityLabel("正在准备今天的家庭摘要")
        }
    }

    private var offlineView: some View {
        ContentUnavailableView {
            Label("小P正在休息", systemImage: "moon.stars")
        } description: {
            Text("暂时没连上家庭服务。已有内容不会丢失，可以稍后再试。")
        } actions: {
            Button("重新连接") { Task { await model.load() } }
                .buttonStyle(.borderedProminent)
                .frame(minHeight: 44)
        }
    }

    private var emptyView: some View {
        ContentUnavailableView(
            "今天还没有新记录",
            systemImage: "sparkles",
            description: Text("小P会在下一次真实互动后带回新的发现。")
        )
    }
}
