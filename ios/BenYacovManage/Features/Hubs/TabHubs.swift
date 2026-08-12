import SwiftUI

/// טאב הזמנות — כל מחזור החיים של הזמנה.
struct OrdersHubView: View {
    var body: some View {
        DomainHubView(
            title: "הזמנות",
            tabs: [.workingOrders, .orderHistory, .quoteHistory, .deliveryConfirmations, .installationCases],
            flows: [
                .workingOrders: .orderComposer,
                .orderHistory: .orderComposer,
                .quoteHistory: .quoteComposer,
            ]
        )
    }
}

/// טאב לקוחות — פעילים, לא פעילים ויצירת לקוח.
struct CustomersHubView: View {
    var body: some View {
        DomainHubView(
            title: "לקוחות",
            tabs: [.customers, .inactiveCustomers],
            creationForms: [.customers: .customer]
        )
    }
}

/// טאב כספים — תשלומים, חשבוניות, ניכויים ובנק.
struct FinanceHubView: View {
    var body: some View {
        DomainHubView(
            title: "כספים",
            tabs: [.paymentsTransfer, .financeInvoices, .financeCustomerWithholdings, .financeBankMovements],
            creationForms: [.paymentsTransfer: .paymentRow, .financeCustomerWithholdings: .withholding],
            flows: [.financeInvoices: .invoiceUpload]
        )
    }
}

