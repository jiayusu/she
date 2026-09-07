import SwiftUI

struct ProfileView: View {
    @Bindable var model: AppModel
    @State private var sessionMinutes = 10.0
    @State private var nextDayContext = "明天去动物园"
    @State private var showingExport = false
    @State private var showingErase = false
    @State private var privacyResult: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("家庭") {
                    Label("苏家 · 演示家庭", systemImage: "person.2.fill")
                    Text("无登录 · 单家庭演示资料")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("下一次互动") {
                    Stepper("时长 \(Int(sessionMinutes)) 分钟", value: $sessionMinutes, in: 5...30, step: 5)
                    TextField("明天的场景", text: $nextDayContext)
                    Button("保存家长目标") {
                        Task {
                            await model.updateParentConstraints(
                                ParentConstraintsUpdate(
                                    sessionBudgetSeconds: Int(sessionMinutes * 60),
                                    preferredTopics: ["animals", "food"],
                                    avoidTopics: [],
                                    nextDayContext: nextDayContext,
                                    teachingPressure: .low
                                )
                            )
                        }
                    }
                    .frame(minHeight: 44)
                }

                Section("隐私与数据") {
                    Text(AccessibilityCopy.demoPrivacyNotice)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Button("导出演示数据") { showingExport = true }
                        .frame(minHeight: 44)
                    Button(AccessibilityCopy.eraseDemoData, role: .destructive) { showingErase = true }
                        .frame(minHeight: 44)
                    if let privacyResult {
                        Text(privacyResult).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .navigationTitle("家庭")
            .confirmationDialog("确认导出演示数据？", isPresented: $showingExport) {
                Button("继续演示导出") { Task { await performPrivacy(export: true) } }
                Button("取消", role: .cancel) {}
            } message: {
                Text(AccessibilityCopy.demoPrivacyNotice)
            }
            .confirmationDialog("确认删除演示数据？", isPresented: $showingErase) {
                Button(AccessibilityCopy.eraseDemoData, role: .destructive) { Task { await performPrivacy(export: false) } }
                Button("取消", role: .cancel) {}
            } message: {
                Text(AccessibilityCopy.demoPrivacyNotice)
            }
        }
        .softOrbitPage()
    }

    private func performPrivacy(export: Bool) async {
        do {
            let result = try await (export ? model.requestPrivacyExport() : model.requestPrivacyErase())
            privacyResult = result.mock && !result.storeMutated
                ? "演示请求已接收；真实学习存储没有改变。"
                : "请求状态需要人工确认。"
        } catch {
            privacyResult = "暂时无法完成演示，请稍后再试。"
        }
    }
}
