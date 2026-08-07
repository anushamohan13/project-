import ExpoModulesCore
import Foundation
import WidgetKit

public final class BudgetWidgetModule: Module {
    private let snapshotKey = "latestBudgetSnapshot"

    private var appGroup: String {
        Bundle.main.object(forInfoDictionaryKey: "PocketPilotAppGroup") as? String
            ?? "group.com.example.pocketpilot"
    }

    public func definition() -> ModuleDefinition {
        Name("BudgetWidget")

        AsyncFunction("writeSnapshot") { (snapshot: [String: Any]) in
            guard JSONSerialization.isValidJSONObject(snapshot) else {
                throw WidgetBridgeError.invalidPayload
            }
            let data = try JSONSerialization.data(withJSONObject: snapshot, options: [.sortedKeys])
            guard let defaults = UserDefaults(suiteName: self.appGroup) else {
                throw WidgetBridgeError.appGroupUnavailable
            }
            defaults.set(data, forKey: self.snapshotKey)
            defaults.set(Date().timeIntervalSince1970, forKey: "latestBudgetSnapshotWrittenAt")
            WidgetCenter.shared.reloadTimelines(ofKind: "FinanceWidget")
        }

        AsyncFunction("clearSnapshot") {
            guard let defaults = UserDefaults(suiteName: self.appGroup) else {
                throw WidgetBridgeError.appGroupUnavailable
            }
            defaults.removeObject(forKey: self.snapshotKey)
            defaults.removeObject(forKey: "latestBudgetSnapshotWrittenAt")
            WidgetCenter.shared.reloadAllTimelines()
        }

        Function("lastWrittenAt") { () -> Double? in
            guard let defaults = UserDefaults(suiteName: self.appGroup) else { return nil }
            let value = defaults.double(forKey: "latestBudgetSnapshotWrittenAt")
            return value == 0 ? nil : value
        }
    }
}

enum WidgetBridgeError: Error {
    case invalidPayload
    case appGroupUnavailable
}
