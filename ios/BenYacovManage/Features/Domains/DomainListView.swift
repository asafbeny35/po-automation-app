import SwiftUI

/// רשימה גנרית לדומיין: חיפוש, רענון במשיכה, מצבי טעינה/שגיאה/ריק, וניווט לפירוט.
struct DomainListView: View {
    @Environment(SessionStore.self) private var session
    let domain: Domain
    /// סינון נוסף מעל הדאטה (למשל "רק לא שולם").
    var filter: ((DomainRecord) -> Bool)? = nil
    /// האם המסך עטוף כבר ב-NavigationStack (בתוך hub) או עצמאי.
    var embedded: Bool = false

    @State private var searchText = ""
    @State private var selectedRecord: DomainRecord?
    /// סינון תשלומים והעברות — כמו בדסקטופ: כיוון (גבייה/תשלום) + סטטוס כטוגל.
    @State private var paymentsDirection: PaymentsDirection = .collection
    @State private var paymentsStatus: PaymentsMath.RowStatus?
    /// סינון תיקי התקנה לפי סטטוס — כמו הסלקט בדסקטופ.
    @State private var installationsStatusFilter = ""
    /// סינון לקוחות לפי סוג (תחום) — nil = הכל.
    @State private var customerTypeFilter: String?
    /// חשבוניות ספקים — מיון (ברירת מחדל: תאריך, מהחדש לישן) וסינון לפי מועד דיווח.
    @State private var financeSort: FinanceInvoices.Sort = .dateDesc
    @State private var financeReportFilter = ""
    /// אישורי מסירה — פילוח "טרם נשלח / נשלח" כמו שני כפתורי הסינון בדסקטופ.
    /// ברירת המחדל זהה לדסקטופ: מה שעדיין ממתין לשליחה.
    @State private var deliverySent = false
    /// עובדים ושכר — פעילים מול עובדי עבר, כמו מתג התצוגה בדסקטופ.
    @State private var hrShowFormer = false
    /// תיקי התקנה — שלב: הכול / תואמו·ממתינים / הושלמו·בוטלו.
    @State private var installationsPhase: InstallationsPhase = .all
    /// תשלומים — סינון לפי אות ראשונה של שם הלקוח וטווח תאריכים, כמו בדסקטופ.
    @State private var paymentsLetter: String?
    @State private var paymentsDateField: PaymentsDateField = .due
    @State private var paymentsFrom: Date?
    @State private var paymentsTo: Date?

    enum PaymentsDateField: String, CaseIterable {
        case due, invoice
        var key: String { self == .due ? "due_date" : "invoice_date" }
        func title(_ direction: PaymentsDirection) -> String {
            self == .due ? (direction == .collection ? "מועד הגבייה" : "מועד התשלום") : "תאריך חשבונית"
        }
    }

    enum InstallationsPhase: String, CaseIterable {
        case all, open, closed
        var title: String {
            switch self {
            case .all: return "הכול"
            case .open: return "תואמו / ממתינים"
            case .closed: return "הושלמו / בוטלו"
            }
        }
    }

    enum PaymentsDirection: String, CaseIterable {
        case collection
        case payment

        var title: String { self == .collection ? "גבייה" : "תשלום" }

        func statusLabel(_ status: PaymentsMath.RowStatus) -> String {
            switch (self, status) {
            case (.collection, .paid): return "התקבל"
            case (.collection, .open): return "לגבייה"
            case (.collection, .overdue): return "מועד הגבייה חלף"
            case (.payment, .paid): return "שולם"
            case (.payment, .open): return "לתשלום"
            case (.payment, .overdue): return "מועד התשלום חלף"
            }
        }
    }

