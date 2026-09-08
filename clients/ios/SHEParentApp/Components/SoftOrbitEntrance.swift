import SwiftUI

/// One-shot entrance: content rises a little and fades in, cascading by index.
/// Runs once per appearance; Reduce Motion shows content immediately.
private struct SoftOrbitEntrance: ViewModifier {
    let index: Int

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 16)
            .onAppear {
                guard !shown else { return }
                if reduceMotion {
                    shown = true
                } else {
                    withAnimation(
                        SoftOrbit.Motion.entrance.delay(Double(index) * SoftOrbit.Motion.stagger)
                    ) {
                        shown = true
                    }
                }
            }
            .onChange(of: reduceMotion) { _, value in
                if value { shown = true }
            }
    }
}

extension View {
    func softOrbitEntrance(index: Int) -> some View {
        modifier(SoftOrbitEntrance(index: index))
    }
}
