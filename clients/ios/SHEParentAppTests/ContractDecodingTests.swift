import XCTest
@testable import SHEParentApp

final class ContractDecodingTests: XCTestCase {
    private let decoder = JSONDecoder()

    private func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: "json"))
        return try Data(contentsOf: url)
    }

    func testDashboardUsesCanonicalSnakeCaseMappings() throws {
        let dashboard = try decoder.decode(
            DashboardSnapshot.self,
            from: fixture("dashboard-snapshot")
        )

        XCTAssertEqual(dashboard.contractVersion, "1.0")
        XCTAssertTrue(dashboard.mock)
        XCTAssertEqual(dashboard.metrics.spontaneousSpeakingCount, 6)
        XCTAssertEqual(dashboard.metrics.unpromptedOutputCount, 3)
        XCTAssertEqual(dashboard.metrics.newWords, ["milk", "open"])
        XCTAssertEqual(dashboard.device.batteryPercent, 82)
    }

    func testWeeklyReportDecodesEvidenceAndMasteryStateMachine() throws {
        let report = try decoder.decode(
            WeeklyReport.self,
            from: fixture("weekly-report")
        )

        XCTAssertTrue(report.mock)
        XCTAssertEqual(report.evidence.first?.kind, .spontaneous)
        XCTAssertEqual(report.masteryUpdates.first?.from, .promptedOutput)
        XCTAssertEqual(report.masteryUpdates.first?.to, .spontaneousOutput)
    }

    func testDeviceAndParentConstraintsRemainDemoData() throws {
        let device = try decoder.decode(DeviceSettings.self, from: fixture("device-settings"))
        let constraints = try decoder.decode(
            ParentConstraints.self,
            from: fixture("parent-constraints")
        )

        XCTAssertTrue(device.mock)
        XCTAssertFalse(device.rawAudioUploadEnabled)
        XCTAssertTrue(constraints.mock)
        XCTAssertEqual(constraints.teachingPressure, .low)
    }
}
