import SwiftUI

/// מסך הבית — ברכה, מדדים חיים, וגישה מהירה לכל תחומי המערכת.
struct HomeView: View {
    @Environment(SessionStore.self) private var session

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    heroHeader
                    kpiGrid
                    quickSections
                }
                .padding(.bottom, 24)
            }
            .accessibilityIdentifier("home-screen")
            .background(BYTheme.screenBackground)
            .navigationBarHidden(true)
            .refreshable {
                await session.loadBootstrap(force: true)
                await session.loadDomain(.paymentsTransfer, force: true)
                await session.loadDomain(.marketingReminders, force: true)
            }
            .navigationDestination(for: Domain.self) { domain in
                DomainListView(domain: domain, embedded: true)
                    .navigationTitle(domain.spec.title)
                    .navigationBarTitleDisplayMode(.large)
            }
        }
        .task {
            await session.loadBootstrap()
            await session.loadDomain(.paymentsTransfer)
            await session.loadDomain(.marketingReminders)
        }
        .accessibilityIdentifier("home-screen")
    }

    // MARK: - כותרת

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        let name = session.currentUserName.isEmpty ? "" : ", \(session.currentUserName)"
        switch hour {
        case 5..<12: return "בוקר טוב\(name)"
        case 12..<17: return "צהריים טובים\(name)"
        case 17..<21: return "ערב טוב\(name)"
        default: return "לילה טוב\(name)"
        }
    }

    private var todayText: String {
        let formatter = DateFormatter()
        formatter.locale = Formatters.hebrewLocale
        formatter.dateFormat = "EEEE, d בMMMM yyyy"
        return formatter.string(from: Date())
    }

    private var heroHeader: some View {
        ZStack(alignment: .bottomLeading) {
            BYTheme.heroGradient
            VStack(alignment: .leading, spacing: 5) {
                HStack {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(greeting)
                            .font(.byLargeTitle)
                            .foregroundStyle(.white)
                            .accessibilityIdentifier("greeting")
                        Text(todayText)
                            .font(.byBody)
                            .foregroundStyle(.white.opacity(0.75))
                    }
                    Spacer()
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 30, weight: .light))
                        .foregroundStyle(.white.opacity(0.85))
                }
            }
            .padding(20)
            .padding(.top, 46)
        }
        .clipShape(
            .rect(bottomLeadingRadius: 26, bottomTrailingRadius: 26)
        )
        .ignoresSafeArea(edges: .top)
    }

    // MARK: - מדדים

    private struct KPI: Identifiable {
        let id: String
        let title: String
        let value: String
        let icon: String
        let tint: Color
        let domain: Domain
        /// שורת פירוט קטנה (למשל כמה מתוך הסכום כבר עבר את מועד היעד).
        var detail: String? = nil
    }

    private var kpis: [KPI] {
        // אותה קטגוריזציה כמו בדסקטופ — כדי שהמספרים יהיו זהים למסכי "לגבייה"/"לתשלום".
        // הסכום הפתוח כולל תמיד גם שורות שמועד הגבייה/התשלום שלהן כבר חלף.
        let categories = PaymentsMath.categorize(session.records(for: .paymentsTransfer))
        let collect = PaymentsMath.openTotal(categories.collection)
        let collectOverdue = PaymentsMath.overdueTotal(categories.collection)
        let pay = PaymentsMath.openTotal(categories.payment)
        let payOverdue = PaymentsMath.overdueTotal(categories.payment)
        let workingCount = sectionCount("working-orders")
        let openReminders = session.records(for: .marketingReminders)
            .filter { $0["status"].lowercased() != "completed" }
            .count

        return [
            KPI(id: "kpi-working", title: "הזמנות בעבודה", value: "\(workingCount)",
                icon: "hammer.fill", tint: BYTheme.Palette.amber, domain: .workingOrders),
            KPI(id: "kpi-collect", title: "לגבייה", value: Formatters.currencyValue(collect),
                icon: "arrow.down.circle.fill", tint: BYTheme.Palette.green, domain: .paymentsTransfer,
                detail: collectOverdue > 0 ? "מועד הגבייה חלף: \(Formatters.currencyValue(collectOverdue))" : nil),
            KPI(id: "kpi-pay", title: "לתשלום", value: Formatters.currencyValue(pay),
                icon: "arrow.up.circle.fill", tint: BYTheme.Palette.red, domain: .paymentsTransfer,
                detail: payOverdue > 0 ? "מועד התשלום חלף: \(Formatters.currencyValue(payOverdue))" : nil),
            KPI(id: "kpi-reminders", title: "תזכורות פתוחות", value: "\(openReminders)",
                icon: "bell.badge.fill", tint: BYTheme.Palette.purple, domain: .marketingReminders),
        ]
    }

    private func sectionCount(_ id: String) -> Int {
        session.bootstrap.value?.sections.first { $0.id == id }?.count ?? 0
    }

    private var kpiGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
            ForEach(kpis) { kpi in
                NavigationLink(value: kpi.domain) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Image(systemName: kpi.icon)
                                .font(.system(size: 15, weight: .semibold))
                                .foregroundStyle(kpi.tint)
                                .frame(width: 30, height: 30)
                                .background(kpi.tint.opacity(0.13))
                                .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                            Spacer()
                        }
                        Text(kpi.value)
                            .font(.byNumber(22))
                            .foregroundStyle(BYTheme.textPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        Text(kpi.title)
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        if let detail = kpi.detail {
                            Text(detail)
                                .font(.system(size: 10.5, weight: .semibold))
                                .foregroundStyle(BYTheme.Palette.red)
                                .lineLimit(1)
                                .minimumScaleFactor(0.75)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(BYTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: BYTheme.cardRadius, style: .continuous))
                    .shadow(color: .black.opacity(0.05), radius: 8, y: 3)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier(kpi.id)
            }
        }
        .padding(.horizontal, 16)
    }

    // MARK: - כל התחומים

    private struct SectionGroup: Identifiable {
        let id: String
        let title: String
        let domains: [Domain]
    }

    private let groups: [SectionGroup] = [
        SectionGroup(id: "orders", title: "הזמנות ומשלוחים",
                     domains: [.workingOrders, .orderHistory, .quoteHistory, .deliveryConfirmations, .deliveryContacts, .projectManagers]),
        SectionGroup(id: "money", title: "כספים",
                     domains: [.paymentsTransfer, .financeInvoices, .financeCustomerWithholdings, .financeBankMovements, .pazomat, .sibus]),
        SectionGroup(id: "customers", title: "לקוחות ושיווק",
                     domains: [.customers, .inactiveCustomers, .marketingPipeline, .marketingReminders, .marketingWorkManagers, .marketingConstructionCompanies]),
        SectionGroup(id: "operations", title: "תפעול ומלאי",
                     domains: [.inventoryPurchaseOrders, .inventoryRaw, .inventoryFinish, .supplierDeliveryNotes, .pricingItems, .pricingComponents]),
        SectionGroup(id: "hr", title: "עובדים ושכר",
                     domains: [.hrEmployees, .hrHours, .hrPayroll, .hrContributions, .hrDocuments, .hrPayslipPrepHistory]),
    ]

    private var quickSections: some View {
        VStack(spacing: 18) {
            ForEach(groups) { group in
                VStack(spacing: 8) {
                    SectionHeader(title: group.title)
                        .padding(.horizontal, 16)
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        ForEach(group.domains) { domain in
                            NavigationLink(value: domain) {
                                HStack(spacing: 10) {
                                    Image(systemName: domain.spec.icon)
                                        .font(.system(size: 14, weight: .semibold))
                                        .foregroundStyle(domain.spec.tint.color)
                                        .frame(width: 28, height: 28)
                                        .background(domain.spec.tint.color.opacity(0.12))
                                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                    VStack(alignment: .leading, spacing: 1) {
                                        Text(domain.spec.title)
                                            .font(.byCaption.weight(.semibold))
                                            .foregroundStyle(BYTheme.textPrimary)
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.8)
                                        Text("\(bootstrapCount(domain)) רשומות")
                                            .font(.system(size: 11))
                                            .foregroundStyle(BYTheme.textSecondary)
                                    }
                                    Spacer(minLength: 0)
                                }
                                .padding(10)
                                .background(BYTheme.cardBackground)
                                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("home-domain-\(domain.rawValue)")
                        }
                    }
                    .padding(.horizontal, 16)
                }
            }
        }
    }

    private func bootstrapCount(_ domain: Domain) -> Int {
        session.bootstrap.value?.sections.first { $0.id == domain.bootstrapSectionID }?.count
            ?? session.records(for: domain).count
    }
}
