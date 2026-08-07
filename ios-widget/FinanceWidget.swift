import SwiftUI
import WidgetKit

struct FinanceWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: FinanceWidgetEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            Gauge(value: entry.snapshot.savingsProgress, in: 0...100) {
                Text("Save")
            } currentValueLabel: {
                Text("\(Int(entry.snapshot.savingsProgress))%")
            }
            .gaugeStyle(.accessoryCircular)
        case .accessoryInline:
            Text("Remaining \(entry.snapshot.currency) \(entry.snapshot.remainingBudget.description)")
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 3) {
                HStack { Text("PocketPilot").font(.headline); Spacer(); if entry.snapshot.planVersion > 0 { Text("v\(entry.snapshot.planVersion)").font(.caption2).foregroundStyle(.secondary) } }
                Text("Remaining \(entry.snapshot.currency) \(entry.snapshot.remainingBudget.description)")
                ProgressView(value: entry.snapshot.wishlistProgress, total: 100)
            }
        default:
            VStack(alignment: .leading, spacing: 8) {
                Text("Weekly allowance").font(.caption).foregroundStyle(.secondary)
                Text("\(entry.snapshot.currency) \(entry.snapshot.weeklyAllowance.description)").font(.title2.bold())
                HStack {
                    Label("Save \(Int(entry.snapshot.savingsProgress))%", systemImage: "banknote")
                    Spacer()
                    Label("Wish \(Int(entry.snapshot.wishlistProgress))%", systemImage: "gift")
                }
                .font(.caption2)
                ProgressView(value: entry.snapshot.savingsProgress, total: 100)
            }
            .containerBackground(.fill.tertiary, for: .widget)
        }
    }
}

struct FinanceWidget: Widget {
    let kind = "FinanceWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: FinanceWidgetProvider()) { entry in
            FinanceWidgetView(entry: entry)
        }
        .configurationDisplayName("PocketPilot Budget")
        .description("Weekly allowance, savings, and wishlist progress.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}
