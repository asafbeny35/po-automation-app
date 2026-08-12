import SwiftUI

/// עטיפת Identifiable לשדות המרת הצעה — נדרש ל-sheet(item:).
struct ClassicConvertPayload: Identifiable {
    let fields: [String: String]
    var id: String { fields["customer_name"] ?? "convert" }
}

/// פירוט רשומה + כל הפעולות מהקטלוג המשותף (DomainActionCatalog).
struct ClassicRecordDetailView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    let domain: Domain
    let recordID: String

    @State private var pendingAction: RecordAction?
    @State private var runningActionID: String?
    @State private var editForm: EditFormKind?
    /// קומפוזר שנפתח מהרשומה — יצירת הזמנה מ"בעבודה" (רשומה מלאה) או המרת הצעה (שדות).
    @State private var composerRecord: DomainRecord?
    @State private var convertFields: ClassicConvertPayload?
    @State private var isLoadingConversion = false

    private var record: DomainRecord? {
        session.records(for: domain).first { $0.id == recordID }
    }

    var body: some View {
        NavigationStack {
            Group {
                if let record {
                    ScrollView {
                        VStack(spacing: 14) {
                            composerCard(record)
                            fieldsCard(record)
                            actionsCard(record)
                        }
                        .padding(16)
                    }
                } else {
                    Text("הרשומה עודכנה — סגור ורענן.")
                        .foregroundColor(.secondary)
                }
            }
            .background(ClassicTheme.screen)
            .navigationTitle(record?.first(of: domain.spec.titleKeys) ?? domain.spec.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("classic-close-detail")
                }
                if EditFormKind.form(for: domain) != nil {
                    ToolbarItem(placement: .primaryAction) {
                        Button("עריכה") { editForm = EditFormKind.form(for: domain) }
                            .accessibilityIdentifier("classic-edit")
                    }
                }
            }
        }
        .accessibilityIdentifier("classic-detail")
        .confirmationDialog(pendingAction?.confirmation ?? "", isPresented: Binding(
            get: { pendingAction != nil },
            set: { if !$0 { pendingAction = nil } }
        ), titleVisibility: .visible) {
            if let action = pendingAction {
                Button(action.title, role: action.style == .destructive ? .destructive : nil) {
                    Task { await run(action) }
                }
            }
            Button("ביטול", role: .cancel) {}
        }
        .sheet(item: $editForm) { form in
            ClassicRecordFormView(kind: form, domain: domain, existing: record)
        }
        .sheet(item: $composerRecord) { loaded in
            ClassicOrderComposerView(initialRecord: loaded)
        }
        .sheet(item: $convertFields) { payload in
            ClassicOrderComposerView(initialFields: payload.fields)
        }
    }

    /// כניסות לקומפוזרים מתוך הרשומה — כמו בדסקטופ ובאפליקציה הראשית.
    @ViewBuilder
    private func composerCard(_ record: DomainRecord) -> some View {
        if domain == .workingOrders {
            Button {
                openWorkingOrderComposer(record)
            } label: {
                HStack {
                    Image(systemName: "arrow.left.circle.fill")
                    Text("יצירת הזמנה").font(.headline)
                    Spacer()
                    Text("עריכה ויצירת מסמכים")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(14)
                .background(ClassicTheme.brand.opacity(0.1), in: RoundedRectangle(cornerRadius: 14))
                .foregroundColor(ClassicTheme.brand)
            }
            .accessibilityIdentifier("classic-working-order-create")
        } else if domain == .quoteHistory {
            Button {
                Task { await loadQuoteConversion(record) }
            } label: {
                HStack {
                    if isLoadingConversion { ProgressView() } else { Image(systemName: "arrow.left.circle.fill") }
                    Text("המרה להזמנה").font(.headline)
                    Spacer()
                }
                .padding(14)
                .background(ClassicTheme.brand.opacity(0.1), in: RoundedRectangle(cornerRadius: 14))
                .foregroundColor(ClassicTheme.brand)
            }
            .disabled(isLoadingConversion)
            .accessibilityIdentifier("classic-quote-convert")
        }
    }

    private func openWorkingOrderComposer(_ record: DomainRecord) {
        guard let data = record["payload_json"].data(using: .utf8),
              let decoded = try? JSONDecoder().decode([String: JSONValue].self, from: data),
              !decoded.isEmpty else {
            session.showError("נתוני ההזמנה פגומים — אי אפשר לטעון אותה למסך.")
            return
        }
        var fields = decoded
        // כמו בדסקטופ: finalize בפרודקשן מסיר את השורה מ"בעבודה" לפי המזהה הזה.
        fields["working_order_row_id"] = .string(record["row_id"])
        composerRecord = DomainRecord(fields: fields)
    }

    private func loadQuoteConversion(_ record: DomainRecord) async {
        isLoadingConversion = true
        defer { isLoadingConversion = false }
        do {
            let source = try await session.api.quoteOrderData(historyID: record["history_id"])
            var initial: [String: String] = [:]
            for key in ["customer_name", "customer_id", "po_number", "po_date", "delivery_address",
                        "project", "contact_name", "contact_phone", "payment_terms_label"] {
                initial[key] = source[key].isEmpty ? record[key] : source[key]
            }
            convertFields = ClassicConvertPayload(fields: initial)
        } catch {
            session.showError((error as? APIError)?.message ?? "טעינת נתוני ההצעה נכשלה.")
        }
    }

    private func fieldsCard(_ record: DomainRecord) -> some View {
        VStack(spacing: 0) {
            ForEach(domain.spec.detailKeys.filter { !record[$0].isEmpty }, id: \.self) { key in
                HStack(alignment: .top) {
                    Text(FieldLabels.label(for: key))
                        .font(.caption.weight(.semibold))
                        .foregroundColor(.secondary)
                        .frame(width: 120, alignment: .leading)
                    Text(record[key])
                        .font(.subheadline)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .padding(.vertical, 7)
                Divider()
            }
        }
        .padding(14)
        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
    }

    private func actionsCard(_ record: DomainRecord) -> some View {
        let actions = DomainActionCatalog.actions(for: domain, record: record)
        return VStack(spacing: 8) {
            ForEach(actions) { action in
                Button {
                    if action.confirmation != nil {
                        pendingAction = action
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
                        Text(action.title).font(.headline)
                        Spacer()
                    }
                    .padding(14)
                    .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
                    .foregroundColor(action.style == .destructive ? .red : .primary)
                }
                .disabled(runningActionID != nil)
                .accessibilityIdentifier("classic-action-\(action.id)")
            }
        }
    }

    private func run(_ action: RecordAction) async {
        guard let record else { return }
        runningActionID = action.id
        defer { runningActionID = nil }
        let api = session.api
        await session.perform(action.successMessage, refreshing: action.refreshing) {
            try await action.run(api, record)
        }
    }
}
