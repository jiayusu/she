import Foundation

enum AppAPIError: Error, Equatable, Sendable {
    case offline
    case invalidResponse
    case incompatibleContract
    case server(code: String)
}

@MainActor
protocol AppAPI: AnyObject {
    func dashboard() async throws -> DashboardSnapshot
    func weeklyReport() async throws -> WeeklyReport
    func deviceSettings(deviceID: String) async throws -> DeviceSettings
    func updateDeviceSettings(deviceID: String, patch: DeviceSettingsPatch) async throws -> DeviceSettings
    func updateParentConstraints(_ update: ParentConstraintsUpdate) async throws -> ParentConstraints
    func requestPrivacyExport() async throws -> PrivacyOperation
    func requestPrivacyErase() async throws -> PrivacyOperation
}
