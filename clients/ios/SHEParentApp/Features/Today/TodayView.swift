import SwiftUI

struct TodayView: View {
    @Bindable var model: AppModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

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
            .animation(
                reduceMotion ? nil : SoftOrbit.Motion.settle,
                value: model.phase
            )
            .navigationTitle("今天")
            .navigationBarTitleDisplayMode(.inline)
        }
        .softOrbitPage()
    }

    private func dashboardView(_ dashboard: DashboardSnapshot) -> some View {
        ScrollView {
            VStack(spacing: SoftOrbit.Spacing.large) {
                if model.refreshError != nil {
                    staleBanner
                }

                VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                    Text("家庭学习台")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(SoftOrbit.lavender)
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
                .softOrbitEntrance(index: 0)

                GlassCard {
                    HStack(alignment: .center, spacing: SoftOrbit.Spacing.medium) {
                        PetOrbView(statusLabel: dashboard.pet.accessibilityLabel, size: 132)
                        VStack(alignment: .leading, spacing: SoftOrbit.Spacing.small) {
                            Text("小P的观察")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                            Label(dashboard.highlight.text, systemImage: "star.fill")
                                .font(.headline.weight(.semibold))
                                .foregroundStyle(SoftOrbit.ink)
                                .accessibilityLabel("今日发现，\(dashboard.highlight.text)")
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .softOrbitEntrance(index: 1)

                if model.isQuestStateConfigured {
                    questCard(model.questSummary)
                        .softOrbitEntrance(index: 2)
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: SoftOrbit.Spacing.medium) {
                        Text("下一步")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(SoftOrbit.lavender)
                        Text(dashboard.task.title)
                            .font(.title3.bold())
                        Text(dashboard.task.subtitle)
                            .foregroundStyle(.secondary)
                        ProgressView(value: dashboard.task.progress)
                            .tint(SoftOrbit.mint)
                        Button(dashboard.task.actionLabel) {}
                            .buttonStyle(SoftOrbitPrimaryButtonStyle())
                    }
                }
                .softOrbitEntrance(index: 3)

                metrics(dashboard.metrics)
                    .softOrbitEntrance(index: 4)
            }
            .animation(
                reduceMotion ? nil : SoftOrbit.Motion.settle,
                value: model.refreshError
            )
            .padding(SoftOrbit.Spacing.large)
        }
        .refreshable { await model.load() }
    }

    private func questCard(_ summary: RpgQuestSummary?) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: SoftOrbit.Spacing.medium) {
                HStack {
                    Label("现实语言任务", systemImage: "map.fill")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(SoftOrbit.mint)
                    Spacer()
                    Text("只读")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.secondary)
                }

                if let quest = summary?.quest {
                    Text(questTitle(quest.nodeID))
                        .font(.title3.bold())
                    Label(phaseLabel(quest.phase), systemImage: phaseIcon(quest.phase))
                        .font(.subheadline.weight(.medium))
                    LabeledContent("现实角色", value: quest.worldRole.rawValue)
                    LabeledContent("目标表达", value: quest.targetExpression)
                    if !quest.inventory.isEmpty {
                        LabeledContent(
                            "已经获得",
                            value: quest.inventory.map(inventoryLabel).joined(separator: "、")
                        )
                    }
                    if model.questRefreshError != nil {
                        Label("状态暂时未刷新，当前显示上次保存的任务", systemImage: "arrow.clockwise")
                            .font(.footnote)
                            .foregroundStyle(SoftOrbit.warm)
                    }
                } else if model.questRefreshError != nil {
                    Label("暂时读不到设备上的剧情状态", systemImage: "wifi.exclamationmark")
                        .foregroundStyle(.secondary)
                } else {
                    Label("当前没有进行中的现实语言任务", systemImage: "sparkles")
                        .foregroundStyle(.secondary)
                }
            }
            .accessibilityElement(children: .combine)
        }
    }

    private func questTitle(_ node: RpgNodeID) -> String {
        switch node {
        case .collectMilk: "寻找野餐牛奶"
        case .findRedCup: "寻找红色杯子"
        case .picnicReady: "野餐准备完成"
        }
    }

    private func phaseLabel(_ phase: RpgQuestPhase) -> String {
        switch phase {
        case .seekingObject: "等待孩子找到现实物体"
        case .confirmingObject: "正在确认孩子指向的物体"
        case .presenting: "角色正在给出语言任务"
        case .awaitingSpeech: "等待孩子开口改变剧情"
        case .resolving: "正在判定这次语言行动"
        case .paused: "任务已暂停，稍后可继续"
        case .deliveryFailed: "上次话术未送达，设备将安全重试"
        case .completed: "任务已经完成"
        }
    }

    private func phaseIcon(_ phase: RpgQuestPhase) -> String {
        switch phase {
        case .seekingObject, .confirmingObject: "viewfinder"
        case .presenting, .awaitingSpeech: "quote.bubble"
        case .resolving: "ellipsis.circle"
        case .paused: "pause.circle"
        case .deliveryFailed: "exclamationmark.arrow.triangle.2.circlepath"
        case .completed: "checkmark.seal.fill"
        }
    }

    private func inventoryLabel(_ item: RpgInventoryItem) -> String {
        switch item {
        case .milkToken: "牛奶"
        case .redCupToken: "红色杯子"
        }
    }

    private var staleBanner: some View {
        Label(AccessibilityCopy.staleContentBanner, systemImage: "wifi.exclamationmark")
            .font(.footnote.weight(.medium))
            .foregroundStyle(SoftOrbit.warm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(SoftOrbit.Spacing.small)
            .background(
                SoftOrbit.surface,
                in: RoundedRectangle(cornerRadius: SoftOrbit.Radius.small, style: .continuous)
            )
            .overlay {
                RoundedRectangle(cornerRadius: SoftOrbit.Radius.small, style: .continuous)
                    .strokeBorder(SoftOrbit.warm.opacity(0.35), lineWidth: 1)
            }
            .transition(.move(edge: .top).combined(with: .opacity))
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
                RoundedRectangle(cornerRadius: SoftOrbit.Radius.small, style: .continuous).fill(.quaternary).frame(height: 58)
                Circle().fill(SoftOrbit.lavender.opacity(0.12)).frame(width: 150, height: 150)
                ForEach(0..<3, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: SoftOrbit.Radius.card, style: .continuous).fill(.quaternary).frame(height: 120)
                }
            }
            .padding(SoftOrbit.Spacing.large)
            .redacted(reason: .placeholder)
            .softOrbitPulse()
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
                .buttonStyle(SoftOrbitPrimaryButtonStyle())
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
