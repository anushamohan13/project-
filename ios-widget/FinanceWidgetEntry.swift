import WidgetKit

struct FinanceWidgetEntry: TimelineEntry {
    let date: Date
    let snapshot: SharedBudgetData
}

struct FinanceWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> FinanceWidgetEntry {
        FinanceWidgetEntry(date: Date(), snapshot: .placeholder)
    }

    func getSnapshot(in context: Context, completion: @escaping (FinanceWidgetEntry) -> Void) {
        completion(FinanceWidgetEntry(date: Date(), snapshot: SharedBudgetStore.load()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<FinanceWidgetEntry>) -> Void) {
        let entry = FinanceWidgetEntry(date: Date(), snapshot: SharedBudgetStore.load())
        let nextRefresh = Calendar.current.date(byAdding: .minute, value: 30, to: Date()) ?? Date().addingTimeInterval(1800)
        completion(Timeline(entries: [entry], policy: .after(nextRefresh)))
    }
}
