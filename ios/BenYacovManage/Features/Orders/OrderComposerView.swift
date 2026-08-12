import SwiftUI
import UniformTypeIdentifiers

/// זרימת הזמנת רכש מלאה: העלאת PDF → פרסור → עריכה → יצירת מסמכים (סנדבוקס/פרודקשן) → וואטסאפ.
struct OrderComposerView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    /// מילוי מוקדם (למשל בהמרת הצעת מחיר להזמנה).
    var initialFields: [String: String]? = nil
    /// מילוי מוקדם מרשומה מלאה כולל פריטים — "יצירת הזמנה" מתוך הזמנות בעבודה.
    var initialRecord: DomainRecord? = nil

    enum Step: Equatable {
        case pickFile
        case parsing
        case review
        case finalizing
        case done(String)
    }

    @State private var step: Step = .pickFile
    @State private var mode: String = "sandbox"
    @State private var sendWhatsapp = false
    @State private var sendToDad = false
    @State private var requiresInstallation = false
    @State private var showFileImporter = false
    @State private var parsed: DomainRecord?
    @State private var fields: [String: String] = [:]
    @State private var errorMessage: String?
    @State private var pdfData: Data?
    @State private var pdfFilename: String = ""
    @State private var isParking = false
    /// הזנה ידנית — מקבילה ל"יצירת הזמנה ידנית" בדסקטופ, בלי PDF.
    @State private var isManual = false
    @State private var manualItems: [ComposerItem] = [ComposerItem()]
    @State private var manualFooter = ""
    @State private var partialDelivery = false
    @State private var labelPerItem = false
    /// מלא / תעודת משלוח בלבד / חשבונית מס בלבד — כמו כפתורי היצירה בדסקטופ.
    @State private var documentMode = "full"

    private let manualFields: [(key: String, label: String)] = [
        ("po_number", "מספר הזמנה"),
        ("po_date", "תאריך הזמנה"),
        ("customer_name", "שם לקוח"),
        ("customer_id", "ח.פ / ע.מ"),
        ("customer_phone", "טלפון לקוח"),
        ("customer_email", "אימייל לקוח"),
        ("delivery_address", "כתובת אספקה"),
        ("project", "פרויקט"),
        ("contact_name", "איש קשר"),
        ("contact_phone", "טלפון איש קשר"),
    ]

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
                .background(BYTheme.screenBackground)
                .navigationTitle("הזמנת רכש חדשה")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("סגירה") { dismiss() }
                            .accessibilityIdentifier("composer-close")
                    }
                }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf]) { result in
            if case .success(let url) = result {
                loadFile(url: url)
            }
        }
        .accessibilityIdentifier("order-composer")
        .onDisappear {
            // הזמנה בעבודה שהושלמה — עכשיו בטוח לרענן; אם נוצרה בפרודקשן
            // השורה תרד מהרשימה ומסך הפירוט ייסגר מאחורינו.
            if initialRecord != nil, case .done = step {
                Task { await session.loadDomain(.workingOrders, force: true) }
            }
        }
        .onAppear {
            if let initialRecord, parsed == nil {
                // הזמנה בעבודה — ה-payload המפורסר כבר קיים, עוברים ישר לעריכה.
                parsed = initialRecord
                fields = Dictionary(uniqueKeysWithValues: editableFields.map { ($0.key, initialRecord[$0.key]) })
                step = .review
            } else if let initialFields, fields.isEmpty {
                fields = initialFields
                // בהמרה מהצעה אין PDF — עוברים ישר לעריכה כהזמנה ידנית.
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
            progressStep(text: "מפרסר את הזמנת הרכש…")
        case .review:
            reviewStep
        case .finalizing:
            progressStep(text: "יוצר מסמכים ב\(mode == "sandbox" ? "סנדבוקס" : "פרודקשן")…")
        case .done(let message):
            doneStep(message: message)
        }
    }

    // MARK: - שלב 1: בחירת קובץ

    private var pickFileStep: some View {
        ScrollView {
            VStack(spacing: 18) {
                BYCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("קובץ הזמנת רכש (PDF)", systemImage: "doc.badge.arrow.up.fill")
                            .font(.byRowTitle)
                        Text("העלה הזמנת רכש מהלקוח, המערכת תפרסר את הפרטים אוטומטית ותכין את המסמכים.")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        BYPrimaryButton(title: "בחירת קובץ PDF", icon: "folder.fill") {
                            showFileImporter = true
                        }
                        .accessibilityIdentifier("composer-pick-file")
                        Button {
                            Haptics.tap()
                            isManual = true
                            if fields["payment_terms_days"] == nil {
                                fields["payment_terms_days"] = "30"
                                fields["payment_terms_label"] = "שוטף + 30"
                            }
                            step = .review
                        } label: {
                            Label("יצירת הזמנה ידנית (בלי PDF)", systemImage: "square.and.pencil")
                                .font(.byCaption.weight(.semibold))
                        }
                        .accessibilityIdentifier("composer-manual-entry")
                        if AppConfig.isUITest {
                            BYPrimaryButton(title: "טעינת הזמנה לדוגמה", icon: "wand.and.stars", tint: BYTheme.Palette.teal) {
                                loadSampleFile()
                            }
                            .accessibilityIdentifier("composer-sample-file")
                        }
                    }
                }
                modeCard
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("composer-error")
                }
            }
            .padding(16)
        }
    }

    private var modeCard: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("מצב עבודה")
                    .font(.byRowTitle)
                Picker("מצב", selection: $mode) {
                    Text("סנדבוקס (בדיקה)").tag("sandbox")
                    Text("פרודקשן").tag("prod")
                }
                .pickerStyle(.segmented)
                .accessibilityIdentifier("composer-mode")
                Toggle(isOn: $sendWhatsapp) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("שליחת המסמכים בוואטסאפ")
                            .font(.byBody)
                        Text("כבוי = יצירת מסמכים בלבד, בלי שליחה")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                }
                .tint(BYTheme.Palette.green)
                .accessibilityIdentifier("composer-whatsapp-toggle")
                if sendWhatsapp {
                    Toggle(isOn: $sendToDad) {
                        Text("שלח גם לאבא")
                            .font(.byCaption.weight(.semibold))
                    }
                    .tint(BYTheme.Palette.green)
                    .padding(.top, 2)
                    .accessibilityIdentifier("composer-dad-toggle")
                }
            }
        }
    }

    // MARK: - שלב 2: סקירה ועריכה

    private var reviewStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                BYCard {
                    VStack(alignment: .leading, spacing: 4) {
                        Label(
                            isManual ? "הזמנה ידנית — מלא את הפרטים" : "ההזמנה פורסרה — בדוק ותקן לפני יצירה",
                            systemImage: isManual ? "square.and.pencil" : "checkmark.seal.fill"
                        )
                        .font(.byRowTitle)
                        .foregroundStyle(isManual ? BYTheme.Palette.brand : BYTheme.Palette.green)
                        if let parsed, !isManual {
                            Text("קובץ: \(parsed["source_file"])")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                        }
                    }
                }
                BYCard {
                    VStack(spacing: 4) {
                        ForEach(isManual ? manualFields : editableFields, id: \.key) { field in
                            LabeledContent {
                                TextField("", text: binding(field.key))
                                    .multilineTextAlignment(.leading)
                                    .font(.byBody)
                                    .accessibilityIdentifier("composer-field-\(field.key)")
                            } label: {
                                Text(field.label)
                                    .font(.byCaption.weight(.medium))
                                    .foregroundStyle(BYTheme.textSecondary)
                            }
                            .padding(.vertical, 5)
                            Divider().overlay(BYTheme.separator)
                        }
                        Picker("תנאי תשלום", selection: paymentTermsBinding) {
                            ForEach(ComposerMath.paymentTerms, id: \.days) { term in
                                Text(term.label).tag(term.days)
                            }
                        }
                        .accessibilityIdentifier("composer-field-payment_terms")
                    }
                }
                if isManual {
                    BYCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Label("פריטים", systemImage: "tag.fill").font(.byRowTitle)
                            ComposerItemsEditor(items: $manualItems, idPrefix: "order")
                            Divider()
                            ComposerTotalsView(items: manualItems, idPrefix: "order")
                        }
                    }
                    BYCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Label("אפשרויות", systemImage: "slider.horizontal.3").font(.byRowTitle)
                            Toggle("אספקה חלקית", isOn: $partialDelivery)
                                .accessibilityIdentifier("composer-partial-delivery")
                            Toggle("מדבקה לפי שורה", isOn: $labelPerItem)
                                .accessibilityIdentifier("composer-label-per-item")
                            Picker("מה ליצור", selection: $documentMode) {
                                Text("מלא").tag("full")
                                Text("ת. משלוח").tag("delivery_only")
                                Text("חשבונית").tag("invoice_only")
                            }
                            .pickerStyle(.segmented)
                            .accessibilityIdentifier("composer-document-mode")
                            VStack(alignment: .leading, spacing: 6) {
                                Text("הערות למסמכים")
                                    .font(.byCaption.weight(.medium))
                                    .foregroundStyle(BYTheme.textSecondary)
                                TextField("", text: $manualFooter, axis: .vertical)
                                    .lineLimit(2...5)
                                    .padding(10)
                                    .background(BYTheme.insetBackground)
                                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                                    .accessibilityIdentifier("composer-footer-text")
                            }
                        }
                    }
                } else {
                    itemsCard
                    totalsCard
                }
                modeCard
                BYPrimaryButton(
                    title: mode == "sandbox" ? "יצירת מסמכים בסנדבוקס" : "יצירת מסמכים בפרודקשן",
                    icon: "doc.on.doc.fill",
                    tint: mode == "sandbox" ? BYTheme.Palette.teal : BYTheme.Palette.brand
                ) {
                    Task { await finalize() }
                }
                .accessibilityIdentifier("composer-finalize")
                // חלופה: לשמור את ההזמנה ל"בעבודה" בלי ליצור מסמכים עדיין.
                // רלוונטי רק כשהגענו מקובץ PDF — לא בהמרת הצעה או בהזמנה שכבר בעבודה.
                if pdfData != nil {
                Toggle(isOn: $requiresInstallation) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("ההזמנה דורשת התקנה")
                            .font(.byCaption.weight(.semibold))
                        Text("ייפתח תיק התקנה כשההזמנה תושלם")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                }
                .tint(BYTheme.Palette.indigo)
                .padding(.horizontal, 4)
                .accessibilityIdentifier("composer-installation-toggle")
                Button {
                    Haptics.tap()
                    Task { await parkInWorkingOrders() }
                } label: {
                    HStack {
                        if isParking { ProgressView() } else { Image(systemName: "tray.and.arrow.down") }
                        Text("שמירה להזמנות בעבודה (בלי מסמכים)")
                        Spacer()
                    }
                    .font(.byRowTitle)
                    .padding(.vertical, 14)
                    .padding(.horizontal, 16)
                    .background(BYTheme.cardBackground)
                    .foregroundStyle(BYTheme.textPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .disabled(isParking)
                .accessibilityIdentifier("composer-park")
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("composer-error")
                }
            }
            .padding(16)
        }
    }

    @ViewBuilder
    private var itemsCard: some View {
        if let parsed, case .array(let items)? = parsed.fields["items"], !items.isEmpty {
            BYCard {
                VStack(alignment: .leading, spacing: 8) {
                    Text("פריטים (\(items.count))")
                        .font(.byRowTitle)
                    ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                        if case .object(let itemFields) = item {
                            let record = DomainRecord(fields: itemFields)
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(record["description"])
                                        .font(.byBody)
                                        .lineLimit(2)
                                    Text("כמות: \(record["quantity"]) · מחיר יחידה: \(record["unit_price"])")
                                        .font(.byCaption)
                                        .foregroundStyle(BYTheme.textSecondary)
                                }
                                Spacer()
                                Text(Formatters.currencyText(record["line_total"]))
                                    .font(.byNumber(14, weight: .semibold))
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var totalsCard: some View {
        if let parsed {
            BYCard {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("לפני מע\"מ: \(Formatters.currencyText(parsed["subtotal"], detailed: true))")
                        Text("מע\"מ: \(Formatters.currencyText(parsed["vat"], detailed: true))")
                    }
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.textSecondary)
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("סה\"כ")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        Text(Formatters.currencyText(parsed["total"], detailed: true))
                            .font(.byNumber(22))
                            .foregroundStyle(BYTheme.Palette.brand)
                            .accessibilityIdentifier("composer-total")
                    }
                }
            }
        }
    }

    // MARK: - שלבי ביניים וסיום

    private func progressStep(text: String) -> some View {
        VStack(spacing: 16) {
            ProgressView()
                .controlSize(.large)
            Text(text)
                .font(.byRowTitle)
                .foregroundStyle(BYTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityIdentifier("composer-progress")
    }

    private func doneStep(message: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(BYTheme.Palette.green)
                .accessibilityIdentifier("composer-done")
            Text(message)
                .font(.byTitle)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .accessibilityIdentifier("composer-done-message")
            BYPrimaryButton(title: "סגירה", icon: "checkmark") {
                dismiss()
            }
            .padding(.horizontal, 40)
            .accessibilityIdentifier("composer-done-close")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - לוגיקה

    private func binding(_ key: String) -> Binding<String> {
        Binding(get: { fields[key] ?? "" }, set: { fields[key] = $0 })
    }

    private func loadFile(url: URL) {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else {
            errorMessage = "לא הצלחתי לקרוא את הקובץ."
            return
        }
        Task { await parse(data: data, filename: url.lastPathComponent) }
    }

    private func loadSampleFile() {
        let bundles = [Bundle.main]
        for bundle in bundles {
            if let url = bundle.url(forResource: "sample_po", withExtension: "pdf", subdirectory: "Fixtures")
                ?? bundle.url(forResource: "sample_po", withExtension: "pdf"),
               let data = try? Data(contentsOf: url) {
                Task { await parse(data: data, filename: "sample_po.pdf") }
                return
            }
        }
        errorMessage = "קובץ הדוגמה לא נמצא."
    }

    private func parse(data: Data, filename: String) async {
        step = .parsing
        errorMessage = nil
        pdfData = data
        pdfFilename = filename
        do {
            let record = try await session.api.processPurchaseOrder(pdf: data, filename: filename, mode: mode)
            parsed = record
            for field in editableFields {
                fields[field.key] = record[field.key]
            }
            step = .review
            Haptics.success()
        } catch {
            errorMessage = (error as? APIError)?.message ?? "הפרסור נכשל: \(error.localizedDescription)"
            step = .pickFile
            Haptics.error()
        }
    }

    private func parkInWorkingOrders() async {
        guard let pdfData else { return }
        isParking = true
        defer { isParking = false }
        let api = session.api
        let filename = pdfFilename
        let succeeded = await session.perform(
            "ההזמנה נשמרה בהזמנות בעבודה.", refreshing: [.workingOrders]
        ) {
            try await api.uploadWorkingOrder(pdf: pdfData, filename: filename, requiresInstallation: requiresInstallation)
        }
        if succeeded {
            step = .done("ההזמנה נשמרה בהזמנות בעבודה — אפשר להפיק מסמכים בהמשך.")
        }
    }

    private var paymentTermsBinding: Binding<String> {
        Binding(
            get: { fields["payment_terms_days"] ?? "30" },
            set: { days in
                fields["payment_terms_days"] = days
                fields["payment_terms_label"] = ComposerMath.paymentTerms.first { $0.days == days }?.label ?? ""
            }
        )
    }

    private func finalize() async {
        var data: [String: Any]
        if isManual {
            // אותם שדות חובה שהדסקטופ אוכף ב-validateBeforeSend.
            let required: [(String, String)] = [
                ("po_number", "מספר הזמנה"),
                ("po_date", "תאריך הזמנה"),
                ("customer_name", "שם לקוח"),
                ("customer_id", "ח.פ / ע.מ"),
                ("delivery_address", "כתובת אספקה"),
            ]
            if let missing = required.first(where: { (fields[$0.0] ?? "").trimmingCharacters(in: .whitespaces).isEmpty }) {
                errorMessage = "\(missing.1) הוא שדה חובה."
                Haptics.error()
                return
            }
            let complete = manualItems.filter(\.isComplete)
            let subtotal = ComposerMath.subtotal(of: manualItems)
            guard !complete.isEmpty, subtotal > 0 else {
                errorMessage = "יש למלא לפחות פריט אחד עם תיאור, כמות ומחיר."
                Haptics.error()
                return
            }
            data = fields
            data["manual_entry"] = true
            data["manual_document_kind"] = "order"
            data["mode"] = "manual"
            data["source_file"] = "manual-order"
            data["footer_text"] = manualFooter
            data["partial_delivery"] = partialDelivery
            data["label_per_item"] = labelPerItem
            let payloads = complete.map(\.payload)
            data["items"] = payloads
            data["ordered_items"] = payloads
            if let first = complete.first {
                data["item_description"] = first.description
                data["item_sku"] = first.sku
                data["item_unit"] = first.unit
                data["item_quantity"] = first.quantityValue
                data["item_unit_price"] = first.unitPriceValue
            }
            data["subtotal"] = subtotal
            data["vat"] = ComposerMath.vat(subtotal)
            data["total"] = ComposerMath.total(subtotal)
        } else {
            guard let parsed else { return }
            data = parsed.jsonObject
            for (key, value) in fields { data[key] = value }
        }
        step = .finalizing
        errorMessage = nil
        do {
            data["send_to_dad"] = sendWhatsapp && sendToDad
            let message = try await session.api.finalizeOrder(
                mode: mode, data: data, skipWhatsapp: !sendWhatsapp,
                documentMode: isManual ? documentMode : "full"
            )
            await session.loadDomain(.orderHistory, force: true)
            // כשהגענו מהזמנה בעבודה, רענון הרשימה מעלים את הרשומה וסוגר את
            // מסך הפירוט (וגם אותנו) — דוחים אותו לסגירת הקומפוזר (onDisappear).
            if initialRecord == nil {
                await session.loadDomain(.workingOrders, force: true)
            }
            step = .done(message)
            session.showSuccess(message)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת המסמכים נכשלה."
            step = .review
            Haptics.error()
        }
    }
}
