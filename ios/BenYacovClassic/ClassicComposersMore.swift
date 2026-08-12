import SwiftUI
import UniformTypeIdentifiers

// MARK: - קומפוזר הזמנת רכש לספק

/// הזמנת רכש לספק בקלאסי: בחירת ספק מאנשי הקשר במלאי, פריטים, יצירה בסנדבוקס/פרודקשן.
struct ClassicSupplierPOComposerView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    struct LineItem: Identifiable {
        let id = UUID()
        var description = ""
        var quantity = "1"
        var unitPrice = ""

        var lineTotal: Double { (Double(quantity) ?? 0) * (Double(unitPrice) ?? 0) }
    }

    @State private var mode = "sandbox"
    @State private var supplierName = ""
    @State private var supplierID = ""
    @State private var supplierEmail = ""
    @State private var supplierPhone = ""
    @State private var remarks = ""
    @State private var items: [LineItem] = [LineItem()]
    @State private var contacts: [DomainRecord] = []
    @State private var isCreating = false
    @State private var errorMessage: String?
    @State private var doneMessage: String?

    private var subtotal: Double { items.reduce(0) { $0 + $1.lineTotal } }

    var body: some View {
        NavigationStack {
            Group {
                if let doneMessage {
                    ClassicDoneView(
                        message: doneMessage,
                        note: "שליחה לספק במייל או בוואטסאפ — מתוך ההזמנה בטאב הזמנות רכש במלאי.",
                        idPrefix: "classic-supplier"
                    ) { dismiss() }
                } else {
                    formView
                }
            }
            .background(ClassicTheme.screen)
            .navigationTitle("הזמנת רכש לספק")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("classic-supplier-close")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task {
            await session.loadDomain(.inventoryContacts)
            contacts = session.records(for: .inventoryContacts)
        }
        .scrollDismissesKeyboard(.immediately)
        .accessibilityIdentifier("classic-supplier-composer")
    }

    private var formView: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    HStack {
                        Label("הספק", systemImage: "shippingbox.fill").font(.headline)
                        Spacer()
                        if !contacts.isEmpty {
                            Menu {
                                ForEach(contacts.prefix(15)) { contact in
                                    Button(contact.first(of: ["company", "supplier", "supplier_name", "name"])) {
                                        supplierName = contact.first(of: ["company", "supplier", "supplier_name", "name"])
                                        supplierEmail = contact.first(of: ["email", "supplier_email"])
                                        supplierPhone = contact.first(of: ["direct_phone", "phone", "company_phone", "supplier_phone"])
                                    }
                                }
                            } label: {
                                Label("מאנשי הקשר", systemImage: "person.crop.circle.badge.checkmark")
                                    .font(.caption.weight(.bold))
                            }
                            .accessibilityIdentifier("classic-supplier-picker")
                        }
                    }
                    ClassicFieldRow(label: "שם הספק", text: $supplierName, identifier: "classic-supplier-field-name")
                    ClassicFieldRow(label: "ח.פ", text: $supplierID, identifier: "classic-supplier-field-id", keyboard: .numberPad)
                    ClassicFieldRow(label: "אימייל", text: $supplierEmail, identifier: "classic-supplier-field-email", keyboard: .emailAddress)
                    ClassicFieldRow(label: "טלפון", text: $supplierPhone, identifier: "classic-supplier-field-phone", keyboard: .phonePad)
                }
                ClassicCard {
                    HStack {
                        Label("פריטים", systemImage: "list.bullet.rectangle").font(.headline)
                        Spacer()
                        Button {
                            items.append(LineItem())
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .font(.system(size: 20))
                                .foregroundColor(ClassicTheme.brand)
                        }
                        .accessibilityIdentifier("classic-supplier-add-item")
                    }
                    ForEach($items) { $item in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                TextField("תיאור הפריט", text: $item.description)
                                    .accessibilityIdentifier("classic-supplier-item-description")
                                if items.count > 1 {
                                    Button {
                                        items.removeAll { $0.id == item.id }
                                    } label: {
                                        Image(systemName: "minus.circle").foregroundColor(.red)
                                    }
                                }
                            }
                            HStack(spacing: 12) {
                                LabeledContent("כמות") {
                                    TextField("", text: $item.quantity)
                                        .keyboardType(.decimalPad)
                                        .multilineTextAlignment(.leading)
                                        .accessibilityIdentifier("classic-supplier-item-quantity")
                                }
                                LabeledContent("מחיר יח'") {
                                    TextField("", text: $item.unitPrice)
                                        .keyboardType(.decimalPad)
                                        .multilineTextAlignment(.leading)
                                        .accessibilityIdentifier("classic-supplier-item-price")
                                }
                            }
                            Divider()
                        }
                    }
                    HStack {
                        Text("סה\"כ לפני מע\"מ")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(Formatters.currencyValue(subtotal, detailed: true))
                            .font(.title3.weight(.bold).monospacedDigit())
                            .foregroundColor(.teal)
                            .accessibilityIdentifier("classic-supplier-subtotal")
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text("הערות")
                            .font(.caption.weight(.medium))
                            .foregroundColor(.secondary)
                        TextField("", text: $remarks, axis: .vertical)
                            .lineLimit(2...4)
                            .accessibilityIdentifier("classic-supplier-remarks")
                    }
                }
                ClassicCard {
                    Picker("מצב", selection: $mode) {
                        Text("סנדבוקס (בדיקה)").tag("sandbox")
                        Text("פרודקשן").tag("prod")
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("classic-supplier-mode")
                }
                ClassicPrimaryButton(
                    title: mode == "sandbox" ? "יצירת הזמנה בסנדבוקס" : "יצירת הזמנה בפרודקשן",
                    icon: "shippingbox.fill",
                    isLoading: isCreating,
                    tint: mode == "sandbox" ? .teal : ClassicTheme.brand
                ) {
                    Task { await create() }
                }
                .accessibilityIdentifier("classic-supplier-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.red)
                        .accessibilityIdentifier("classic-supplier-error")
                }
            }
            .padding(16)
        }
    }

    private func create() async {
        guard !supplierName.trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "יש למלא שם ספק."
            return
        }
        let validItems = items.filter { !$0.description.trimmingCharacters(in: .whitespaces).isEmpty && $0.lineTotal > 0 }
        guard !validItems.isEmpty else {
            errorMessage = "יש למלא לפחות פריט אחד עם כמות ומחיר."
            return
        }
        errorMessage = nil
        isCreating = true
        defer { isCreating = false }

        let payloadItems: [[String: Any]] = validItems.map { item in
            [
                "description": item.description, "sku": "", "unit": "יח׳",
                "quantity": Double(item.quantity) ?? 1,
                "unit_price": Double(item.unitPrice) ?? 0,
                "line_total": item.lineTotal,
            ]
        }
        do {
            try await session.api.createSupplierPO(
                mode: mode,
                supplier: [
                    "supplier_name": supplierName, "supplier_id": supplierID,
                    "supplier_email": supplierEmail, "supplier_phone": supplierPhone,
                ],
                items: payloadItems, remarks: remarks,
                subtotal: subtotal, vat: subtotal * 0.17, total: subtotal * 1.17
            )
            await session.loadDomain(.inventoryPurchaseOrders, force: true)
            doneMessage = "הזמנת הרכש לספק \(supplierName) נוצרה."
            session.showSuccess("הזמנת הרכש נוצרה.")
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת ההזמנה נכשלה."
        }
    }
}

