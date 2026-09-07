import Foundation

@MainActor
final class MockAppAPI: AppAPI {
    var failure: AppAPIError?
    var delayNanoseconds: UInt64 = 0
    private var settings = DemoData.device
    private var constraints = DemoData.constraints

    init(failure: AppAPIError? = nil) {
        self.failure = failure
    }

    func dashboard() async throws -> DashboardSnapshot {
        try await prepare()
        return DemoData.dashboard
    }

    func weeklyReport() async throws -> WeeklyReport {
        try await prepare()
        return DemoData.report
    }

    func deviceSettings(deviceID: String) async throws -> DeviceSettings {
        try await prepare()
        return settings
    }

    func updateDeviceSettings(deviceID: String, patch: DeviceSettingsPatch) async throws -> DeviceSettings {
        try await prepare()
        if let volume = patch.volume { settings.volume = volume }
        if let value = patch.ledEnabled { settings.ledEnabled = value }
        if let value = patch.cameraEnabled { settings.cameraEnabled = value }
        if let value = patch.rawAudioUploadEnabled { settings.rawAudioUploadEnabled = value }
        return settings
    }

    func updateParentConstraints(_ update: ParentConstraintsUpdate) async throws -> ParentConstraints {
        try await prepare()
        constraints.sessionBudgetSeconds = update.sessionBudgetSeconds
        constraints.preferredTopics = update.preferredTopics
        constraints.avoidTopics = update.avoidTopics
        constraints.nextDayContext = update.nextDayContext
        constraints.teachingPressure = update.teachingPressure
        return constraints
    }

    func requestPrivacyExport() async throws -> PrivacyOperation {
        try await prepare()
        return PrivacyOperation(
            contractVersion: supportedContractVersion,
            operation: "export",
            status: "accepted_demo_only",
            mock: true,
            storeMutated: false
        )
    }

    func requestPrivacyErase() async throws -> PrivacyOperation {
        try await prepare()
        return PrivacyOperation(
            contractVersion: supportedContractVersion,
            operation: "erase",
            status: "accepted_demo_only",
            mock: true,
            storeMutated: false
        )
    }

    private func prepare() async throws {
        if delayNanoseconds > 0 {
            try await Task.sleep(nanoseconds: delayNanoseconds)
        }
        if let failure { throw failure }
    }
}

private enum DemoData {
    static let device = DeviceSettings(
        contractVersion: "1.0", deviceID: "rx5-demo-001", name: "小P 设备",
        online: false, batteryPercent: 82, volume: 58, ledEnabled: true,
        cameraEnabled: true, rawAudioUploadEnabled: false,
        firmwareVersion: "demo-0.1.0", lastSeenAt: "2026-09-07T10:00:00Z", mock: true
    )
    static let constraints = ParentConstraints(
        contractVersion: "1.0", sessionBudgetSeconds: 600,
        preferredTopics: ["animals", "food"], avoidTopics: [],
        nextDayContext: "明天去动物园", teachingPressure: .low,
        updatedAt: "2026-09-07T10:00:00Z", mock: true
    )
    static let dashboard = DashboardSnapshot(
        contractVersion: "1.0", generatedAt: "2026-09-07T10:00:00Z", greeting: "早上好，苏妈妈",
        pet: PetSummary(name: "小P", mood: "delighted", accessibilityLabel: "小P很开心，带回了一颗新星星"),
        highlight: HighlightSummary(text: "“milk” 今天第一次主动出现", evidenceID: "evidence-milk-001"),
        task: TodayTask(title: "把 “I want…” 说得更自然", subtitle: "冰箱星球的小任务", progress: 0.64, actionLabel: "查看今日探险"),
        metrics: DashboardMetrics(spontaneousSpeakingCount: 6, unpromptedOutputCount: 3, newWords: ["milk", "open"]),
        device: DeviceSummary(deviceID: "rx5-demo-001", name: "小P 设备", online: false, batteryPercent: 82),
        mock: true
    )
    static let report = WeeklyReport(
        contractVersion: "1.0", periodStart: "2026-09-01", periodEnd: "2026-09-07",
        spontaneousSpeakingCount: 32, promptedSpeakingCount: 17,
        newSpontaneousWords: ["milk", "open"], transferredWords: ["apple"],
        currentFocus: "主动表达食物需求", scaffoldTrend: "L3 → L2",
        evidence: [LearningEvidence(evidenceID: "evidence-milk-001", kind: .spontaneous, expression: "milk", occurredAt: "2026-09-07T09:30:00Z", confidence: 0.96)],
        masteryUpdates: [MasteryUpdate(expression: "milk", from: .promptedOutput, to: .spontaneousOutput, evidenceIDs: ["evidence-milk-001"])],
        mock: true
    )
}
