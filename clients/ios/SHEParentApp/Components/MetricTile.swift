import SwiftUI

struct MetricTile: View {
    let label: String
    let value: String
    let detail: String

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: SoftOrbit.Spacing.xSmall) {
            Text(value)
                .font(.title2.weight(.semibold))
                .foregroundStyle(SoftOrbit.ink)
                .contentTransition(.numericText())
                .animation(
                    reduceMotion ? nil : SoftOrbit.Motion.settle,
                    value: value
                )
            Text(label)
                .font(.subheadline.weight(.medium))
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(SoftOrbit.Spacing.medium)
        .frame(maxWidth: .infinity, minHeight: 112, alignment: .leading)
        .background(SoftOrbit.surface, in: RoundedRectangle(cornerRadius: SoftOrbit.Radius.small, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: SoftOrbit.Radius.small, style: .continuous)
                .strokeBorder(SoftOrbit.ink.opacity(0.08), lineWidth: 1)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label)，\(value)，\(detail)")
    }
}
