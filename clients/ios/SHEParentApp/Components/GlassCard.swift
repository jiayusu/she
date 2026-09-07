import SwiftUI

struct GlassCard<Content: View>: View {
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.colorSchemeContrast) private var contrast
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding(SoftOrbit.Spacing.large)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: SoftOrbit.Radius.card, style: .continuous)
                    .fill(cardFill)
                    .overlay {
                        RoundedRectangle(cornerRadius: SoftOrbit.Radius.card, style: .continuous)
                            .strokeBorder(.white.opacity(reduceTransparency ? 0.12 : 0.42), lineWidth: 1)
                    }
            }
            .shadow(color: SoftOrbit.lavender.opacity(0.10), radius: 18, y: 9)
    }

    private var cardFill: AnyShapeStyle {
        if reduceTransparency || contrast == .increased {
            return AnyShapeStyle(SoftOrbit.surface)
        }
        return AnyShapeStyle(.ultraThinMaterial)
    }
}