// MARK: - העלאת חשבוניות ספקים

/// העלאת חשבוניות בקלאסי: קבצים → פרסור בשרת → סקירת טיוטות → שמירה לכספים.
struct ClassicInvoiceUploadView: View {
    @EnvironmentObject private var session: ClassicSession
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
                .background(ClassicTheme.screen)
                .navigationTitle("העלאת חשבונית")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("סגירה") { dismiss() }
                            .accessibilityIdentifier("classic-invoice-close")
                    }
                }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf], allowsMultipleSelection: true) { result in
            if case .success(let urls) = result {
                loadFiles(urls: urls)
            }
        }
        .accessibilityIdentifier("classic-invoice-upload")
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .pick:
            pickStep
        case .uploading:
            VStack(spacing: 16) {
                ProgressView().controlSize(.large)
                Text("מעלה ומפרסר את החשבוניות…").font(.headline).foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .review, .saving:
            reviewStep
        }
    }

    private var pickStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    Label("קובצי חשבוניות (PDF)", systemImage: "doc.plaintext.fill")
                        .font(.headline)
                    Text("החשבוניות יפורסרו אוטומטית ותוכל לאשר את הנתונים לפני שמירה לטבלת הכספים.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    ClassicPrimaryButton(title: "בחירת קבצים", icon: "folder.fill") {
                        showFileImporter = true
                    }
                    .accessibilityIdentifier("classic-invoice-pick-files")
                    if AppConfig.isUITest {
                        ClassicPrimaryButton(title: "טעינת חשבונית לדוגמה", icon: "wand.and.stars", tint: .teal) {
                            loadSample()
                        }
                        .accessibilityIdentifier("classic-invoice-sample-file")
                    }
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.red)
                        .accessibilityIdentifier("classic-invoice-error")
                }
            }
            .padding(16)
        }
    }

    private var reviewStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    Label("בדוק את הנתונים המפורסרים ושמור כל חשבונית", systemImage: "checkmark.seal.fill")
                        .font(.headline)
                        .foregroundColor(.green)
                }
                ForEach(drafts) { draft in
                    draftCard(draft)
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.red)
                        .accessibilityIdentifier("classic-invoice-error")
                }
            }
            .padding(16)
        }
    }

    private func draftCard(_ draft: DomainRecord) -> some View {
        ClassicCard {
            ForEach(draftFields, id: \.key) { field in
                LabeledContent {
                    TextField("", text: draftBinding(draft.id, field.key))
                        .multilineTextAlignment(.leading)
                        .font(.subheadline)
                        .disabled(savedDraftIDs.contains(draft.id))
                        .accessibilityIdentifier("classic-invoice-field-\(field.key)")
                } label: {
                    Text(field.label)
                        .font(.caption.weight(.medium))
                        .foregroundColor(.secondary)
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
                        Text("טרם שולמה").font(.caption.weight(.semibold))
                        Text("תצטרף גם ל'לתשלום' בתשלומים והעברות")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .tint(.teal)
                .padding(.vertical, 4)
                .accessibilityIdentifier("classic-invoice-unpaid-toggle")
            }
            if savedDraftIDs.contains(draft.id) {
                Label("נשמר לטבלת הכספים", systemImage: "checkmark.circle.fill")
                    .font(.headline)
                    .foregroundColor(.green)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 6)
                    .accessibilityIdentifier("classic-invoice-saved-badge")
            } else {
                ClassicPrimaryButton(title: "שמירה לטבלת הכספים", icon: "tray.and.arrow.down.fill",
                                     isLoading: step == .saving) {
                    Task { await save(draft: draft) }
                }
                .padding(.top, 6)
                .accessibilityIdentifier("classic-invoice-save-draft")
            }
        }
    }

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
        } catch {
            errorMessage = (error as? APIError)?.message ?? "ההעלאה נכשלה."
            step = .pick
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
        let payload = row
        let succeeded = await session.perform(
            markUnpaid ? "החשבונית נשמרה ונוספה גם ל'לתשלום'." : "החשבונית נשמרה לטבלת הכספים.",
            refreshing: markUnpaid ? [.financeInvoices, .paymentsTransfer] : [.financeInvoices]
        ) {
            try await api.saveInvoiceDraft(row: payload)
        }
        if succeeded {
            savedDraftIDs.insert(draft.id)
        }
        step = .review
    }
}

