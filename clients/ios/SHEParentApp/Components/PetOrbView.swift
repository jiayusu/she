import SwiftUI

struct PetOrbView: View {
    let statusLabel: String
    var size: CGFloat = 210

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var breathing = false
    @State private var eyesOpen = true

    var body: some View {
        ZStack {
            Ellipse()
                .fill(SoftOrbit.lavender.opacity(0.12))
                .frame(width: size * 0.72, height: size * 0.18)
                .blur(radius: reduceTransparency ? 1 : 9)
                .offset(y: size * 0.47)

            Circle()
                .fill(
                    RadialGradient(
                        colors: [SoftOrbit.lavenderLight, SoftOrbit.lavender, Color(red: 0.55, green: 0.10, blue: 0.09)],
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
                .shadow(
                    color: SoftOrbit.lavender.opacity(0.18),
                    radius: breathing && !reduceMotion ? 22 : 18,
                    y: breathing && !reduceMotion ? 12 : 10
                )
                .scaleEffect(breathing && !reduceMotion ? 1.025 : 1)
                .animation(
                    reduceMotion ? nil : .easeInOut(duration: SoftOrbit.Motion.breathing).repeatForever(autoreverses: true),
                    value: breathing
                )
        }
        .frame(width: size, height: size * (dynamicTypeSize.isAccessibilitySize ? 1.08 : 1))
        .onAppear { breathing = !reduceMotion }
        .onChange(of: reduceMotion) { _, value in breathing = !value }
        .task(id: reduceMotion) {
            await blinkLoop()
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(statusLabel)
    }

    private func blinkLoop() async {
        guard !reduceMotion else { return }
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(Double.random(in: 2.6...5.2)))
            if Task.isCancelled { return }
            withAnimation(.easeOut(duration: 0.08)) { eyesOpen = false }
            try? await Task.sleep(for: .seconds(0.12))
            if Task.isCancelled { return }
            withAnimation(.easeIn(duration: 0.08)) { eyesOpen = true }
        }
    }

    private var face: some View {
        VStack(spacing: size * 0.09) {
            HStack(spacing: size * 0.22) {
                eye
                eye
            }
            .scaleEffect(
                y: eyesOpen || reduceMotion ? 1 : 0.08,
                anchor: .center
            )
            Capsule()
                .fill(SoftOrbit.ink.opacity(0.78))
                .frame(width: size * 0.18, height: size * 0.055)
                .overlay(alignment: .bottom) {
                    Capsule().fill(Color.pink.opacity(0.75)).frame(width: size * 0.09, height: size * 0.025)
                }
        }
        .offset(y: size * 0.08)
    }

    private var eye: some View {
        Circle()
            .fill(SoftOrbit.ink.opacity(0.82))
            .frame(width: size * 0.075)
    }
}
