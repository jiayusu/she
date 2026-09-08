import SwiftUI

struct GlassCard<Content: View>: View {
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
                    .fill(SoftOrbit.surface)
                    .overlay {
                        RoundedRectangle(cornerRadius: SoftOrbit.Radius.card, style: .continuous)
                            .strokeBorder(SoftOrbit.ink.opacity(0.08), lineWidth: 1)
                    }
            }
            .shadow(color: Color.black.opacity(0.06), radius: 12, y: 5)
    }
}
