import SwiftUI
import UniformTypeIdentifiers

// MARK: - עזרי UI משותפים לקומפוזרים של הקלאסי

struct ClassicCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) { content }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
    }
}

struct ClassicPrimaryButton: View {
    let title: String
    var icon: String = "checkmark"
    var isLoading = false
    var tint: Color = ClassicTheme.brand
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if isLoading { ProgressView().tint(.white) } else { Image(systemName: icon) }
                Text(title).font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(tint, in: RoundedRectangle(cornerRadius: 14))
            .foregroundColor(.white)
        }
        .disabled(isLoading)
    }
}

/// שורת שדה אחידה לקומפוזרים.
struct ClassicFieldRow: View {
    let label: String
    @Binding var text: String
    let identifier: String
    var keyboard: UIKeyboardType = .default

    var body: some View {
        LabeledContent(label) {
            TextField("", text: $text)
                .keyboardType(keyboard)
                .multilineTextAlignment(.leading)
                .accessibilityIdentifier(identifier)
        }
        .padding(.vertical, 3)
    }
}

/// מסך סיום אחיד — וי ירוק, הודעה וכפתור סגירה.
struct ClassicDoneView: View {
    let message: String
    var note: String = ""
    let idPrefix: String
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundColor(.green)
                .accessibilityIdentifier("\(idPrefix)-done")
            Text(message)
                .font(.title3.weight(.semibold))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .accessibilityIdentifier("\(idPrefix)-done-message")
            if !note.isEmpty {
                Text(note)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 30)
            }
            ClassicPrimaryButton(title: "סגירה", icon: "checkmark") { onClose() }
                .padding(.horizontal, 40)
                .accessibilityIdentifier("\(idPrefix)-done-close")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - קומפוזר הזמנת רכש

