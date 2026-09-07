import Foundation
import Observation

enum AppPhase: Equatable {
    case idle
    case loading
    case ready
    case offline
}

@Observable
@MainActor
final class AppModel: NSObject {
    private let api: AppAPI

    private(set) var phase: AppPhase = .idle
    private(set) var dashboard: DashboardSnapshot?
    private(set) var weeklyReport: WeeklyReport?
    private(set) var deviceSettings: DeviceSettings?
    private(set) var parentConstraints: ParentConstraints?
    private(set) var transientError: AppAPIError?

    init(api: AppAPI) {
        self.api = api
        super.init()
    }

    func load() async {
        phase = .loading
        transientError = nil
        do {
            let dashboard = try await api.dashboard()
            let report = try await api.weeklyReport()
            let settings = try await api.deviceSettings(deviceID: dashboard.device.deviceID)
            self.dashboard = dashboard
            self.weeklyReport = report
            self.deviceSettings = settings
            phase = .ready
        } catch let error as AppAPIError {
            dashboard = nil
            weeklyReport = nil
            deviceSettings = nil
            transientError = error
            phase = .offline
        } catch {
            transientError = .invalidResponse
            phase = .offline
        }
    }

    func updateDeviceSettings(_ patch: DeviceSettingsPatch) async {
        guard let current = deviceSettings else { return }
        let previous = current
        var optimistic = current
        if let volume = patch.volume { optimistic.volume = volume }
        if let value = patch.ledEnabled { optimistic.ledEnabled = value }
        if let value = patch.cameraEnabled { optimistic.cameraEnabled = value }
        if let value = patch.rawAudioUploadEnabled { optimistic.rawAudioUploadEnabled = value }
        deviceSettings = optimistic
        transientError = nil
        do {
            deviceSettings = try await api.updateDeviceSettings(deviceID: current.deviceID, patch: patch)
        } catch let error as AppAPIError {
            deviceSettings = previous
            transientError = error
        } catch {
            deviceSettings = previous
            transientError = .invalidResponse
        }
    }

    func updateParentConstraints(_ update: ParentConstraintsUpdate) async {
        do {
            parentConstraints = try await api.updateParentConstraints(update)
        } catch let error as AppAPIError {
            transientError = error
        } catch {
            transientError = .invalidResponse
        }
    }

    func requestPrivacyExport() async throws -> PrivacyOperation {
        try await api.requestPrivacyExport()
    }

    func requestPrivacyErase() async throws -> PrivacyOperation {
        try await api.requestPrivacyErase()
    }
}
