import SwiftUI

/// חמשת הטאבים — אותו מבנה כמו האפליקציה הראשית.
struct ClassicMainView: View {
    var body: some View {
        TabView {
            ClassicHomeView()
                .tabItem { Label("בית", systemImage: "house.fill") }
            ClassicHubView(title: "הזמנות",
                           tabs: [.workingOrders, .orderHistory, .quoteHistory, .deliveryConfirmations, .installationCases],
                           flows: [.workingOrders: .orderComposer,
                                   .orderHistory: .orderComposer,
                                   .quoteHistory: .quoteComposer])
                .tabItem { Label("הזמנות", systemImage: "doc.text.fill") }
            ClassicHubView(title: "לקוחות",
                           tabs: [.customers, .inactiveCustomers],
                           creationForms: [.customers: .customer])
                .tabItem { Label("לקוחות", systemImage: "person.2.fill") }
            ClassicHubView(title: "כספים",
                           tabs: [.paymentsTransfer, .financeInvoices, .financeCustomerWithholdings, .financeBankMovements],
                           creationForms: [.paymentsTransfer: .paymentRow, .financeCustomerWithholdings: .withholding],
                           flows: [.financeInvoices: .invoiceUpload])
                .tabItem { Label("כספים", systemImage: "creditcard.fill") }
            ClassicMoreView()
                .tabItem { Label("עוד", systemImage: "ellipsis.circle.fill") }
        }
    }
}

/// טאב "עוד" — קבוצות הדומיינים הנוספות + התנתקות.
struct ClassicMoreView: View {
    @EnvironmentObject private var session: ClassicSession
    @EnvironmentObject private var biometricLock: ClassicBiometricLock

    var body: some View {
        NavigationStack {
            List {
                Section("תחומים") {
                    NavigationLink("שיווק") {
                        ClassicHubContent(title: "שיווק",
                                          tabs: [.marketingPipeline, .marketingReminders, .marketingWorkManagers, .marketingConstructionCompanies, .marketingHistory],
                                          creationForms: [.marketingReminders: .reminder,
                                                          .marketingWorkManagers: .workManager,
                                                          .marketingConstructionCompanies: .constructionCompany])
                    }
                    NavigationLink("עובדים ושכר") {
                        ClassicHubContent(title: "עובדים ושכר",
                                          tabs: [.hrEmployees, .hrHours, .hrPayroll, .hrContributions, .hrDocuments, .hrPayslipPrepHistory],
                                          creationForms: [.hrEmployees: .hrEmployee, .hrHours: .hrHours])
                    }
                    NavigationLink("מלאי ותמחור") {
                        ClassicHubContent(title: "מלאי ותמחור",
                                          tabs: [.inventoryPurchaseOrders, .inventoryRaw, .inventoryFinish, .inventoryContacts, .supplierDeliveryNotes, .pricingItems, .pricingComponents],
                                          flows: [.inventoryPurchaseOrders: .supplierPOComposer])
                    }
                    NavigationLink("הנהלה") {
                        ClassicHubContent(title: "הנהלה",
                                          tabs: [.pazomat, .sibus, .deliveryContacts, .projectManagers, .financeSettings])
                    }
                }
                Section("כלים") {
                    NavigationLink {
                        ClassicLabelsView()
                    } label: {
                        Label("מדבקות משלוח", systemImage: "tag.fill")
                    }
                    .accessibilityIdentifier("classic-more-labels")
                }
                Section("מנהלה פיננסית") {
                    NavigationLink {
                        ClassicLoansView()
                    } label: {
                        Label("הלוואות ומשכנתאות", systemImage: "banknote.fill")
                    }
                    .accessibilityIdentifier("classic-more-loans")
                    NavigationLink {
                        ClassicVehiclesView()
                    } label: {
                        Label("צי רכבים וכלי עבודה", systemImage: "car.fill")
                    }
                    .accessibilityIdentifier("classic-more-vehicles")
                }
                if biometricLock.isSupported {
                    Section("אבטחה") {
                        Toggle(isOn: Binding(
                            get: { biometricLock.isEnabled },
                            set: { wantsOn in
                                if wantsOn {
                                    Task {
                                        if await biometricLock.enableAfterVerification() {
                                            session.showSuccess("הכניסה עם \(biometricLock.biometryLabel) הופעלה.")
                                        } else {
                                            session.showError("האימות נכשל — הנעילה לא הופעלה.")
                                        }
                                    }
                                } else {
                                    biometricLock.isEnabled = false
                                }
                            }
                        )) {
                            Label("כניסה עם \(biometricLock.biometryLabel)",
                                  systemImage: "touchid")
                        }
                        .accessibilityIdentifier("classic-touchid-toggle")
                    }
                }
                Section {
                    LabeledContent("מחובר", value: session.currentUserName)
                    Button("התנתקות", role: .destructive) {
                        Task { await session.logout() }
                    }
                    .accessibilityIdentifier("classic-logout")
                } footer: {
                    Text("בן יעקב קלאסי — גרסה תואמת iPadOS 16. ליצירת מסמכים והעלאות: האפליקציה הראשית או הדסקטופ.")
                }
            }
            .navigationTitle("עוד")
        }
        .accessibilityIdentifier("classic-more")
    }
}

