import Foundation

private struct GatewayErrorEnvelope: Decodable {
    struct GatewayError: Decodable {
        let code: String
    }

    let error: GatewayError
}

@MainActor
final class LiveAppAPI: AppAPI {
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    init(baseURL: URL, credentialStore: KeychainStore = KeychainStore()) {
        self.baseURL = baseURL
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 8
        configuration.timeoutIntervalForResource = 15
        if let credential = credentialStore.readCredential() {
            configuration.httpAdditionalHeaders = ["Authorization": "Bearer \(credential)"]
        }
        self.session = URLSession(configuration: configuration)
    }

    func dashboard() async throws -> DashboardSnapshot {
        try await request("v1/dashboard")
    }

    func questState(identity: RpgReadIdentity) async throws -> RpgQuestSummary {
        var components = URLComponents(
            url: baseURL.appending(path: "v1/rpg/state"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [
            URLQueryItem(name: "child_id", value: identity.childID),
            URLQueryItem(name: "session_id", value: identity.sessionID),
        ]
        guard let url = components?.url else { throw AppAPIError.invalidResponse }
        let summary: RpgQuestSummary = try await request(url)
        guard summary.isCanonicalProjection else { throw AppAPIError.invalidResponse }
        return summary
    }

    func weeklyReport() async throws -> WeeklyReport {
        try await request("v1/reports/weekly")
    }

    func deviceSettings(deviceID: String) async throws -> DeviceSettings {
        try await request("v1/devices/\(deviceID)")
    }

    func updateDeviceSettings(deviceID: String, patch: DeviceSettingsPatch) async throws -> DeviceSettings {
        try await request("v1/devices/\(deviceID)", method: "PATCH", body: patch)
    }

    func updateParentConstraints(_ update: ParentConstraintsUpdate) async throws -> ParentConstraints {
        try await request("v1/parent-constraints", method: "PUT", body: update)
    }

    func requestPrivacyExport() async throws -> PrivacyOperation {
        try await request("v1/privacy/export", method: "POST")
    }

    func requestPrivacyErase() async throws -> PrivacyOperation {
        try await request("v1/privacy/erase", method: "POST")
    }

    private func request<Response: Decodable & VersionedContract>(
        _ path: String,
        method: String = "GET"
    ) async throws -> Response {
        try await request(baseURL.appending(path: path), method: method, bodyData: nil)
    }

    private func request<Response: Decodable & VersionedContract, Body: Encodable>(
        _ path: String,
        method: String,
        body: Body
    ) async throws -> Response {
        try await request(
            baseURL.appending(path: path),
            method: method,
            bodyData: encoder.encode(body)
        )
    }

    private func request<Response: Decodable & VersionedContract>(
        _ url: URL,
        method: String = "GET"
    ) async throws -> Response {
        try await request(url, method: method, bodyData: nil)
    }

    private func request<Response: Decodable & VersionedContract>(
        _ url: URL,
        method: String,
        bodyData: Data?
    ) async throws -> Response {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = bodyData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if bodyData != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw AppAPIError.offline
        }
        guard let http = response as? HTTPURLResponse else {
            throw AppAPIError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            if let envelope = try? decoder.decode(GatewayErrorEnvelope.self, from: data) {
                throw AppAPIError.server(code: envelope.error.code)
            }
            throw AppAPIError.invalidResponse
        }
        guard let decoded = try? decoder.decode(Response.self, from: data) else {
            throw AppAPIError.invalidResponse
        }
        guard decoded.contractVersion == supportedContractVersion else {
            throw AppAPIError.incompatibleContract
        }
        return decoded
    }
}
