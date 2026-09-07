import SwiftUI

struct PetOrbView: View {
    let statusLabel: String
    var size: CGFloat = 210

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var breathing = false

    var body: some View {
        ZStack {
            Ellipse()
                .fill(SoftOrbit.lavender.opacity(0.16))
                .frame(width: size * 0.72, height: size * 0.18)
                .blur(radius: reduceTransparency ? 1 : 9)
                .offset(y: size * 0.47)

            Circle()
                .fill(
                    RadialGradient(
                        colors: [SoftOrbit.lavenderLight, SoftOrbit.lavender, Color(red: 0.28, green: 0.25, blue: 0.68)],
                        center: UnitPoint(x: 0.34, y: 0.25),
                        startRadius: 2,
                        endRadius: size * 0.62
                    )
                )
                .overlay(alignment: .topLeading) {
                    Ellipse()
                        .fill(.white.opacity(reduceTransparency ? 0.48 : 0.68))
                        .frame(width: size * 0.34, height: size * 0.18)
                        .rotationEffect(.degrees(-28))
                        .blur(radius: reduceTransparency ? 0 : 2)
                        .offset(x: size * 0.17, y: size * 0.14)
                }
                .overlay {
                    face
                }
                .overlay {
                    Circle()
                        .strokeBorder(.white.opacity(0.20), lineWidth: 2)
                }
                .shadow(color: SoftOrbit.lavender.opacity(0.26), radius: 24, y: 15)
                .scaleEffect(breathing && !reduceMotion ? 1.025 : 1)
                .animation(
                    reduceMotion ? nil : .easeInOut(duration: SoftOrbit.Motion.breathing).repeatForever(autoreverses: true),
                    value: breathing
                )
        }
        .frame(width: size, height: size * (dynamicTypeSize.isAccessibilitySize ? 1.08 : 1))
        .onAppear { breathing = !reduceMotion }
        .onChange(of: reduceMotion) { _, value in breathing = !value }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(statusLabel)
    }

    private var face: some View {
        VStack(spacing: size * 0.09) {
            HStack(spacing: size * 0.22) {
                Circle().fill(SoftOrbit.ink.opacity(0.82)).frame(width: size * 0.075)
                Circle().fill(SoftOrbit.ink.opacity(0.82)).frame(width: size * 0.075)
            }
            Capsule()
                .fill(SoftOrbit.ink.opacity(0.78))
                .frame(width: size * 0.18, height: size * 0.055)
                .overlay(alignment: .bottom) {
                    Capsule().fill(Color.pink.opacity(0.75)).frame(width: size * 0.09, height: size * 0.025)
                }
        }
        .offset(y: size * 0.08)
    }
}
