import SwiftUI
import UniformTypeIdentifiers

/// קומפוזר הצעות מחיר: פרטי לקוח ופריט → יצירה ב-GreenInvoice (סנדבוקס/פרודקשן)
/// → מספר הצעה + שליחה. תומך גם בפרסור PDF וגם בהזנה ידנית עם לקוחות אחרונים.
struct QuoteComposerView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    enum Step: Equatable {
        case form
        case working(String)
        case done(quoteNumber: String, driveURL: String, message: String)
    }

    @State private var step: Step = .form
    @State private var mode: String = "sandbox"
    @State private var fields: [String: String] = [
        "po_number": "", "po_date": "",
        "customer_name": "", "customer_id": "", "customer_email": "", "customer_phone": "",
        "delivery_address": "", "project": "", "contact_name": "", "contact_phone": "",
        "payment_terms_label": "שוטף + 30", "payment_terms_days": "30",
    ]
    @State private var items: [ComposerItem] = [ComposerItem()]
    @State private var footerText = ""
    @State private var recentCustomers: [DomainRecord] = []
    @State private var errorMessage: String?
    @State private var showFileImporter = false

    private var subtotal: Double { ComposerMath.subtotal(of: items) }

    var body: some View {
        NavigationStack {
            content
                .background(BYTheme.screenBackground)
                .navigationTitle("הצעת מחיר חדשה")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("סגירה") { dismiss() }
                            .accessibilityIdentifier("quote-composer-close")
                    }
                }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task {
            recentCustomers = (try? await session.api.recentManualCustomers()) ?? []
        }
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf]) { result in
            if case .success(let url) = result {
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                if let data = try? Data(contentsOf: url) {
                    Task { await parse(data: data, filename: url.lastPathComponent) }
                }
            }
        }
        .scrollDismissesKeyboard(.immediately)
        .accessibilityIdentifier("quote-composer")
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .form:
            formStep
        case .working(let text):
            VStack(spacing: 16) {
                ProgressView().controlSize(.large)
                Text(text).font(.byRowTitle).foregroundStyle(BYTheme.textSecondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .done(let quoteNumber, let driveURL, let message):
            doneStep(quoteNumber: quoteNumber, driveURL: driveURL, message: message)
        }
    }

    private var formStep: some View {
        ScrollView {
            VStack(spacing: 14) {
                BYCard {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Label("פרטי הלקוח", systemImage: "person.fill")
                                .font(.byRowTitle)
                            Spacer()
                            if !recentCustomers.isEmpty {
                                Menu {
                                    ForEach(recentCustomers.prefix(8)) { customer in
                                        Button(customer["customer_name"]) {
                                            fields["customer_name"] = customer["customer_name"]
                                            fields["customer_id"] = customer["customer_id"]
                                            fields["customer_phone"] = customer["customer_phone"]
                                            fields["customer_email"] = customer["customer_email"]
                                            Haptics.tap()
                                        }
                                    }
                                } label: {
                                    Label("לקוחות אחרונים", systemImage: "clock.arrow.circlepath")
                                        .font(.byCaption.weight(.bold))
                                }
                                .accessibilityIdentifier("quote-recent-customers")
                            }
                        }
                        fieldRow("מספר הזמנה", key: "po_number", id: "quote-field-po_number")
                        fieldRow("תאריך הזמנה", key: "po_date", id: "quote-field-po_date")
                        fieldRow("שם לקוח", key: "customer_name", id: "quote-field-customer_name")
                        fieldRow("ח.פ / ע.מ", key: "customer_id", id: "quote-field-customer_id")
                        fieldRow("אימייל", key: "customer_email", id: "quote-field-customer_email")
                        fieldRow("טלפון", key: "customer_phone", id: "quote-field-customer_phone")
                        fieldRow("כתובת אספקה", key: "delivery_address", id: "quote-field-delivery_address")
                        fieldRow("פרויקט", key: "project", id: "quote-field-project")
                        fieldRow("איש קשר", key: "contact_name", id: "quote-field-contact_name")
                        fieldRow("טלפון איש קשר", key: "contact_phone", id: "quote-field-contact_phone")
                        Picker("תנאי תשלום", selection: paymentTermsBinding) {
                            ForEach(ComposerMath.paymentTerms, id: \.days) { term in
                                Text(term.label).tag(term.days)
                            }
                        }
                        .accessibilityIdentifier("quote-field-terms")
                    }
                }
                BYCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Label("הפריטים המוצעים", systemImage: "tag.fill")
                            .font(.byRowTitle)
                        ComposerItemsEditor(items: $items, idPrefix: "quote")
                        Divider()
                        ComposerTotalsView(items: items, idPrefix: "quote")
                    }
                }
                BYCard {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("הערות למסמכים", systemImage: "text.alignright")
                            .font(.byRowTitle)
                        TextField("", text: $footerText, axis: .vertical)
                            .lineLimit(3...6)
                            .padding(10)
                            .background(BYTheme.insetBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            .accessibilityIdentifier("quote-footer-text")
                    }
                }
                BYCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("מצב עבודה").font(.byRowTitle)
                        Picker("מצב", selection: $mode) {
                            Text("סנדבוקס (בדיקה)").tag("sandbox")
                            Text("פרודקשן").tag("prod")
                        }
                        .pickerStyle(.segmented)
                        .accessibilityIdentifier("quote-mode")
                        Button {
                            Haptics.tap()
                            showFileImporter = true
                        } label: {
                            Label("מילוי מתוך PDF של הזמנת רכש", systemImage: "doc.text.magnifyingglass")
                                .font(.byCaption.weight(.semibold))
                        }
                        .accessibilityIdentifier("quote-parse-pdf")
                    }
                }
                BYPrimaryButton(
                    title: mode == "sandbox" ? "יצירת הצעה בסנדבוקס" : "יצירת הצעה בפרודקשן",
                    icon: "doc.text.fill",
                    tint: mode == "sandbox" ? BYTheme.Palette.teal : BYTheme.Palette.brand
                ) {
                    Task { await create() }
                }
                .accessibilityIdentifier("quote-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("quote-error")
                }
            }
            .padding(16)
        }
    }

    private func doneStep(quoteNumber: String, driveURL: String, message: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(BYTheme.Palette.green)
                .accessibilityIdentifier("quote-done")
            Text(message)
                .font(.byTitle)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .accessibilityIdentifier("quote-done-message")
            if let url = URL(string: driveURL), !driveURL.isEmpty {
                Link(destination: url) {
                    Label("פתיחת ההצעה ב-Drive", systemImage: "arrow.up.right.square")
                        .font(.byRowTitle)
                }
                .accessibilityIdentifier("quote-done-drive")
            }
            Text("שליחה ללקוח במייל או בוואטסאפ — מתוך ההצעה בטאב הצעות מחיר.")
                .font(.byCaption)
                .foregroundStyle(BYTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 30)
            BYPrimaryButton(title: "סגירה", icon: "checkmark") { dismiss() }
                .padding(.horizontal, 40)
                .accessibilityIdentifier("quote-done-close")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func fieldRow(_ label: String, key: String, id: String) -> some View {
        LabeledContent(label) {
            TextField("", text: Binding(
                get: { fields[key] ?? "" },
                set: { fields[key] = $0 }
            ))
            .multilineTextAlignment(.leading)
            .accessibilityIdentifier(id)
        }
    }

    private func parse(data: Data, filename: String) async {
        step = .working("מפרסר את הקובץ…")
        do {
            let parsed = try await session.api.processPurchaseOrder(pdf: data, filename: filename, mode: mode)
            for key in fields.keys {
                let value = parsed[key]
                if !value.isEmpty { fields[key] = value }
            }
            // כל הפריטים שפורסרו נכנסים, לא רק הראשון.
            if case .array(let parsedItems)? = parsed.fields["items"] {
                let imported: [ComposerItem] = parsedItems.compactMap { entry in
                    guard case .object(let raw) = entry else { return nil }
                    let record = DomainRecord(fields: raw)
                    guard !record["description"].isEmpty else { return nil }
                    var item = ComposerItem()
                    item.description = record["description"]
                    item.sku = record["sku"]
                    item.quantity = record["quantity"].isEmpty ? "1" : record["quantity"]
                    item.unitPrice = record["unit_price"]
                    let unit = record["unit"]
                    item.unit = ComposerMath.units.contains(unit) ? unit : ComposerMath.units[0]
                    return item
                }
                if !imported.isEmpty { items = imported }
            }
            step = .form
            Haptics.success()
        } catch {
            errorMessage = (error as? APIError)?.message ?? "הפרסור נכשל."
            step = .form
        }
    }

    /// בורר תנאי התשלום מעדכן גם את התווית וגם את מספר הימים, כמו הסלקט בדסקטופ.
    private var paymentTermsBinding: Binding<String> {
        Binding(
            get: { fields["payment_terms_days"] ?? "30" },
            set: { days in
                fields["payment_terms_days"] = days
                fields["payment_terms_label"] = ComposerMath.paymentTerms.first { $0.days == days }?.label ?? ""
            }
        )
    }

    private func create() async {
        // אותם שדות חובה שהדסקטופ אוכף לפני שליחה.
        let required: [(String, String)] = [
            ("po_number", "מספר הזמנה"),
            ("customer_name", "שם לקוח"),
            ("customer_id", "ח.פ / ע.מ"),
            ("delivery_address", "כתובת אספקה"),
        ]
        if let missing = required.first(where: { (fields[$0.0] ?? "").trimmingCharacters(in: .whitespaces).isEmpty }) {
            errorMessage = "\(missing.1) הוא שדה חובה."
            Haptics.error()
            return
        }
        let completeItems = items.filter(\.isComplete)
        guard !completeItems.isEmpty, subtotal > 0 else {
            errorMessage = "יש למלא לפחות פריט אחד עם תיאור, כמות ומחיר."
            Haptics.error()
            return
        }
        errorMessage = nil
        step = .working("יוצר את ההצעה ב\(mode == "sandbox" ? "סנדבוקס" : "פרודקשן")…")

        var data: [String: Any] = fields
        data["manual_entry"] = true
        data["manual_document_kind"] = "quote"
        data["footer_text"] = footerText
        let payloads = completeItems.map(\.payload)
        data["items"] = payloads
        data["ordered_items"] = payloads
        // שדות הפריט הראשון בנפרד — הדסקטופ שולח אותם לצד המערך.
        if let first = completeItems.first {
            data["item_description"] = first.description
            data["item_sku"] = first.sku
            data["item_unit"] = first.unit
            data["item_quantity"] = first.quantityValue
            data["item_unit_price"] = first.unitPriceValue
            data["item_line_total"] = first.lineTotal
        }
        data["subtotal"] = subtotal
        data["vat"] = ComposerMath.vat(subtotal)
        data["total"] = ComposerMath.total(subtotal)

        do {
            let result = try await session.api.finalizeQuote(mode: mode, data: data)
            await session.loadDomain(.quoteHistory, force: true)
            let quoteNumber = result.first(of: ["quote_document_number", "quote_number"])
            step = .done(
                quoteNumber: quoteNumber,
                driveURL: result["quote_drive_url"],
                message: quoteNumber.isEmpty ? "ההצעה נוצרה." : "הצעת מחיר \(quoteNumber) נוצרה."
            )
            session.showSuccess("הצעת המחיר נוצרה.")
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת ההצעה נכשלה."
            step = .form
            Haptics.error()
        }
    }
}