/// זרימת הזמנת רכש מלאה בקלאסי: העלאת PDF → פרסור → עריכה → יצירת מסמכים
/// (סנדבוקס/פרודקשן) → וואטסאפ. תומך גם במילוי מוקדם מהזמנה בעבודה או מהצעה.
struct ClassicOrderComposerView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    /// מילוי מוקדם שטוח (המרת הצעת מחיר להזמנה).
    var initialFields: [String: String]? = nil
    /// מילוי מוקדם מרשומה מלאה כולל פריטים ("יצירת הזמנה" מהזמנות בעבודה).
    var initialRecord: DomainRecord? = nil

    enum Step: Equatable {
        case pickFile
        case parsing
        case review
        case finalizing
        case done(String)
    }

    @State private var step: Step = .pickFile
    @State private var mode = "sandbox"
    @State private var sendWhatsapp = false
    @State private var sendToDad = false
    @State private var requiresInstallation = false
    @State private var showFileImporter = false
    @State private var parsed: DomainRecord?
    @State private var fields: [String: String] = [:]
    @State private var errorMessage: String?
    @State private var pdfData: Data?
    @State private var pdfFilename = ""
    @State private var isParking = false

    private let editableFields: [(key: String, label: String)] = [
        ("customer_name", "שם לקוח"),
        ("customer_id", "ח.פ לקוח"),
        ("po_number", "מס' הזמנה"),
        ("po_date", "תאריך הזמנה"),
        ("delivery_address", "כתובת אספקה"),
        ("project", "פרויקט"),
        ("contact_name", "איש קשר"),
        ("contact_phone", "טלפון איש קשר"),
        ("payment_terms_label", "תנאי תשלום"),
    ]

    var body: some View {
        NavigationStack {
            content
                .background(ClassicTheme.screen)
                .navigationTitle("הזמנת רכש חדשה")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("סגירה") { dismiss() }
                            .accessibilityIdentifier("classic-composer-close")
                    }
                }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf]) { result in
            if case .success(let url) = result {
                loadFile(url: url)
            }
        }
        .accessibilityIdentifier("classic-order-composer")
        .onDisappear {
            // כמו בראשית: רענון "בעבודה" נדחה לכאן כדי שמסך הסיום לא ייסגר מוקדם.
            if initialRecord != nil, case .done = step {
                Task { await session.loadDomain(.workingOrders, force: true) }
            }
        }
        .onAppear {
            if let initialRecord, parsed == nil {
                parsed = initialRecord
                fields = Dictionary(uniqueKeysWithValues: editableFields.map { ($0.key, initialRecord[$0.key]) })
                step = .review
            } else if let initialFields, fields.isEmpty {
                fields = initialFields
                if parsed == nil {
                    parsed = DomainRecord(fields: initialFields.mapValues { .string($0) })
                    step = .review
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .pickFile:
            pickFileStep
        case .parsing:
            progressStep("מפרסר את הזמנת הרכש…")
        case .review:
            reviewStep
        case .finalizing:
            progressStep("יוצר מסמכים ב\(mode == "sandbox" ? "סנדבוקס" : "פרודקשן")…")
        case .done(let message):
            ClassicDoneView(
                message: message,
                note: "ההזמנה מופיעה בהיסטוריית ההזמנות.",
                idPrefix: "classic-composer"
            ) { dismiss() }
        }
    }

    private var pickFileStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    Label("קובץ הזמנת רכש (PDF)", systemImage: "doc.badge.arrow.up.fill")
                        .font(.headline)
                    Text("העלה הזמנת רכש מהלקוח, המערכת תפרסר את הפרטים אוטומטית ותכין את המסמכים.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    ClassicPrimaryButton(title: "בחירת קובץ PDF", icon: "folder.fill") {
                        showFileImporter = true
                    }
                    .accessibilityIdentifier("classic-composer-pick-file")
                    if AppConfig.isUITest {
                        ClassicPrimaryButton(title: "טעינת הזמנה לדוגמה", icon: "wand.and.stars", tint: .teal) {
                            loadSampleFile()
                        }
                        .accessibilityIdentifier("classic-composer-sample-file")
                    }
                }
                modeCard
                if let errorMessage {
                    errorLabel(errorMessage)
                }
            }
            .padding(16)
        }
    }

    private var modeCard: some View {
        ClassicCard {
            Text("מצב עבודה").font(.headline)
            Picker("מצב", selection: $mode) {
                Text("סנדבוקס (בדיקה)").tag("sandbox")
                Text("פרודקשן").tag("prod")
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("classic-composer-mode")
            Toggle(isOn: $sendWhatsapp) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("שליחת המסמכים בוואטסאפ").font(.subheadline)
                    Text("כבוי = יצירת מסמכים בלבד, בלי שליחה")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .tint(.green)
            .accessibilityIdentifier("classic-composer-whatsapp-toggle")
            if sendWhatsapp {
                Toggle(isOn: $sendToDad) {
                    Text("שלח גם לאבא").font(.caption.weight(.semibold))
                }
                .tint(.green)
                .accessibilityIdentifier("classic-composer-dad-toggle")
            }
        }
    }

    private var reviewStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    Label("ההזמנה מוכנה — בדוק ותקן לפני יצירה", systemImage: "checkmark.seal.fill")
                        .font(.headline)
                        .foregroundColor(.green)
                }
                ClassicCard {
                    ForEach(editableFields, id: \.key) { field in
                        ClassicFieldRow(
                            label: field.label,
                            text: Binding(
                                get: { fields[field.key] ?? "" },
                                set: { fields[field.key] = $0 }
                            ),
                            identifier: "classic-composer-field-\(field.key)"
                        )
                        if field.key != editableFields.last?.key {
                            Divider()
                        }
                    }
                }
                itemsCard
                totalsCard
                modeCard
                ClassicPrimaryButton(
                    title: mode == "sandbox" ? "יצירת מסמכים בסנדבוקס" : "יצירת מסמכים בפרודקשן",
                    icon: "doc.on.doc.fill",
                    tint: mode == "sandbox" ? .teal : ClassicTheme.brand
                ) {
                    Task { await finalize() }
                }
                .accessibilityIdentifier("classic-composer-finalize")
                // שמירה ל"בעבודה" — רלוונטי רק כשהגענו מקובץ PDF.
                if pdfData != nil {
                    Toggle(isOn: $requiresInstallation) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("ההזמנה דורשת התקנה").font(.caption.weight(.semibold))
                            Text("ייפתח תיק התקנה כשההזמנה תושלם")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .tint(.indigo)
                    .padding(.horizontal, 4)
                    .accessibilityIdentifier("classic-composer-installation-toggle")
                    Button {
                        Task { await parkInWorkingOrders() }
                    } label: {
                        HStack {
                            if isParking { ProgressView() } else { Image(systemName: "tray.and.arrow.down") }
                            Text("שמירה להזמנות בעבודה (בלי מסמכים)").font(.headline)
                            Spacer()
                        }
                        .padding(14)
                        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
                        .foregroundColor(.primary)
                    }
                    .disabled(isParking)
                    .accessibilityIdentifier("classic-composer-park")
                }
                if let errorMessage {
                    errorLabel(errorMessage)
                }
            }
            .padding(16)
        }
    }

    @ViewBuilder
    private var itemsCard: some View {
        if let parsed, case .array(let items)? = parsed.fields["items"], !items.isEmpty {
            ClassicCard {
                Text("פריטים (\(items.count))").font(.headline)
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    if case .object(let itemFields) = item {
                        let record = DomainRecord(fields: itemFields)
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(record["description"]).font(.subheadline).lineLimit(2)
                                Text("כמות: \(record["quantity"]) · מחיר יחידה: \(record["unit_price"])")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Text(Formatters.currencyText(record["line_total"]))
                                .font(.subheadline.weight(.semibold).monospacedDigit())
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var totalsCard: some View {
        if let parsed {
            ClassicCard {
                HStack {
                    Text("סה\"כ כולל מע\"מ")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(Formatters.currencyText(parsed.first(of: ["total", "grand_total"])))
                        .font(.title3.weight(.bold).monospacedDigit())
                        .foregroundColor(ClassicTheme.brand)
                        .accessibilityIdentifier("classic-composer-total")
                }
            }
        }
    }

    private func progressStep(_ text: String) -> some View {
        VStack(spacing: 16) {
            ProgressView().controlSize(.large)
            Text(text).font(.headline).foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityIdentifier("classic-composer-progress")
    }

    private func errorLabel(_ message: String) -> some View {
        Label(message, systemImage: "exclamationmark.triangle.fill")
            .font(.caption.weight(.medium))
            .foregroundColor(.red)
            .accessibilityIdentifier("classic-composer-error")
    }

    // MARK: - לוגיקה

    private func loadFile(url: URL) {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else {
            errorMessage = "לא הצלחתי לקרוא את הקובץ."
            return
        }
        pdfData = data
        pdfFilename = url.lastPathComponent
        Task { await process() }
    }

    private func loadSampleFile() {
        if let url = Bundle.main.url(forResource: "sample_po", withExtension: "pdf", subdirectory: "Fixtures")
            ?? Bundle.main.url(forResource: "sample_po", withExtension: "pdf")
            ?? Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf", subdirectory: "Fixtures")
            ?? Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf"),
           let data = try? Data(contentsOf: url) {
            pdfData = data
            pdfFilename = url.lastPathComponent
            Task { await process() }
        } else {
            errorMessage = "קובץ הדוגמה לא נמצא."
        }
    }

    private func process() async {
        guard let pdfData else { return }
        step = .parsing
        errorMessage = nil
        do {
            let record = try await session.api.processPurchaseOrder(pdf: pdfData, filename: pdfFilename, mode: mode)
            parsed = record
            fields = Dictionary(uniqueKeysWithValues: editableFields.map { ($0.key, record[$0.key]) })
            step = .review
        } catch {
            errorMessage = (error as? APIError)?.message ?? "הפרסור נכשל."
            step = .pickFile
        }
    }

    private func finalize() async {
        guard let parsed else { return }
        step = .finalizing
        errorMessage = nil
        var data = parsed.jsonObject
        for (key, value) in fields { data[key] = value }
        data["send_to_dad"] = sendWhatsapp && sendToDad
        do {
            let message = try await session.api.finalizeOrder(
                mode: mode, data: data, skipWhatsapp: !sendWhatsapp
            )
            await session.loadDomain(.orderHistory, force: true)
            if initialRecord == nil {
                await session.loadDomain(.workingOrders, force: true)
            }
            step = .done(message)
            session.showSuccess(message)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת המסמכים נכשלה."
            step = .review
        }
    }

    private func parkInWorkingOrders() async {
        guard let pdfData else { return }
        isParking = true
        defer { isParking = false }
        let api = session.api
        let filename = pdfFilename
        let installation = requiresInstallation
        let succeeded = await session.perform(
            "ההזמנה נשמרה בהזמנות בעבודה.", refreshing: [.workingOrders]
        ) {
            try await api.uploadWorkingOrder(pdf: pdfData, filename: filename, requiresInstallation: installation)
        }
        if succeeded {
            step = .done("ההזמנה נשמרה בהזמנות בעבודה — אפשר להפיק מסמכים בהמשך.")
        }
    }
}

// MARK: - קומפוזר הצעות מחיר

/// הצעת מחיר בקלאסי: פרטי לקוח ופריט → יצירה ב-GreenInvoice (סנדבוקס/פרודקשן).
struct ClassicQuoteComposerView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    enum Step: Equatable {
        case form
        case working(String)
        case done(message: String)
    }

    @State private var step: Step = .form
    @State private var mode = "sandbox"
    @State private var fields: [String: String] = [
        "customer_name": "", "customer_id": "", "customer_email": "", "customer_phone": "",
        "delivery_address": "", "project": "", "contact_name": "", "contact_phone": "",
        "payment_terms_label": "שוטף + 30", "payment_terms_days": "30",
    ]
    @State private var itemDescription = ""
    @State private var itemQuantity = "1"
    @State private var itemUnitPrice = ""
    @State private var recentCustomers: [DomainRecord] = []
    @State private var errorMessage: String?

    private var subtotal: Double {
        (Double(itemQuantity) ?? 0) * (Double(itemUnitPrice) ?? 0)
    }

    var body: some View {
        NavigationStack {
            Group {
                switch step {
                case .form:
                    formStep
                case .working(let text):
                    VStack(spacing: 16) {
                        ProgressView().controlSize(.large)
                        Text(text).font(.headline).foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                case .done(let message):
                    ClassicDoneView(
                        message: message,
                        note: "שליחה ללקוח במייל או בוואטסאפ — מתוך ההצעה בטאב הצעות מחיר.",
                        idPrefix: "classic-quote"
                    ) { dismiss() }
                }
            }
            .background(ClassicTheme.screen)
            .navigationTitle("הצעת מחיר חדשה")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("classic-quote-close")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task {
            recentCustomers = (try? await session.api.recentManualCustomers()) ?? []
        }
        .scrollDismissesKeyboard(.immediately)
        .accessibilityIdentifier("classic-quote-composer")
    }

    private var formStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                ClassicCard {
                    HStack {
                        Label("פרטי הלקוח", systemImage: "person.fill").font(.headline)
                        Spacer()
                        if !recentCustomers.isEmpty {
                            Menu {
                                ForEach(recentCustomers.prefix(8)) { customer in
                                    Button(customer["customer_name"]) {
                                        fields["customer_name"] = customer["customer_name"]
                                        fields["customer_id"] = customer["customer_id"]
                                        fields["customer_phone"] = customer["customer_phone"]
                                        fields["customer_email"] = customer["customer_email"]
                                    }
                                }
                            } label: {
                                Label("לקוחות אחרונים", systemImage: "clock.arrow.circlepath")
                                    .font(.caption.weight(.bold))
                            }
                            .accessibilityIdentifier("classic-quote-recent-customers")
                        }
                    }
                    fieldRow("שם לקוח", key: "customer_name", id: "classic-quote-field-customer_name")
                    fieldRow("ח.פ / ע.מ", key: "customer_id", id: "classic-quote-field-customer_id")
                    fieldRow("אימייל", key: "customer_email", id: "classic-quote-field-customer_email")
                    fieldRow("טלפון", key: "customer_phone", id: "classic-quote-field-customer_phone")
                    fieldRow("כתובת אספקה", key: "delivery_address", id: "classic-quote-field-delivery_address")
                    fieldRow("פרויקט", key: "project", id: "classic-quote-field-project")
                    fieldRow("תנאי תשלום", key: "payment_terms_label", id: "classic-quote-field-terms")
                }
                ClassicCard {
                    Label("הפריט המוצע", systemImage: "tag.fill").font(.headline)
                    VStack(alignment: .leading, spacing: 6) {
                        Text("תיאור")
                            .font(.caption.weight(.medium))
                            .foregroundColor(.secondary)
                        TextField("", text: $itemDescription, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(10)
                            .background(ClassicTheme.screen, in: RoundedRectangle(cornerRadius: 10))
                            .accessibilityIdentifier("classic-quote-item-description")
                    }
                    HStack(spacing: 12) {
                        LabeledContent("כמות") {
                            TextField("", text: $itemQuantity)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("classic-quote-item-quantity")
                        }
                        LabeledContent("מחיר יח'") {
                            TextField("", text: $itemUnitPrice)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("classic-quote-item-price")
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
                            .accessibilityIdentifier("classic-quote-subtotal")
                    }
                }
                ClassicCard {
                    Text("מצב עבודה").font(.headline)
                    Picker("מצב", selection: $mode) {
                        Text("סנדבוקס (בדיקה)").tag("sandbox")
                        Text("פרודקשן").tag("prod")
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("classic-quote-mode")
                }
                ClassicPrimaryButton(
                    title: mode == "sandbox" ? "יצירת הצעה בסנדבוקס" : "יצירת הצעה בפרודקשן",
                    icon: "doc.text.fill",
                    tint: mode == "sandbox" ? .teal : ClassicTheme.brand
                ) {
                    Task { await create() }
                }
                .accessibilityIdentifier("classic-quote-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption.weight(.medium))
                        .foregroundColor(.red)
                        .accessibilityIdentifier("classic-quote-error")
                }
            }
            .padding(16)
        }
    }

    private func fieldRow(_ label: String, key: String, id: String) -> some View {
        ClassicFieldRow(
            label: label,
            text: Binding(
                get: { fields[key] ?? "" },
                set: { fields[key] = $0 }
            ),
            identifier: id
        )
    }

    private func create() async {
        guard !(fields["customer_name"] ?? "").trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "יש למלא שם לקוח."
            return
        }
        guard !itemDescription.trimmingCharacters(in: .whitespaces).isEmpty, subtotal > 0 else {
            errorMessage = "יש למלא תיאור פריט, כמות ומחיר."
            return
        }
        errorMessage = nil
        step = .working("יוצר את ההצעה ב\(mode == "sandbox" ? "סנדבוקס" : "פרודקשן")…")

        var data: [String: Any] = fields
        data["manual_entry"] = true
        let quantity = Double(itemQuantity) ?? 1
        let price = Double(itemUnitPrice) ?? 0
        data["items"] = [[
            "description": itemDescription, "sku": "", "unit": "יחידה",
            "quantity": quantity, "unit_price": price, "line_total": subtotal,
            "generate_label": false,
        ]]
        data["subtotal"] = subtotal
        data["vat"] = subtotal * 0.17
        data["total"] = subtotal * 1.17

        do {
            let result = try await session.api.finalizeQuote(mode: mode, data: data)
            await session.loadDomain(.quoteHistory, force: true)
            let quoteNumber = result.first(of: ["quote_document_number", "quote_number"])
            step = .done(message: quoteNumber.isEmpty ? "ההצעה נוצרה." : "הצעת מחיר \(quoteNumber) נוצרה.")
            session.showSuccess("הצעת המחיר נוצרה.")
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת ההצעה נכשלה."
            step = .form
        }
    }
}
