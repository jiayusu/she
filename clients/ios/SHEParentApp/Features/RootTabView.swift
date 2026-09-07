import SwiftUI

struct RootTabView: View {
    let model: AppModel

    var body: some View {
        TabView {
            TodayView(model: model)
                .tabItem { Label("今天", systemImage: "sparkles") }
            ReportsView(model: model)
                .tabItem { Label("成长", systemImage: "chart.line.uptrend.xyaxis") }
            DeviceView(model: model)
                .tabItem { Label("设备", systemImage: "dot.radiowaves.left.and.right") }
            ProfileView(model: model)
                .tabItem { Label("家庭", systemImage: "house") }
        }
        .tint(SoftOrbit.lavender)
    }
}
