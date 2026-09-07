import SwiftUI

@main
struct SHEParentApp: App {
    @State private var model: AppModel

    init() {
        let configured = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
        let baseURL = URL(string: configured ?? "http://127.0.0.1:8788")!
        _model = State(initialValue: AppModel(api: LiveAppAPI(baseURL: baseURL)))
    }

    var body: some Scene {
        WindowGroup {
            RootTabView(model: model)
                .task { await model.load() }
        }
    }
}
