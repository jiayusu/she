import XCTest
@testable import SHEParentApp

@MainActor
final class AppModelTests: XCTestCase {
    func testLoadMovesFromLoadingToReady() async {
        let api = MockAppAPI()
        api.delayNanoseconds = 50_000_000
        let model = AppModel(api: api)

        XCTAssertEqual(model.phase, .idle)
        let load = Task { await model.load() }
        await Task.yield()
        XCTAssertEqual(model.phase, .loading)
        await load.value

        XCTAssertEqual(model.phase, .ready)
        XCTAssertEqual(model.dashboard?.pet.name, "小P")
        XCTAssertTrue(model.dashboard?.mock == true)
    }

    func testLoadFailureUsesCalmOfflineState() async {
        let api = MockAppAPI(failure: .offline)
        let model = AppModel(api: api)

        await model.load()

        XCTAssertEqual(model.phase, .offline)
        XCTAssertNil(model.dashboard)
    }

    func testFailedRefreshKeepsEvidenceAndReportsRefreshError() async {
        let api = MockAppAPI()
        let model = AppModel(api: api)
        await model.load()
        let dashboard = model.dashboard
        api.failure = .offline

        await model.load()

        XCTAssertEqual(model.phase, .ready)
        XCTAssertEqual(model.dashboard, dashboard)
        XCTAssertEqual(model.refreshError, .offline)
        XCTAssertNil(model.transientError)
    }

    func testRefreshWithEvidenceDoesNotDropBackToSkeleton() async {
        let api = MockAppAPI()
        api.delayNanoseconds = 50_000_000
        let model = AppModel(api: api)
        await model.load()

        let refresh = Task { await model.load() }
        await Task.yield()
        XCTAssertEqual(model.phase, .ready)
        await refresh.value

        XCTAssertEqual(model.phase, .ready)
    }

    func testFailedSettingsPatchRollsBackOptimisticChange() async {
        let api = MockAppAPI()
        let model = AppModel(api: api)
        await model.load()
        let original = model.deviceSettings
        api.failure = .offline

        await model.updateDeviceSettings(DeviceSettingsPatch(volume: 12))

        XCTAssertEqual(model.deviceSettings, original)
        XCTAssertEqual(model.transientError, .offline)
    }

    func testAppModelHasNoMasteryMutationAPI() {
        let selectors = [
            "setMastery:", "updateMastery:", "saveMastery:", "overrideMastery:"
        ]
        for selector in selectors {
            XCTAssertFalse(AppModel.instancesRespond(to: NSSelectorFromString(selector)))
        }
    }
}
