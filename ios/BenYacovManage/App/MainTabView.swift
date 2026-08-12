import SwiftUI

/// המבנה הראשי — חמישה טאבים.
struct MainTabView: View {
    enum Tab: Hashable {
        case home, orders, customers, finance, more
    }

    @State private var selection: Tab

    init() {
        // בטסטים/צילומי מסך אפשר לפתוח ישר טאב מסוים.
        switch ProcessInfo.processInfo.environment["BY_UITEST_START_TAB"] {
        case "orders": _selection = State(initialValue: .orders)
        case "customers": _selection = State(initialValue: .customers)
        case "finance": _selection = State(initialValue: .finance)
        case "more": _selection = State(initialValue: .more)
        default: _selection = State(initialValue: .home)
        }
    }

    var body: some View {
        TabView(selection: $selection) {
            HomeView()
                .tabItem { Label("בית", systemImage: "house.fill") }
                .tag(Tab.home)
                .accessibilityIdentifier("tab-home")

            OrdersHubView()
                .tabItem { Label("הזמנות", systemImage: "shippingbox.fill") }
                .tag(Tab.orders)
                .accessibilityIdentifier("tab-orders")

            CustomersHubView()
                .tabItem { Label("לקוחות", systemImage: "person.2.fill") }
                .tag(Tab.customers)
                .accessibilityIdentifier("tab-customers")

            FinanceHubView()
                .tabItem { Label("כספים", systemImage: "creditcard.fill") }
                .tag(Tab.finance)
                .accessibilityIdentifier("tab-finance")

            MoreHubView()
                .tabItem { Label("עוד", systemImage: "square.grid.2x2.fill") }
                .tag(Tab.more)
                .accessibilityIdentifier("tab-more")
        }
    }
}