/// hub עם צ'יפים — עטוף NavigationStack.
struct ClassicHubView: View {
    let title: String
    let tabs: [Domain]
    var creationForms: [Domain: EditFormKind] = [:]
    var flows: [Domain: ClassicComposerFlow] = [:]

    var body: some View {
        NavigationStack {
            ClassicHubContent(title: title, tabs: tabs, creationForms: creationForms, flows: flows)
        }
    }
}

/// זרימות הקומפוזרים — אותו קטלוג כמו האפליקציה הראשית.
enum ClassicComposerFlow: String, Identifiable {
    case orderComposer
    case quoteComposer
    case supplierPOComposer
    case invoiceUpload

    var id: String { rawValue }
}

struct ClassicHubContent: View {
    let title: String
    let tabs: [Domain]
    var creationForms: [Domain: EditFormKind] = [:]
    var flows: [Domain: ClassicComposerFlow] = [:]

    @State private var selected: Domain
    @State private var creationForm: EditFormKind?
    @State private var activeFlow: ClassicComposerFlow?

    init(title: String, tabs: [Domain],
         creationForms: [Domain: EditFormKind] = [:],
         flows: [Domain: ClassicComposerFlow] = [:]) {
        self.title = title
        self.tabs = tabs
        self.creationForms = creationForms
        self.flows = flows
        _selected = State(initialValue: tabs[0])
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(tabs) { domain in
                        Button {
                            withAnimation(.easeOut(duration: 0.15)) { selected = domain }
                        } label: {
                            Text(domain.spec.title)
                                .font(.subheadline.weight(.semibold))
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)
                                .background(selected == domain ? ClassicTheme.brand : ClassicTheme.card,
                                            in: Capsule())
                                .foregroundColor(selected == domain ? .white : .primary)
                        }
                        .accessibilityIdentifier("classic-chip-\(domain.rawValue)")
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
            }
            ClassicDomainListView(domain: selected)
                .id(selected)
        }
        .navigationTitle(title)
        .toolbar {
            if let flow = flows[selected] {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        activeFlow = flow
                    } label: {
                        Image(systemName: "plus.rectangle.on.rectangle")
                    }
                    .accessibilityIdentifier("classic-flow-button")
                }
            }
            if let form = creationForms[selected] {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        creationForm = form
                    } label: {
                        Image(systemName: "plus.circle.fill")
                    }
                    .accessibilityIdentifier("classic-add")
                }
            }
        }
        .sheet(item: $creationForm) { form in
            ClassicRecordFormView(kind: form, domain: selected, existing: nil)
        }
        .sheet(item: $activeFlow) { flow in
            switch flow {
            case .orderComposer: ClassicOrderComposerView()
            case .quoteComposer: ClassicQuoteComposerView()
            case .supplierPOComposer: ClassicSupplierPOComposerView()
            case .invoiceUpload: ClassicInvoiceUploadView()
            }
        }
    }
}
