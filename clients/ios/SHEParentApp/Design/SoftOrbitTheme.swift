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
        static let small: CGFloat = 14
        static let card: CGFloat = 24
        static let hero: CGFloat = 32
    }

    enum Motion {
        static let quick = 0.22
        static let breathing = 3.8
    }

    static let mist = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.07, green: 0.08, blue: 0.13, alpha: 1)
                : UIColor(red: 0.965, green: 0.968, blue: 0.99, alpha: 1)
        }
    )
    static let surface = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.12, green: 0.13, blue: 0.20, alpha: 1)
                : UIColor.white
        }
    )
    static let lavender = Color(red: 0.48, green: 0.43, blue: 0.92)
    static let lavenderLight = Color(red: 0.76, green: 0.72, blue: 1.0)
    static let mint = Color(red: 0.40, green: 0.79, blue: 0.69)
    static let warm = Color(red: 1.0, green: 0.72, blue: 0.45)
    static let ink = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.94, green: 0.94, blue: 0.99, alpha: 1)
                : UIColor(red: 0.10, green: 0.11, blue: 0.18, alpha: 1)
        }
    )

    static let pageGradient = LinearGradient(
        colors: [mist, lavender.opacity(0.08), mint.opacity(0.06)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}

enum AccessibilityCopy {
    static let todayMetricLabels = ["主动开口", "无提示输出", "新词"]
    static let petFallbackSummary = "小P正在安静等待新的探险"
    static let cameraControl = "允许短时指向识别摄像头"
    static let rawAudioControl = "允许上传原始音频"
    static let eraseDemoData = "删除演示数据"
    static let demoPrivacyNotice = "当前为演示家庭；导出与删除只演示流程，不会修改真实学习存储。"
}

struct SoftOrbitPage: ViewModifier {
    func body(content: Content) -> some View {
        content
            .foregroundStyle(SoftOrbit.ink)
            .background(SoftOrbit.pageGradient.ignoresSafeArea())
            .tint(SoftOrbit.lavender)
    }
}

extension View {
    func softOrbitPage() -> some View {
        modifier(SoftOrbitPage())
    }
}