    /// watch חי: דומיינים עם endpoint של epoch מתרעננים אוטומטית כשמשהו
    /// משתנה בשרת (למשל חשבונית ספק שנשמרה מהנייד או מהדסקטופ).
    private func watchEpochIfSupported() async {
        guard let epochPath = domain.epochPath else { return }
        let interval: UInt64 = AppConfig.isUITest ? 1_000_000_000 : 20_000_000_000
        var lastSignature: String?
        while !Task.isCancelled {
            try? await Task.sleep(nanoseconds: interval)
            guard !Task.isCancelled else { return }
            guard let data = try? await session.api.getJSON(epochPath),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                continue
            }
            let signature = "\(object["count"] ?? "")|\(object["latest_updated_at"] ?? "")"
            if let last = lastSignature, signature != last {
                await session.loadDomain(domain, force: true)
            }
            lastSignature = signature
        }
    }

    private var records: [DomainRecord] {
        var rows = session.records(for: domain)
        if let filter { rows = rows.filter(filter) }
        if domain == .installationCases {
            if installationsPhase != .all {
                let closed = ["הושלם", "בוטל"]
                rows = rows.filter { closed.contains($0["status"]) == (installationsPhase == .closed) }
            }
            if !installationsStatusFilter.isEmpty {
                rows = rows.filter { $0["status"] == installationsStatusFilter }
            }
        }
        if domain == .hrEmployees {
            rows = rows.filter { HREmployees.isFormer($0) == hrShowFormer }
        }
        if domain == .customers || domain == .inactiveCustomers {
            if let customerTypeFilter {
                rows = rows.filter { CustomerDomains.normalized($0["customer_domain"]) == customerTypeFilter }
            }
            // מיון הדסקטופ: אלפביתי עברי לפי שם הלקוח.
            rows = CustomerDomains.sorted(rows)
        }
        if domain == .financeInvoices {
            if !financeReportFilter.isEmpty {
                rows = rows.filter { FinanceInvoices.matches($0, dueDate: financeReportFilter) }
            }
            rows = FinanceInvoices.sorted(rows, by: financeSort)
        }
        if domain == .deliveryConfirmations {
            rows = rows.filter { DeliveryConfirmations.isSent($0) == deliverySent }
        }
        if domain == .paymentsTransfer {
            // אותם כללי סיווג כמו מקטעי הדסקטופ (רק שורות הפעילות הנוכחית).
            let buckets = PaymentsMath.categorize(rows)
            rows = paymentsDirection == .payment ? buckets.payment : buckets.collection
            if let paymentsStatus {
                rows = rows.filter { PaymentsMath.status(of: $0) == paymentsStatus }
            }
            if paymentsFrom != nil || paymentsTo != nil {
                rows = rows.filter { PaymentsFilters.inRange($0, field: paymentsDateField.key, from: paymentsFrom, to: paymentsTo) }
            }
            if let paymentsLetter {
                rows = rows.filter { PaymentsFilters.letter(of: $0) == paymentsLetter }
            }
        }
        let query = searchText.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else { return rows }
        let keys = domain.spec.searchKeys
        return rows.filter { record in
            keys.contains { record[$0].localizedCaseInsensitiveContains(query) }
        }
    }

    var body: some View {
        Group {
            if embedded {
                content
            } else {
                NavigationStack {
                    content
                        .navigationTitle(domain.spec.title)
                        .navigationBarTitleDisplayMode(.large)
                }
            }
        }
    }

    private var content: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                switch session.state(for: domain) {
                case .idle, .loading:
                    ShimmerList()
                case .failed(let message):
                    ErrorStateView(message: message) {
                        Task { await session.loadDomain(domain, force: true) }
                    }
                case .loaded:
                    if domain == .paymentsTransfer {
                        paymentsFilterBar
                    }
                    if domain == .installationCases {
                        installationsFilterBar
                    }
                    if domain == .customers || domain == .inactiveCustomers {
                        customerTypeFilterBar
                    }
                    if domain == .financeInvoices {
                        AccountantSendBar()
                        financeFilterBar
                    }
                    if domain == .deliveryConfirmations {
                        deliveryFilterBar
                    }
                    if domain == .hrEmployees {
                        hrViewFilterBar
                    }
                    if records.isEmpty {
                        EmptyStateView(
                            icon: domain.spec.icon,
                            title: searchText.isEmpty ? "אין נתונים להצגה" : "לא נמצאו תוצאות",
                            subtitle: searchText.isEmpty ? nil : "נסה חיפוש אחר"
                        )
                    } else {
                        countHeader
                        ForEach(records) { record in
                            Button {
                                Haptics.tap()
                                selectedRecord = record
                            } label: {
                                DomainRowView(domain: domain, record: record)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("row-\(domain.rawValue)")
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .background(BYTheme.screenBackground)
        .searchable(text: $searchText, placement: .navigationBarDrawer(displayMode: .always), prompt: "חיפוש ב\(domain.spec.title)")
        .refreshable { await session.loadDomain(domain, force: true) }
        .task { await session.loadDomain(domain) }
        .task { await watchEpochIfSupported() }
        .sheet(item: $selectedRecord) { record in
            RecordDetailView(domain: domain, recordID: record.id)
        }
        .accessibilityIdentifier("domain-list-\(domain.rawValue)")
    }

    private var countHeader: some View {
        HStack {
            Text("\(records.count) רשומות")
                .font(.byCaption)
                .foregroundStyle(BYTheme.textSecondary)
                .accessibilityIdentifier("record-count")
            Spacer()
            if domain == .paymentsTransfer {
                let total = records.compactMap { $0.number("amount") }.reduce(0, +)
                Text(Formatters.currencyValue(total, detailed: true))
                    .font(.byCaption.weight(.bold))
                    .foregroundStyle(BYTheme.textPrimary)
                    .accessibilityIdentifier("payments-filter-total")
            }
        }
        .padding(.horizontal, 4)
        .padding(.bottom, 2)
    }

    /// צבעי התחומים — זהים לתגי השורות (StatusBadge) ולחלוקת הצבעים בדסקטופ.
    static func customerDomainTint(_ value: String) -> Color {
        switch value {
        case "construction": return BYTheme.Palette.brown
        case "textile": return BYTheme.Palette.teal
        case "supplier": return BYTheme.Palette.indigo
        case "graphic_web": return BYTheme.Palette.purple
        default: return BYTheme.Palette.blue
        }
    }

    /// סינון לקוחות לפי סוג — כמו תחומי הלקוחות בדסקטופ; טוגל: לחיצה שנייה מבטלת.
    private var customerTypeFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(CustomerDomains.options) { option in
                    let isActive = customerTypeFilter == option.value
                    let tint = Self.customerDomainTint(option.value)
                    Button {
                        Haptics.tap()
                        withAnimation(.snappy(duration: 0.18)) {
                            customerTypeFilter = isActive ? nil : option.value
                        }
                    } label: {
                        Text(option.short)
                            .font(.byCaption.weight(.semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(isActive ? tint : tint.opacity(0.13))
                            .foregroundStyle(isActive ? Color.white : tint)
                            .clipShape(Capsule())
                    }
                    .accessibilityIdentifier("customer-type-\(option.value.isEmpty ? "none" : option.value)")
                }
            }
            .padding(.horizontal, 2)
        }
        .padding(.bottom, 6)
    }

    /// חשבוניות ספקים — בורר מיון + צ'יפי מועדי דיווח, כמו כפתורי "חשבוניות 15.7.26"
    /// והמיון בטבלת הדסקטופ. הצ'יפים נגזרים מהמועדים שקיימים בשורות הטעונות.
    private var financeFilterBar: some View {
        let dueDates = FinanceInvoices.availableDueDates(session.records(for: domain))
        return VStack(alignment: .leading, spacing: 8) {
            Menu {
                ForEach(FinanceInvoices.Sort.allCases) { option in
                    Button {
                        Haptics.tap()
                        withAnimation(.snappy(duration: 0.18)) { financeSort = option }
                    } label: {
                        if financeSort == option {
                            Label(option.title, systemImage: "checkmark")
                        } else {
                            Label(option.title, systemImage: option.icon)
                        }
                    }
                    .accessibilityIdentifier("finance-sort-\(option.rawValue)")
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 12, weight: .semibold))
                    Text("מיון: \(financeSort.title)")
                        .font(.byCaption.weight(.semibold))
                        .lineLimit(1)
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(BYTheme.textSecondary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(BYTheme.cardBackground)
                .foregroundStyle(BYTheme.textPrimary)
                .clipShape(Capsule())
                .overlay(Capsule().strokeBorder(BYTheme.separator, lineWidth: 1))
            }
            .accessibilityIdentifier("finance-sort-menu")

            if !dueDates.isEmpty {
                // פריסת flow עוטפת — כמו צ'יפי הדומיינים; צ'יפים נגללים לא אמינים לאוטומציה.
                ChipFlowLayout(spacing: 8) {
                    ForEach(dueDates, id: \.self) { dueDate in
                        let isActive = financeReportFilter == dueDate
                        let tint = BYTheme.Palette.green
                        Button {
                            Haptics.tap()
                            withAnimation(.snappy(duration: 0.18)) {
                                financeReportFilter = isActive ? "" : dueDate
                            }
                        } label: {
                            HStack(spacing: 5) {
                                Image(systemName: "calendar.badge.checkmark")
                                    .font(.system(size: 11, weight: .semibold))
                                Text("דיווח \(FinanceInvoices.chipLabel(dueDate))")
                                    .font(.byCaption.weight(.semibold))
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(isActive ? tint : tint.opacity(0.13))
                            .foregroundStyle(isActive ? Color.white : tint)
                            .clipShape(Capsule())
                        }
                        .accessibilityIdentifier("finance-report-filter")
                    }
                }
            }
        }
        .padding(.bottom, 6)
    }

    /// סינון תיקי התקנה לפי סטטוס — צ'יפים צבעוניים גלויים, טוגל כמו בשאר הסינונים.
    private var installationsFilterBar: some View {
        VStack(spacing: 8) {
            Picker("שלב", selection: $installationsPhase) {
                ForEach(InstallationsPhase.allCases, id: \.self) { phase in
                    Text(phase.title).tag(phase)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("installations-phase-filter")
            installationsStatusChips
        }
        .padding(.bottom, 6)
    }

    private var installationsStatusChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(APIClient.installationStatusOptions, id: \.self) { option in
                    let isActive = installationsStatusFilter == option
                    let tint = InstallationStatus.tint(option)
                    Button {
                        Haptics.tap()
                        withAnimation(.snappy(duration: 0.18)) {
                            installationsStatusFilter = isActive ? "" : option
                        }
                    } label: {
                        Text(option)
                            .font(.byCaption.weight(.semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(isActive ? tint : tint.opacity(0.13))
                            .foregroundStyle(isActive ? Color.white : tint)
                            .clipShape(Capsule())
                    }
                    .accessibilityIdentifier("installations-status-filter")
                }
            }
            .padding(.horizontal, 2)
        }
        .padding(.bottom, 6)
    }

    /// עובדים פעילים מול עובדי עבר — מקבילה למתג התצוגה בדסקטופ, כולל המונים.
    private var hrViewFilterBar: some View {
        let all = session.records(for: .hrEmployees)
        let formerCount = all.filter(HREmployees.isFormer).count
        return VStack(spacing: 8) {
            Picker("תצוגה", selection: $hrShowFormer) {
                Text("עובדים פעילים (\(all.count - formerCount))").tag(false)
                Text("עובדי עבר (\(formerCount))").tag(true)
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("hr-view-filter")
            if hrShowFormer {
                Text("עובדים שסיימו את העסקתם. הנתונים שלהם מוצגים לצפייה בלבד.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .accessibilityIdentifier("hr-view-former-note")
            }
        }
        .padding(.bottom, 6)
    }

    /// סרגל אישורי מסירה — שני כפתורי הסינון של הדסקטופ, עם מוני הצדדים.
    private var deliveryFilterBar: some View {
        let all = session.records(for: .deliveryConfirmations)
        let sentCount = all.filter(DeliveryConfirmations.isSent).count
        let pendingCount = all.count - sentCount
        return VStack(spacing: 8) {
            Picker("סטטוס", selection: $deliverySent) {
                Text("טרם נשלח").tag(false)
                Text("נשלח").tag(true)
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("delivery-sent-filter")

            Text("\(pendingCount) ממתינות לשליחה · \(sentCount) כבר נשלחו")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .accessibilityIdentifier("delivery-sent-summary")
        }
        .padding(.bottom, 6)
    }

    /// סרגל הסינון של תשלומים והעברות — שיקוף כפתורי הדסקטופ.
    private var paymentsFilterBar: some View {
        VStack(spacing: 10) {
            Picker("כיוון", selection: $paymentsDirection) {
                ForEach(PaymentsDirection.allCases, id: \.self) { direction in
                    Text(direction.title).tag(direction)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("payments-direction")

            HStack(spacing: 8) {
                statusChip(.paid, id: "payments-status-paid", tint: BYTheme.Palette.green)
                statusChip(.open, id: "payments-status-open", tint: BYTheme.Palette.blue)
                statusChip(.overdue, id: "payments-status-overdue", tint: BYTheme.Palette.red)
            }
            paymentsDateBar
            paymentsLetterBar
        }
        .padding(.bottom, 6)
    }

    /// טווח תאריכים מעל סינון הסטטוס — לפי מועד או לפי תאריך החשבונית.
    private var paymentsDateBar: some View {
        VStack(spacing: 8) {
            Picker("שדה תאריך", selection: $paymentsDateField) {
                ForEach(PaymentsDateField.allCases, id: \.self) { field in
                    Text(field.title(paymentsDirection)).tag(field)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("payments-date-field")

            HStack(spacing: 10) {
                dateSlot("מ־", date: $paymentsFrom, id: "payments-date-from")
                dateSlot("עד", date: $paymentsTo, id: "payments-date-to")
                if paymentsFrom != nil || paymentsTo != nil {
                    Button {
                        Haptics.tap()
                        paymentsFrom = nil
                        paymentsTo = nil
                    } label: {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(BYTheme.Palette.red)
                    }
                    .accessibilityIdentifier("payments-date-clear")
                }
            }
        }
    }

    private func dateSlot(_ label: String, date: Binding<Date?>, id: String) -> some View {
        HStack(spacing: 4) {
            Text(label).font(.byCaption).foregroundStyle(BYTheme.textSecondary)
            DatePicker(
                label,
                selection: Binding(get: { date.wrappedValue ?? Date() }, set: { date.wrappedValue = $0 }),
                displayedComponents: .date
            )
            .labelsHidden()
            .opacity(date.wrappedValue == nil ? 0.55 : 1)
            .accessibilityIdentifier(id)
        }
    }

    /// סינון לפי האות הראשונה של שם הלקוח. האותיות נגזרות אחרי הסטטוס והתאריכים,
    /// כדי שלא תוצג אות שתחזיר רשימה ריקה.
    private var paymentsLetterBar: some View {
        var rows = session.records(for: .paymentsTransfer)
        let buckets = PaymentsMath.categorize(rows)
        rows = paymentsDirection == .payment ? buckets.payment : buckets.collection
        if let paymentsStatus { rows = rows.filter { PaymentsMath.status(of: $0) == paymentsStatus } }
        if paymentsFrom != nil || paymentsTo != nil {
            rows = rows.filter { PaymentsFilters.inRange($0, field: paymentsDateField.key, from: paymentsFrom, to: paymentsTo) }
        }
        let letters = PaymentsFilters.availableLetters(rows)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(letters, id: \.self) { letter in
                    let isActive = paymentsLetter == letter
                    Button {
                        Haptics.tap()
                        withAnimation(.snappy(duration: 0.18)) {
                            paymentsLetter = isActive ? nil : letter
                        }
                    } label: {
                        Text(letter)
                            .font(.byCaption.weight(.bold))
                            .padding(.horizontal, 12).padding(.vertical, 6)
                            .background(isActive ? BYTheme.Palette.brand.opacity(0.16) : BYTheme.insetBackground)
                            .foregroundStyle(isActive ? BYTheme.Palette.brand : BYTheme.textSecondary)
                            .clipShape(Capsule())
                    }
                    .accessibilityIdentifier("payments-letter-\(letter)")
                }
            }
            .padding(.horizontal, 2)
        }
        .accessibilityIdentifier("payments-letter-filter")
    }

    private func statusChip(_ status: PaymentsMath.RowStatus, id: String, tint: Color) -> some View {
        let isActive = paymentsStatus == status
        return Button {
            Haptics.tap()
            // כמו בדסקטופ: לחיצה נוספת מבטלת את הסינון ומחזירה את כל הרשימה.
            withAnimation(.snappy(duration: 0.18)) {
                paymentsStatus = isActive ? nil : status
            }
        } label: {
            Text(paymentsDirection.statusLabel(status))
                .font(.byCaption.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(isActive ? tint : tint.opacity(0.12))
                .foregroundStyle(isActive ? Color.white : tint)
                .clipShape(Capsule())
        }
        .accessibilityIdentifier(id)
    }
}
