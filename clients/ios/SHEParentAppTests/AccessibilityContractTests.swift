import XCTest
@testable import SHEParentApp

final class AccessibilityContractTests: XCTestCase {
    func testTodayMetricsUseTheApprovedThreeLabels() {
        XCTAssertEqual(
            AccessibilityCopy.todayMetricLabels,
            ["主动开口", "无提示输出", "新词"]
        )
    }

    func testPetAndDevicePrivacyCopyIsCentralized() {
        XCTAssertEqual(AccessibilityCopy.petFallbackSummary, "小P正在安静等待新的探险")
        XCTAssertEqual(AccessibilityCopy.cameraControl, "允许短时指向识别摄像头")
        XCTAssertEqual(AccessibilityCopy.rawAudioControl, "允许上传原始音频")
        XCTAssertEqual(AccessibilityCopy.eraseDemoData, "删除演示数据")
    }

    func testPrivacyCopyDoesNotClaimRealMutation() {
        XCTAssertTrue(AccessibilityCopy.demoPrivacyNotice.contains("演示"))
        XCTAssertFalse(AccessibilityCopy.demoPrivacyNotice.contains("已删除"))
    }
}
