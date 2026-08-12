import SwiftUI
import UniformTypeIdentifiers

/// העלאת חשבוניות ספקים: קובץ → פרסור בשרת → סקירת טיוטה → שמירה לטאב כספים.
struct InvoiceUploadView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    enum Step: Equatable {
        case pick
        case uploading
        case review
        case saving
    }

    @State private var step: Step = .pick
    @State private var showFileImporter = false
    @State private var drafts: [DomainRecord] = []
    @State private var draftValues: [String: [String: String]] = [:]
    @State private var savedDraftIDs: Set<String> = []
    /// טיוטות שסומנו "טרם שולמה" — יצטרפו גם ל"לתשלום" בתשלומים והעברות.
    @State private var unpaidDraftIDs: Set<String> = []
    @State private var errorMessage: String?

    private let draftFields: [(key: String, label: String)] = [
        ("supplier_name", "ספק"),
        ("invoice_date", "תאריך חשבונית"),
        ("reference_number", "מס' אסמכתא"),
        ("service_or_product", "שירות / מוצר"),
        ("subtotal", "לפני מע\"מ"),
        ("vat", "מע\"מ"),
        ("total", "סה\"כ"),
    ]

    var body: some View {
        NavigationStack {
            content
                .background(BYTheme.screenBackground)
                .navigationTitle("העלאת חשבונית")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("סגירה") { dismiss() }
                            .accessibilityIdentifier("invoice-upload-close")
                    }
                }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf], allowsMultipleSelection: true) { result in
            if case .success(let urls) = result {
                loadFiles(urls: urls)
            }
        }
        .accessibilityIdentifier("invoice-upload")
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .pick:
            pickStep
        case .uploading:
            progress("מעלה ומפרסר את החשבוניות…")
        case .review, .saving:
            reviewStep
        }
    }

    private var pickStep: some View {
        ScrollView {
            VStack(spacing: 16) {
                BYCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("קובצי חשבוניות (PDF)", systemImage: "doc.plaintext.fill")
                            .font(.byRowTitle)
                        Text("החשבוניות יפורסרו אוטומטית ותוכל לאשר את הנתונים לפני שמירה לטבלת הכספים.")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        BYPrimaryButton(title: "בחירת קבצים", icon: "folder.fill") {
                            showFileImporter = true
                        }
                        .accessibilityIdentifier("invoice-pick-files")
                        if AppConfig.isUITest {
                            BYPrimaryButton(title: "טעינת חשבונית לדוגמה", icon: "wand.and.stars", tint: BYTheme.Palette.teal) {
                                loadSample()
                            }
                            .accessibilityIdentifier("invoice-sample-file")
                        }
                    }
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("invoice-error")
                }
            }
            .padding(16)
        }
    }

    private var reviewStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                BYCard {
                    Label("בדוק את הנתונים המפורסרים ושמור כל חשבונית", systemImage: "checkmark.seal.fill")
                        .font(.byRowTitle)
                        .foregroundStyle(BYTheme.Palette.green)
                }
                ForEach(drafts) { draft in
                    draftCard(draft)
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("invoice-error")
                }
            }
            .padding(16)
        }
    }

    private func draftCard(_ draft: DomainRecord) -> some View {
        BYCard {
            VStack(spacing: 6) {
                ForEach(draftFields, id: \.key) { field in
                    LabeledContent {
                        TextField("", text: draftBinding(draft.id, field.key))
                            .multilineTextAlignment(.leading)
                            .font(.byBody)
                            .disabled(savedDraftIDs.contains(draft.id))
                            .accessibilityIdentifier("invoice-field-\(field.key)")
                    } label: {
                        Text(field.label)
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                    .padding(.vertical, 3)
                }
                if !savedDraftIDs.contains(draft.id) {
                    Toggle(isOn: Binding(
                        get: { unpaidDraftIDs.contains(draft.id) },
                        set: { on in
                            if on { unpaidDraftIDs.insert(draft.id) } else { unpaidDraftIDs.remove(draft.id) }
                        }
                    )) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("טרם שולמה")
                                .font(.byCaption.weight(.semibold))
                            Text("תצטרף גם ל'לתשלום' בתשלומים והעברות")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                        }
                    }
                    .tint(BYTheme.Palette.teal)
                    .padding(.vertical, 4)
                    .accessibilityIdentifier("invoice-unpaid-toggle")
                }
                if savedDraftIDs.contains(draft.id) {
                    Label("נשמר לטבלת הכספים", systemImage: "checkmark.circle.fill")
                        .font(.byRowTitle)
                        .foregroundStyle(BYTheme.Palette.green)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 6)
                        .accessibilityIdentifier("invoice-saved-badge")
                } else {
                    BYPrimaryButton(title: "שמירה לטבלת הכספים", icon: "tray.and.arrow.down.fill",
                                    isLoading: step == .saving) {
                        Task { await save(draft: draft) }
                    }
                    .padding(.top, 6)
                    .accessibilityIdentifier("invoice-save-draft")
                }
            }
        }
    }

    private func progress(_ text: String) -> some View {
        VStack(spacing: 16) {
            ProgressView().controlSize(.large)
            Text(text)
                .font(.byRowTitle)
                .foregroundStyle(BYTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - לוגיקה

    private func draftBinding(_ draftID: String, _ key: String) -> Binding<String> {
        Binding(
            get: { draftValues[draftID]?[key] ?? "" },
            set: { draftValues[draftID, default: [:]][key] = $0 }
        )
    }

    private func loadFiles(urls: [URL]) {
        var files: [(String, Data)] = []
        for url in urls {
            let accessed = url.startAccessingSecurityScopedResource()
            defer { if accessed { url.stopAccessingSecurityScopedResource() } }
            if let data = try? Data(contentsOf: url) {
                files.append((url.lastPathComponent, data))
            }
        }
        guard !files.isEmpty else {
            errorMessage = "לא הצלחתי לקרוא את הקבצים."
            return
        }
        Task { await upload(files: files) }
    }

    private func loadSample() {
        if let url = Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf", subdirectory: "Fixtures")
            ?? Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf"),
           let data = try? Data(contentsOf: url) {
            Task { await upload(files: [("sample_invoice.pdf", data)]) }
        } else {
            errorMessage = "קובץ הדוגמה לא נמצא."
        }
    }

    private func upload(files: [(filename: String, data: Data)]) async {
        step = .uploading
        errorMessage = nil
        do {
            drafts = try await session.api.uploadInvoices(files: files)
            for draft in drafts {
                var values: [String: String] = [:]
                for field in draftFields {
                    values[field.key] = draft[field.key]
                }
                draftValues[draft.id] = values
            }
            step = .review
            Haptics.success()
        } catch {
            errorMessage = (error as? APIError)?.message ?? "ההעלאה נכשלה."
            step = .pick
            Haptics.error()
        }
    }

    private func save(draft: DomainRecord) async {
        step = .saving
        errorMessage = nil
        var row = draft.jsonObject
        for (key, value) in draftValues[draft.id] ?? [:] { row[key] = value }
        let markUnpaid = unpaidDraftIDs.contains(draft.id)
        if markUnpaid {
            // כמו הטוגל בדסקטופ: החשבונית מצטרפת גם ל"לתשלום".
            row["create_payable_row"] = "TRUE"
            if (row["supplier_invoice_number"] as? String ?? "").isEmpty {
                row["supplier_invoice_number"] = row["reference_number"] as? String ?? ""
            }
        }
        let api = session.api
        let succeeded = await session.perform(
            markUnpaid ? "החשבונית נשמרה ונוספה גם ל'לתשלום'." : "החשבונית נשמרה לטבלת הכספים.",
            refreshing: markUnpaid ? [.financeInvoices, .paymentsTransfer] : [.financeInvoices]
        ) {
            try await api.saveInvoiceDraft(row: row)
        }
        if succeeded {
            savedDraftIDs.insert(draft.id)
        }
        step = .review
    }
}
