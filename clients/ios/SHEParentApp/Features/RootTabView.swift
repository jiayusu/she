import SwiftUI

struct RootTabView: View {
    let model: AppModel
    @State private var selection = 0

    var body: some View {
        TabView(selection: $selection) {
            TodayView(model: model)
                .tabItem { Label("今天", systemImage: "sparkles") }
                .tag(0)
            ReportsView(model: model)
                .tabItem { Label("成长", systemImage: "chart.line.uptrend.xyaxis") }
                .tag(1)
            DeviceView(model: model)
                .tabItem { Label("设备", systemImage: "dot.radiowaves.left.and.right") }
                .tag(2)
            ProfileView(model: model)
                .tabItem { Label("家庭", systemImage: "house") }
                .tag(3)
        }
        .sensoryFeedback(.selection, trigger: selection)
        .tint(SoftOrbit.lavender)
    }
}
