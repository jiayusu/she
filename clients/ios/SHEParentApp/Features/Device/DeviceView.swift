import SwiftUI

struct DeviceView: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationStack {
            Form {
                if let settings = model.deviceSettings {
                    Section("小P设备") {
                        LabeledContent("状态", value: settings.online ? "在线" : "离线")
                        LabeledContent("电量", value: settings.batteryPercent.map { "\($0)%" } ?? "未知")
                        LabeledContent("固件", value: settings.firmwareVersion)
                    }

                    Section("声音与灯光") {
                        VStack(alignment: .leading) {
                            Text("音量 \(settings.volume)")
                            Slider(
                                value: Binding(
                                    get: { Double(model.deviceSettings?.volume ?? settings.volume) },
                                    set: { value in Task { await model.updateDeviceSettings(DeviceSettingsPatch(volume: Int(value))) } }
                                ),
                                in: 0...100,
                                step: 1
                            )
                            .accessibilityLabel("设备音量")
                        }
                        Toggle(
                            "启用陪伴灯",
                            isOn: toggleBinding(settings.ledEnabled) { DeviceSettingsPatch(ledEnabled: $0) }
                        )
                    }

                    Section("感知与隐私") {
                        Toggle(
                            AccessibilityCopy.cameraControl,
                            isOn: toggleBinding(settings.cameraEnabled) { DeviceSettingsPatch(cameraEnabled: $0) }
                        )
                        Toggle(
                            AccessibilityCopy.rawAudioControl,
                            isOn: toggleBinding(settings.rawAudioUploadEnabled) { DeviceSettingsPatch(rawAudioUploadEnabled: $0) }
                        )
                        Text("摄像头只在明确触发的短窗口内开启；原始画面默认不落盘。")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                } else {
                    ContentUnavailableView("设备信息暂不可用", systemImage: "dot.radiowaves.left.and.right")
                }

                if model.transientError != nil {
                    Section {
                        Label("设置没有保存，已恢复原值。", systemImage: "arrow.uturn.backward.circle")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .navigationTitle("设备")
        }
        .softOrbitPage()
    }

    private func toggleBinding(
        _ fallback: Bool,
        patch: @escaping (Bool) -> DeviceSettingsPatch
    ) -> Binding<Bool> {
        Binding(
            get: { fallbackValue(for: patch, default: fallback) },
            set: { value in Task { await model.updateDeviceSettings(patch(value)) } }
        )
    }

    private func fallbackValue(
        for patch: (Bool) -> DeviceSettingsPatch,
        default fallback: Bool
    ) -> Bool {
        let marker = patch(true)
        if marker.ledEnabled != nil { return model.deviceSettings?.ledEnabled ?? fallback }
        if marker.cameraEnabled != nil { return model.deviceSettings?.cameraEnabled ?? fallback }
        return model.deviceSettings?.rawAudioUploadEnabled ?? fallback
    }
}
