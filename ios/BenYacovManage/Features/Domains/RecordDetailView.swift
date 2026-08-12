import SwiftUI

/// מסך פירוט גנרי לרשומה — כותרת, פעולות קשר מהירות, כל השדות, ופעולות שרת.
struct RecordDetailView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    let domain: Domain
    let recordID: String

    @State private var pendingConfirmation: RecordAction?
    @State private var runningActionID: String?
    @State private var editSheet: EditFormKind?

    /// הרשומה החיה מהמטמון — כך מוטציות משתקפות מיד.
    private var record: DomainRecord? {
        session.records(for: domain).first { $0.id == recordID }
    }

    var body: some View {
        NavigationStack {
            Group {
                if let record {
                    detailContent(record)
                } else {
                    // הרשומה נמחקה — סוגרים.
                    Color.clear.onAppear { dismiss() }
                }
            }
            .background(BYTheme.screenBackground)
            .navigationTitle(domain.spec.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("close-detail")
                }
                if let record, let form = EditFormKind.form(for: domain) {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            Haptics.tap()
                            editSheet = form
                        } label: {
                            Label("עריכה", systemImage: "pencil")
                        }
                        .accessibilityIdentifier("edit-record")
                        .disabled(record.fields.isEmpty)
                    }
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .sheet(item: $editSheet) { form in
            if let record {
                RecordFormView(kind: form, domain: domain, existing: record)
            }
        }
        .confirmationDialog(
            pendingConfirmation?.confirmation ?? "",
            isPresented: Binding(
                get: { pendingConfirmation != nil },
                set: { if !$0 { pendingConfirmation = nil } }
            ),
            titleVisibility: .visible
        ) {
            if let action = pendingConfirmation {
                Button(action.title, role: action.style == .destructive ? .destructive : nil) {
                    Task { await run(action) }
                }
                .accessibilityIdentifier("confirm-action")
                Button("ביטול", role: .cancel) {}
                    .accessibilityIdentifier("cancel-action")
            }
        }
        .accessibilityIdentifier("record-detail")
    }

    @ViewBuilder
    private func detailContent(_ record: DomainRecord) -> some View {
        ScrollView {
            VStack(spacing: 14) {
                headerCard(record)
                contactCard(record)
                RecordExtrasSection(domain: domain, record: record)
                fieldsCard(record)
                actionsCard(record)
            }
            .padding(16)
        }
    }

    // MARK: - כותרת

    private func headerCard(_ record: DomainRecord) -> some View {
        BYCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 10) {
                    Image(systemName: domain.spec.icon)
                        .font(.system(size: 22, weight: .medium))
                        .foregroundStyle(domain.spec.tint.color)
                        .frame(width: 44, height: 44)
                        .background(domain.spec.tint.color.opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(record.first(of: domain.spec.titleKeys).isEmpty ? "ללא שם" : record.first(of: domain.spec.titleKeys))
                            .font(.byTitle)
                            .foregroundStyle(BYTheme.textPrimary)
                        if let badgeKey = domain.spec.badgeKey,
                           let badge = StatusBadge.styled(record[badgeKey]) {
                            StatusBadge(text: badge.text, tint: badge.tint)
                        }
                    }
                    Spacer()
                }
                if let amountKey = domain.spec.amountKey, !record[amountKey].isEmpty {
                    HStack {
                        Text(FieldLabels.label(for: amountKey))
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        Spacer()
                        Text(Formatters.currencyText(record[amountKey], detailed: true))
                            .font(.byNumber(24))
                            .foregroundStyle(domain.spec.tint.color)
                            .accessibilityIdentifier("detail-amount")
                    }
                    .padding(.top, 4)
                }
            }
        }
    }

    // MARK: - קשר מהיר

    private static let phoneKeys = ["phone", "mobile", "contact_phone", "customer_phone", "phone_1", "direct_phone", "company_phone"]
    private static let emailKeys = ["emails", "email", "customer_email", "target_email"]

    @ViewBuilder
    private func contactCard(_ record: DomainRecord) -> some View {
        let phone = record.first(of: Self.phoneKeys)
        let email = record.first(of: Self.emailKeys)
        if !phone.isEmpty || !email.isEmpty {
            BYCard(padding: 12) {
                HStack(spacing: 10) {
                    if !phone.isEmpty {
                        contactButton("חיוג", icon: "phone.fill", tint: BYTheme.Palette.blue, url: Formatters.callURL(phone: phone), id: "contact-call")
                        contactButton("וואטסאפ", icon: "message.fill", tint: BYTheme.Palette.green, url: Formatters.whatsappURL(phone: phone), id: "contact-whatsapp")
                    }
                    if !email.isEmpty {
                        contactButton("מייל", icon: "envelope.fill", tint: BYTheme.Palette.amber, url: Formatters.mailURL(email), id: "contact-mail")
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func contactButton(_ title: String, icon: String, tint: Color, url: URL?, id: String) -> some View {
        if let url {
            Link(destination: url) {
                VStack(spacing: 5) {
                    Image(systemName: icon)
                        .font(.system(size: 17, weight: .semibold))
                    Text(title)
                        .font(.byCaption.weight(.semibold))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(tint.opacity(0.12))
                .foregroundStyle(tint)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .accessibilityIdentifier(id)
        }
    }

    // MARK: - שדות

    private func orderedFields(_ record: DomainRecord) -> [(key: String, value: String)] {
        var result: [(String, String)] = []
        var used = Set<String>()
        for key in domain.spec.detailKeys {
            let value = record[key]
            if !value.isEmpty {
                result.append((key, value))
                used.insert(key)
            }
        }
        let remaining = record.fields.keys
            .filter { !used.contains($0) && !FieldLabels.hiddenKeys.contains($0) }
            .sorted()
        for key in remaining {
            let value = record[key]
            if !value.isEmpty && value != "…" {
                result.append((key, value))
            }
        }
        return result
    }

    private func fieldsCard(_ record: DomainRecord) -> some View {
        BYCard {
            VStack(spacing: 0) {
                let fields = orderedFields(record)
                ForEach(Array(fields.enumerated()), id: \.offset) { index, field in
                    DetailFieldRow(
                        label: FieldLabels.label(for: field.key),
                        value: displayValue(key: field.key, raw: field.value),
                        isLink: FieldLabels.linkKeys.contains(field.key)
                    )
                    if index < fields.count - 1 {
                        Divider().overlay(BYTheme.separator)
                    }
                }
            }
        }
    }

    private func displayValue(key: String, raw: String) -> String {
        if FieldLabels.linkKeys.contains(key) { return raw }
        let dateHints = ["date", "_at", "month"]
        if dateHints.contains(where: key.contains) {
            let formatted = Formatters.dateText(raw)
            if !formatted.isEmpty { return formatted }
        }
        let moneyHints = ["amount", "total", "subtotal", "vat", "price", "salary", "balance", "cost"]
        if moneyHints.contains(where: key.contains), Double(raw.replacingOccurrences(of: ",", with: "").replacingOccurrences(of: "₪", with: "").trimmingCharacters(in: .whitespaces)) != nil {
            return Formatters.currencyText(raw, detailed: true)
        }
        return raw
    }

    // MARK: - פעולות

    @ViewBuilder
    private func actionsCard(_ record: DomainRecord) -> some View {
        let actions = DomainActionCatalog.actions(for: domain, record: record)
        if !actions.isEmpty {
            VStack(spacing: 10) {
                ForEach(actions) { action in
                    Button {
                        Haptics.tap()
                        if action.confirmation != nil {
                            pendingConfirmation = action
                        } else {
                            Task { await run(action) }
                        }
                    } label: {
                        HStack {
                            if runningActionID == action.id {
                                ProgressView()
                            } else {
                                Image(systemName: action.icon)
                            }
                            Text(action.title)
                            Spacer()
                        }
                        .font(.byRowTitle)
                        .padding(.vertical, 14)
                        .padding(.horizontal, 16)
                        .background(background(for: action.style))
                        .foregroundStyle(foreground(for: action.style))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .disabled(runningActionID != nil)
                    .accessibilityIdentifier("action-\(action.id)")
                }
            }
        }
    }

    private func background(for style: RecordAction.Style) -> Color {
        switch style {
        case .prominent: return BYTheme.Palette.brand
        case .destructive: return BYTheme.Palette.red.opacity(0.1)
        case .normal: return BYTheme.cardBackground
        }
    }

    private func foreground(for style: RecordAction.Style) -> Color {
        switch style {
        case .prominent: return .white
        case .destructive: return BYTheme.Palette.red
        case .normal: return BYTheme.textPrimary
        }
    }

    private func run(_ action: RecordAction) async {
        guard let record else { return }
        runningActionID = action.id
        defer { runningActionID = nil }
        let api = session.api
        let succeeded = await session.perform(action.successMessage, refreshing: action.refreshing) {
            try await action.run(api, record)
        }
        // אחרי מחיקה הרשומה נעלמת מהמטמון והמסך נסגר דרך ה-onAppear של המצב הריק.
        if succeeded && action.style == .destructive {
            dismiss()
        }
    }
}
