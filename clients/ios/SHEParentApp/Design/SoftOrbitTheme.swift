import SwiftUI
import UIKit

enum SoftOrbit {
    enum Spacing {
        static let xSmall: CGFloat = 6
        static let small: CGFloat = 10
        static let medium: CGFloat = 16
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
    }

    enum Radius {
        static let small: CGFloat = 10
        static let card: CGFloat = 14
        static let hero: CGFloat = 20
    }

    /// Motion vocabulary for 手感: every animation is state-driven with an
    /// explicit value parameter or scoped inside withAnimation, never unscoped,
    /// and all of it yields to Reduce Motion at the call site.
    enum Motion {
        static let quick = 0.22
        static let breathing = 3.8

        /// Seconds between staggered card entrances.
        static let stagger: Double = 0.07

        /// Button press and release: quick with a hint of bounce.
        static let press = Animation.snappy(duration: 0.26, extraBounce: 0.12)

        /// Cards rising into place on first appearance.
        static let entrance = Animation.smooth(duration: 0.55, extraBounce: 0.06)

        /// Phase swaps, banners, and content changes: settled, never showy.
        static let settle = Animation.smooth(duration: 0.4)
    }

    static let mist = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.08, green: 0.09, blue: 0.10, alpha: 1)
                : UIColor(red: 0.965, green: 0.95, blue: 0.91, alpha: 1)
        }
    )
    static let surface = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.14, green: 0.15, blue: 0.16, alpha: 1)
                : UIColor(red: 0.995, green: 0.99, blue: 0.97, alpha: 1)
        }
    )
    static let lavender = Color(red: 0.90, green: 0.29, blue: 0.23)
    static let lavenderLight = Color(red: 1.0, green: 0.66, blue: 0.53)
    static let mint = Color(red: 0.10, green: 0.55, blue: 0.48)
    static let warm = Color(red: 0.93, green: 0.64, blue: 0.18)
    static let ink = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.94, green: 0.94, blue: 0.99, alpha: 1)
                : UIColor(red: 0.12, green: 0.11, blue: 0.10, alpha: 1)
        }
    )

    static let pageGradient = Color.clear
}

enum AccessibilityCopy {
    static let todayMetricLabels = ["主动开口", "无提示输出", "新词"]
    static let petFallbackSummary = "小P正在安静等待新的探险"
    static let cameraControl = "允许短时指向识别摄像头"
    static let rawAudioControl = "允许上传原始音频"
    static let eraseDemoData = "删除演示数据"
    static let demoPrivacyNotice = "当前为演示家庭；导出与删除只演示流程，不会修改真实学习存储。"
    static let staleContentBanner = "刚刚没有刷新成功，现在显示的是已保存的内容"
    static let parentGoalSaving = "正在保存"
    static let parentGoalSaved = "已保存到家庭计划"
    static let parentGoalSaveFailed = "暂时没有保存成功"
}

struct SoftOrbitPage: ViewModifier {
    func body(content: Content) -> some View {
        content
            .foregroundStyle(SoftOrbit.ink)
            .background(SoftOrbit.mist.ignoresSafeArea())
            .tint(SoftOrbit.lavender)
    }
}

/// Gentle opacity breathing for loading skeletons. Stops under Reduce Motion.
private struct SkeletonPulse: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var pulsing = false

    func body(content: Content) -> some View {
        content
            .opacity(pulsing && !reduceMotion ? 0.55 : 1)
            .onAppear { pulsing = true }
            .animation(
                reduceMotion ? nil : .easeInOut(duration: 1.2).repeatForever(autoreverses: true),
                value: pulsing
            )
    }
}

extension View {
    func softOrbitPage() -> some View {
        modifier(SoftOrbitPage())
    }

    func softOrbitPulse() -> some View {
        modifier(SkeletonPulse())
    }
}
