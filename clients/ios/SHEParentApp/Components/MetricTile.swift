import SwiftUI

struct MetricTile: View {
    let label: String
    let value: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: SoftOrbit.Spacing.xSmall) {
            Text(value)
                .font(.title2.weight(.semibold))
                .foregroundStyle(SoftOrbit.ink)
            Text(label)
                .font(.subheadline.weight(.medium))
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(SoftOrbit.Spacing.medium)
        .frame(maxWidth: .infinity, minHeight: 112, alignment: .leading)
        .background(SoftOrbit.surface.opacity(0.88), in: RoundedRectangle(cornerRadius: SoftOrbit.Radius.small))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label)，\(value)，\(detail)")
    }
}