// MARK: - מדבקות משלוח

/// יצירת מדבקות משלוח בלי הזמנה — כמו הכלי בדסקטופ ובאפליקציה הראשית.
struct ClassicLabelsView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    struct LabelEntry: Identifiable {
        let id = UUID()
        var customer = ""
        var address = ""
        var contactName = ""
        var phone = ""
        var labelCount = "1"
    }

    @State private var entries: [LabelEntry] = [LabelEntry()]
    @State private var isSending = false
    @State private var errorMessage: String?
    @State private var doneMessage: String?
    @State private var recentCustomers: [DomainRecord] = []

    var body: some View {
        Group {
            if let doneMessage {
                ClassicDoneView(message: doneMessage, idPrefix: "classic-labels") { dismiss() }
            } else {
                formView
            }
        }
        .background(ClassicTheme.screen)
        .navigationTitle("מדבקות משלוח")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            recentCustomers = (try? await session.api.recentManualCustomers()) ?? []
        }
        .scrollDismissesKeyboard(.immediately)
    }

    private var formView: some View {
        ScrollView {
            VStack(spacing: 14) {
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("classic-labels-screen")
                ForEach($entries) { $entry in
                    ClassicCard {
                        HStack {
                            Label("מדבקה", systemImage: "tag.fill").font(.headline)
                            Spacer()
                            if !recentCustomers.isEmpty {
                                Menu {
                                    ForEach(recentCustomers.prefix(8)) { customer in
                                        Button(customer["customer_name"]) {
                                            entry.customer = customer["customer_name"]
                                            entry.phone = customer["customer_phone"]
                                        }
                                    }
                                } label: {
                                    Image(systemName: "clock.arrow.circlepath")
                                        .font(.system(size: 15, weight: .semibold))
                                }
                                .accessibilityIdentifier("classic-labels-recent-customers")
                            }
                            if entries.count > 1 {
                                Button {
                                    entries.removeAll { $0.id == entry.id }
                                } label: {
                                    Image(systemName: "minus.circle").foregroundColor(.red)
                                }
                            }
                        }
                        ClassicFieldRow(label: "לקוח", text: $entry.customer, identifier: "classic-labels-customer")
                        ClassicFieldRow(label: "כתובת", text: $entry.address, identifier: "classic-labels-address")
                        ClassicFieldRow(label: "איש קשר", text: $entry.contactName, identifier: "classic-labels-contact")
                        ClassicFieldRow(label: "טלפון", text: $entry.phone, identifier: "classic-labels-phone", keyboard: .phonePad)
                        ClassicFieldRow(label: "מספר מדבקות", text: $entry.labelCount, identifier: "classic-labels-count", keyboard: .numberPad)
                    }
                }
                Button {
                    entries.append(LabelEntry())
                } label: {
                    Label("הוספת מדבקה נוספת", systemImage: "plus.circle.fill")
                        .font(.subheadline.weight(.semibold))
                }
                .accessibilityIdentifier("classic-labels-add")
                ClassicPrimaryButton(title: "יצירת המדבקות", icon: "printer.fill", isLoading: isSending) {
                    Task { await create() }
                }
                .accessibilityIdentifier("classic-labels-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.red)
                        .accessibilityIdentifier("classic-labels-error")
                }
            }
            .padding(16)
        }
    }

    private func create() async {
        let valid = entries.filter { !$0.customer.trimmingCharacters(in: .whitespaces).isEmpty }
        guard !valid.isEmpty else {
            errorMessage = "יש למלא שם לקוח לפחות במדבקה אחת."
            return
        }
        errorMessage = nil
        isSending = true
        defer { isSending = false }
        let labels: [[String: Any]] = valid.map { entry in
            [
                "customer": entry.customer, "address": entry.address,
                "contact_name": entry.contactName, "phone": entry.phone,
                "label_count": Int(entry.labelCount) ?? 1,
            ]
        }
        do {
            let message = try await session.api.createLabelsOnly(labels: labels)
            doneMessage = message
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת המדבקות נכשלה."
        }
    }
}
