import SwiftUI

/// מסך הבית — ריבועי לגבייה/לתשלום עם אותם חישובים בדיוק (PaymentsMath המשותף).
struct ClassicHomeView: View {
    @EnvironmentObject private var session: ClassicSession

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    if case .failed(let message) = session.state(for: .paymentsTransfer) {
                        Label(message, systemImage: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                    }
                    HStack(spacing: 12) {
                        tile(title: "לגבייה", rows: buckets.collection, tint: .green, id: "classic-tile-collection")
                        tile(title: "לתשלום", rows: buckets.payment, tint: .orange, id: "classic-tile-payment")
                    }
                    quickLinks
                }
                .padding(16)
            }
            .background(ClassicTheme.screen)
            .navigationTitle("בן יעקב — קלאסי")
            .refreshable { await session.loadDomain(.paymentsTransfer, force: true) }
            .task { await session.loadDomain(.paymentsTransfer) }
        }
        .accessibilityIdentifier("classic-home")
    }

    private var buckets: (collection: [DomainRecord], payment: [DomainRecord]) {
        PaymentsMath.categorize(session.records(for: .paymentsTransfer))
    }

    private func tile(title: String, rows: [DomainRecord], tint: Color, id: String) -> some View {
        let open = PaymentsMath.openTotal(rows)
        let overdue = PaymentsMath.overdueTotal(rows)
        return VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.headline)
            Text(Formatters.currencyValue(open, detailed: true))
                .font(.system(size: 26, weight: .bold).monospacedDigit())
                .foregroundColor(tint)
            if overdue > 0 {
                Text("מועד חלף: \(Formatters.currencyValue(overdue, detailed: true))")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.red)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 16))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier(id)
    }

    private var quickLinks: some View {
        VStack(spacing: 8) {
            ForEach([Domain.workingOrders, .orderHistory, .deliveryConfirmations, .customers, .financeInvoices]) { domain in
                NavigationLink {
                    ClassicDomainListView(domain: domain)
                        .navigationTitle(domain.spec.title)
                } label: {
                    HStack {
                        Image(systemName: domain.spec.icon)
                            .foregroundColor(ClassicTheme.brand)
                            .frame(width: 30)
                        Text(domain.spec.title).font(.headline)
                        Spacer()
                        Image(systemName: "chevron.backward").foregroundColor(.secondary)
                    }
                    .padding(14)
                    .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("classic-home-\(domain.rawValue)")
            }
        }
    }
}
