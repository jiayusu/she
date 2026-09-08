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

    func testStaleContentBannerStaysHonestAboutFreshness() {
        XCTAssertTrue(AccessibilityCopy.staleContentBanner.contains("没有刷新成功"))
        XCTAssertTrue(AccessibilityCopy.staleContentBanner.contains("已保存"))
    }

    func testParentGoalSaveCopyUsesCalmOutcomeWording() {
        XCTAssertEqual(AccessibilityCopy.parentGoalSaving, "正在保存")
        XCTAssertEqual(AccessibilityCopy.parentGoalSaved, "已保存到家庭计划")
        XCTAssertEqual(AccessibilityCopy.parentGoalSaveFailed, "暂时没有保存成功")
    }
}
