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
    private(set) var refreshError: AppAPIError?

    init(api: AppAPI) {
        self.api = api
        super.init()
    }

    func load() async {
        // A refresh over existing evidence must never blank the screen:
        // keep showing saved content and surface a gentle refresh error instead.
        let hasEvidence = dashboard != nil
        if !hasEvidence {
            phase = .loading
        }
        refreshError = nil
        do {
            let dashboard = try await api.dashboard()
            let report = try await api.weeklyReport()
            let settings = try await api.deviceSettings(deviceID: dashboard.device.deviceID)
            self.dashboard = dashboard
            self.weeklyReport = report
            self.deviceSettings = settings
            phase = .ready
        } catch let error as AppAPIError {
            if hasEvidence {
                refreshError = error
            } else {
                dashboard = nil
                weeklyReport = nil
                deviceSettings = nil
                transientError = error
                refreshError = error
                phase = .offline
            }
        } catch {
            if hasEvidence {
                refreshError = .invalidResponse
            } else {
                dashboard = nil
                weeklyReport = nil
                deviceSettings = nil
                transientError = .invalidResponse
                refreshError = .invalidResponse
                phase = .offline
            }
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
