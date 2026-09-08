import SwiftUI

/// The one accent action per screen: fills with the accent color, lifts at
/// rest, presses down into the finger, and ticks a light haptic on touch.
struct SoftOrbitPrimaryButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline.weight(.semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 50)
            .padding(.horizontal, SoftOrbit.Spacing.medium)
            .background(
                RoundedRectangle(cornerRadius: SoftOrbit.Radius.card, style: .continuous)
                    .fill(SoftOrbit.lavender)
            )
            .shadow(
                color: SoftOrbit.lavender.opacity(configuration.isPressed ? 0.0 : 0.20),
                radius: configuration.isPressed ? 4 : 12,
                y: configuration.isPressed ? 1 : 6
            )
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.97 : 1)
            .animation(
                SoftOrbit.Motion.press,
                value: configuration.isPressed
            )
            .sensoryFeedback(
                .impact(weight: .medium, intensity: 0.8),
                trigger: configuration.isPressed
            ) { _, pressed in
                pressed
            }
    }
}
