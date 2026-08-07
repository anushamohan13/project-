import Foundation

struct SharedBudgetData: Codable {
    let planId: String?
    let planVersion: Int
    let weeklyAllowance: String
    let remainingBudget: String
    let savingsProgressPercent: String
    let wishlistProgressPercent: String
    let nextSalaryDate: String?
    let currency: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case planId = "plan_id"
        case planVersion = "plan_version"
        case weeklyAllowance = "weekly_allowance"
        case remainingBudget = "remaining_budget"
        case savingsProgressPercent = "savings_progress_percent"
        case wishlistProgressPercent = "wishlist_progress_percent"
        case nextSalaryDate = "next_salary_date"
        case currency
        case updatedAt = "updated_at"
    }

    var savingsProgress: Double { Double(savingsProgressPercent) ?? 0 }
    var wishlistProgress: Double { Double(wishlistProgressPercent) ?? 0 }

    static let placeholder = SharedBudgetData(
        planId: nil,
        planVersion: 0,
        weeklyAllowance: "250.00",
        remainingBudget: "410.00",
        savingsProgressPercent: "20.00",
        wishlistProgressPercent: "35.00",
        nextSalaryDate: nil,
        currency: "SGD",
        updatedAt: ISO8601DateFormatter().string(from: Date())
    )
}

enum SharedBudgetStore {
    static let appGroup = "group.com.example.pocketpilot"
    static let key = "latestBudgetSnapshot"

    static func load() -> SharedBudgetData {
        guard
            let defaults = UserDefaults(suiteName: appGroup),
            let data = defaults.data(forKey: key),
            let snapshot = try? JSONDecoder().decode(SharedBudgetData.self, from: data)
        else {
            return .placeholder
        }
        return snapshot
    }
}
