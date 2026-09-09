import SwiftUI

@main
struct SHEParentApp: App {
    @State private var model: AppModel

    init() {
        let configured = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
        let baseURL = URL(string: configured ?? "http://127.0.0.1:8788")!
        let rpgIdentity = RpgReadIdentity(
            childID: Bundle.main.object(forInfoDictionaryKey: "RPG_CHILD_ID") as? String,
            sessionID: Bundle.main.object(forInfoDictionaryKey: "RPG_SESSION_ID") as? String
        )
        _model = State(
            initialValue: AppModel(
                api: LiveAppAPI(baseURL: baseURL),
                rpgIdentity: rpgIdentity
            )
        )
    }

    var body: some Scene {
        WindowGroup {
            RootTabView(model: model)
                .task { await model.load() }
        }
    }
}
