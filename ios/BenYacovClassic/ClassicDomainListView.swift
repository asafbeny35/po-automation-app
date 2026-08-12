import SwiftUI

/// רשימה גנרית לכל דומיין — חיפוש, סינון תשלומים, פירוט ופעולות.
struct ClassicDomainListView: View {
    @EnvironmentObject private var session: ClassicSession
    let domain: Domain

    @State private var searchText = ""
    @State private var selectedRecord: DomainRecord?
    @State private var paymentsDirection = "collection"
    @State private var paymentsStatus: PaymentsMath.RowStatus?
    @State private var customerTypeFilter: String?
    @State private var installationsStatusFilter = ""
    /// חשבוניות ספקים — מיון (ברירת מחדל: תאריך, מהחדש לישן) וסינון לפי מועד דיווח.
    @State private var financeSort: FinanceInvoices.Sort = .dateDesc
    @State private var financeReportFilter = ""

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                switch session.state(for: domain) {
                case .idle, .loading:
                    ProgressView().padding(.top, 40)
                case .failed(let message):
                    VStack(spacing: 10) {
                        Label(message, systemImage: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Button("נסה שוב") {
                            Task { await session.loadDomain(domain, force: true) }
                        }
                        .buttonStyle(.borderedProminent)
                        .accessibilityIdentifier("classic-retry")
                    }
                    .padding(.top, 30)
                case .loaded:
                    if domain == .paymentsTransfer { paymentsFilterBar }
                    if domain == .customers || domain == .inactiveCustomers { customerTypeBar }
                    if domain == .installationCases { installationsStatusBar }
                    if domain == .financeInvoices { financeFilterBar }
                    if records.isEmpty {
                        Text(searchText.isEmpty ? "אין נתונים להצגה" : "לא נמצאו תוצאות")
                            .foregroundColor(.secondary)
                            .padding(.top, 30)
                    } else {
                        HStack {
                            Text("\(records.count) רשומות")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .accessibilityIdentifier("classic-count")
                            Spacer()
                        }
                        ForEach(records) { record in
                            Button {
                                selectedRecord = record
                            } label: {
                                rowView(record)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("classic-row-\(domain.rawValue)")
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(ClassicTheme.screen)
        .searchable(text: $searchText, placement: .navigationBarDrawer(displayMode: .always), prompt: "חיפוש ב\(domain.spec.title)")
        .refreshable { await session.loadDomain(domain, force: true) }
        .task { await session.loadDomain(domain) }
        .sheet(item: $selectedRecord) { record in
            ClassicRecordDetailView(domain: domain, recordID: record.id)
        }
    }

    private var records: [DomainRecord] {
        var rows = session.records(for: domain)
        if domain == .installationCases, !installationsStatusFilter.isEmpty {
            rows = rows.filter { $0["status"] == installationsStatusFilter }
        }
        if domain == .customers || domain == .inactiveCustomers {
            if let customerTypeFilter {
                rows = rows.filter { CustomerDomains.normalized($0["customer_domain"]) == customerTypeFilter }
            }
            rows = CustomerDomains.sorted(rows)
        }
        if domain == .financeInvoices {
            if !financeReportFilter.isEmpty {
                rows = rows.filter { FinanceInvoices.matches($0, dueDate: financeReportFilter) }
            }
            rows = FinanceInvoices.sorted(rows, by: financeSort)
        }
        if domain == .paymentsTransfer {
            let buckets = PaymentsMath.categorize(rows)
            rows = paymentsDirection == "payment" ? buckets.payment : buckets.collection
            if let paymentsStatus {
                rows = rows.filter { PaymentsMath.status(of: $0) == paymentsStatus }
            }
        }
        let query = searchText.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else { return rows }
        return rows.filter { record in
            domain.spec.searchKeys.contains { record[$0].localizedCaseInsensitiveContains(query) }
        }
    }

    static func domainTint(_ value: String) -> Color {
        switch CustomerDomains.normalized(value) {
        case "construction": return Color(red: 0.55, green: 0.38, blue: 0.20)
        case "textile": return Color.teal
        case "supplier": return Color.indigo
        case "graphic_web": return Color.purple
        default: return ClassicTheme.brand
        }
    }

    private func rowView(_ record: DomainRecord) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(record.first(of: domain.spec.titleKeys))
                        .font(.headline)
                        .lineLimit(1)
                    if domain == .installationCases, !record["status"].isEmpty {
                        Text(record["status"])
                            .font(.caption2.weight(.bold))
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3)
                            .background(InstallationStatus.tint(record["status"]).opacity(0.15), in: Capsule())
                            .foregroundColor(InstallationStatus.tint(record["status"]))
                    }
                    if domain == .customers || domain == .inactiveCustomers {
                        let value = CustomerDomains.normalized(record["customer_domain"])
                        if !value.isEmpty {
                            Text(CustomerDomains.options.first { $0.value == value }?.short ?? "")
                                .font(.caption2.weight(.bold))
                                .padding(.horizontal, 7)
                                .padding(.vertical, 3)
                                .background(Self.domainTint(value).opacity(0.15), in: Capsule())
                                .foregroundColor(Self.domainTint(value))
                        }
                    }
                }
                if domain == .installationCases {
                    let progress = InstallationStatus.progressSummary(record)
                    if !progress.isEmpty {
                        Text(progress)
                            .font(.caption.weight(.medium))
                            .foregroundColor(InstallationStatus.tint(record["status"]))
                            .lineLimit(1)
                    }
                    if !record["delivery_address"].isEmpty {
                        Text(record["delivery_address"]).font(.caption).foregroundColor(.secondary).lineLimit(1)
                    }
                }
                if let subtitleKey = domain.spec.dateKeys.first {
                    Text(record[subtitleKey]).font(.caption).foregroundColor(.secondary)
                }
            }
            Spacer()
            if let amountKey = domain.spec.amountKey {
                Text(record[amountKey]).font(.subheadline.weight(.semibold).monospacedDigit())
            }
        }
        .padding(14)
        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
    }

    /// חשבוניות ספקים — בורר מיון + צ'יפי מועדי דיווח, כמו בדסקטופ ובאפליקציה הראשית.
    private var financeFilterBar: some View {
        let dueDates = FinanceInvoices.availableDueDates(session.records(for: domain))
        return VStack(alignment: .leading, spacing: 8) {
            Menu {
                ForEach(FinanceInvoices.Sort.allCases) { option in
                    Button {
                        financeSort = option
                    } label: {
                        if financeSort == option {
                            Label(option.title, systemImage: "checkmark")
                        } else {
                            Label(option.title, systemImage: option.icon)
                        }
                    }
                    .accessibilityIdentifier("classic-finance-sort-\(option.rawValue)")
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 12, weight: .semibold))
                    Text("מיון: \(financeSort.title)")
                        .font(.caption.weight(.semibold))
                        .lineLimit(1)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(ClassicTheme.card, in: Capsule())
                .foregroundColor(.primary)
            }
            .accessibilityIdentifier("classic-finance-sort-menu")

            if !dueDates.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(dueDates, id: \.self) { dueDate in
                            let isActive = financeReportFilter == dueDate
                            Button {
                                financeReportFilter = isActive ? "" : dueDate
                            } label: {
                                Text("דיווח \(FinanceInvoices.chipLabel(dueDate))")
                                    .font(.caption.weight(.semibold))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(isActive ? Color.green : Color.green.opacity(0.15), in: Capsule())
                                    .foregroundColor(isActive ? .white : .green)
                            }
                            .accessibilityIdentifier("classic-finance-report-filter")
                        }
                    }
                    .padding(.horizontal, 2)
                }
            }
        }
        .padding(.bottom, 4)
    }

    /// סינון תיקי התקנה לפי סטטוס — צ'יפים צבעוניים, טוגל.
    private var installationsStatusBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(APIClient.installationStatusOptions, id: \.self) { option in
                    let isActive = installationsStatusFilter == option
                    let tint = InstallationStatus.tint(option)
                    Button {
                        installationsStatusFilter = isActive ? "" : option
                    } label: {
                        Text(option)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(isActive ? tint : tint.opacity(0.15), in: Capsule())
                            .foregroundColor(isActive ? .white : tint)
                    }
                    .accessibilityIdentifier("classic-installations-status")
                }
            }
            .padding(.horizontal, 2)
        }
        .padding(.bottom, 4)
    }

    /// סינון סוגי לקוחות — כמו בדסקטופ.
    private var customerTypeBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(CustomerDomains.options) { option in
                    let isActive = customerTypeFilter == option.value
                    let tint = Self.domainTint(option.value)
                    Button {
                        customerTypeFilter = isActive ? nil : option.value
                    } label: {
                        Text(option.short)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(isActive ? tint : tint.opacity(0.15), in: Capsule())
                            .foregroundColor(isActive ? .white : tint)
                    }
                    .accessibilityIdentifier("classic-customer-type-\(option.value.isEmpty ? "none" : option.value)")
                }
            }
            .padding(.horizontal, 2)
        }
        .padding(.bottom, 4)
    }

    /// סינון גבייה/תשלום + סטטוס — כמו באפליקציה הראשית ובדסקטופ.
    private var paymentsFilterBar: some View {
        VStack(spacing: 8) {
            Picker("כיוון", selection: $paymentsDirection) {
                Text("גבייה").tag("collection")
                Text("תשלום").tag("payment")
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("classic-payments-direction")
            HStack(spacing: 8) {
                statusChip(.paid, label: paymentsDirection == "payment" ? "שולם" : "התקבל", id: "classic-status-paid")
                statusChip(.open, label: paymentsDirection == "payment" ? "לתשלום" : "לגבייה", id: "classic-status-open")
                statusChip(.overdue, label: paymentsDirection == "payment" ? "מועד התשלום חלף" : "מועד הגבייה חלף", id: "classic-status-overdue")
            }
        }
        .padding(.bottom, 4)
    }

    private func statusChip(_ status: PaymentsMath.RowStatus, label: String, id: String) -> some View {
        let active = paymentsStatus == status
        return Button {
            paymentsStatus = active ? nil : status
        } label: {
            Text(label)
                .font(.caption.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(active ? ClassicTheme.brand : ClassicTheme.card, in: Capsule())
                .foregroundColor(active ? .white : .primary)
        }
        .accessibilityIdentifier(id)
    }
}
