import SwiftUI

/// קומפוזר הזמנת רכש לספק: בחירת ספק מאנשי הקשר במלאי, פריטים, יצירה בסנדבוקס/פרודקשן.
struct SupplierPOComposerView: View {
    @Environment(SessionStore.self) private var session
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
                    doneView(doneMessage)
                } else {
                    formView
                }
            }
            .background(BYTheme.screenBackground)
            .navigationTitle("הזמנת רכש לספק")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("supplier-composer-close")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task {
            await session.loadDomain(.inventoryContacts)
            contacts = session.records(for: .inventoryContacts)
        }
        .scrollDismissesKeyboard(.immediately)
        .accessibilityIdentifier("supplier-composer")
    }

    private var formView: some View {
        ScrollView {
            VStack(spacing: 14) {
                BYCard {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Label("הספק", systemImage: "shippingbox.fill")
                                .font(.byRowTitle)
                            Spacer()
                            if !contacts.isEmpty {
                                Menu {
                                    ForEach(contacts.prefix(15)) { contact in
                                        Button(contact.first(of: ["company", "supplier", "supplier_name", "name"])) {
                                            supplierName = contact.first(of: ["company", "supplier", "supplier_name", "name"])
                                            supplierEmail = contact.first(of: ["email", "supplier_email"])
                                            supplierPhone = contact.first(of: ["direct_phone", "phone", "company_phone", "supplier_phone"])
                                            Haptics.tap()
                                        }
                                    }
                                } label: {
                                    Label("מאנשי הקשר", systemImage: "person.crop.circle.badge.checkmark")
                                        .font(.byCaption.weight(.bold))
                                }
                                .accessibilityIdentifier("supplier-picker")
                            }
                        }
                        row("שם הספק", text: $supplierName, id: "supplier-field-name")
                        row("ח.פ", text: $supplierID, id: "supplier-field-id", keyboard: .numberPad)
                        row("אימייל", text: $supplierEmail, id: "supplier-field-email", keyboard: .emailAddress)
                        row("טלפון", text: $supplierPhone, id: "supplier-field-phone", keyboard: .phonePad)
                    }
                }
                BYCard {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Label("פריטים", systemImage: "list.bullet.rectangle")
                                .font(.byRowTitle)
                            Spacer()
                            Button {
                                Haptics.tap()
                                items.append(LineItem())
                            } label: {
                                Image(systemName: "plus.circle.fill")
                                    .font(.system(size: 20))
                                    .foregroundStyle(BYTheme.Palette.brand)
                            }
                            .accessibilityIdentifier("supplier-add-item")
                        }
                        ForEach($items) { $item in
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    TextField("תיאור הפריט", text: $item.description)
                                        .accessibilityIdentifier("supplier-item-description")
                                    if items.count > 1 {
                                        Button {
                                            items.removeAll { $0.id == item.id }
                                        } label: {
                                            Image(systemName: "minus.circle")
                                                .foregroundStyle(BYTheme.Palette.red)
                                        }
                                    }
                                }
                                HStack(spacing: 12) {
                                    LabeledContent("כמות") {
                                        TextField("", text: $item.quantity)
                                            .keyboardType(.decimalPad)
                                            .multilineTextAlignment(.leading)
                                            .accessibilityIdentifier("supplier-item-quantity")
                                    }
                                    LabeledContent("מחיר יח'") {
                                        TextField("", text: $item.unitPrice)
                                            .keyboardType(.decimalPad)
                                            .multilineTextAlignment(.leading)
                                            .accessibilityIdentifier("supplier-item-price")
                                    }
                                }
                                Divider()
                            }
                        }
                        HStack {
                            Text("סה\"כ לפני מע\"מ")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                            Spacer()
                            Text(Formatters.currencyValue(subtotal, detailed: true))
                                .font(.byNumber(20))
                                .foregroundStyle(BYTheme.Palette.teal)
                                .accessibilityIdentifier("supplier-subtotal")
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text("הערות")
                                .font(.byCaption.weight(.medium))
                                .foregroundStyle(BYTheme.textSecondary)
                            TextField("", text: $remarks, axis: .vertical)
                                .lineLimit(2...4)
                                .accessibilityIdentifier("supplier-remarks")
                        }
                    }
                }
                BYCard {
                    Picker("מצב", selection: $mode) {
                        Text("סנדבוקס (בדיקה)").tag("sandbox")
                        Text("פרודקשן").tag("prod")
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("supplier-mode")
                }
                BYPrimaryButton(
                    title: mode == "sandbox" ? "יצירת הזמנה בסנדבוקס" : "יצירת הזמנה בפרודקשן",
                    icon: "shippingbox.fill",
                    isLoading: isCreating,
                    tint: mode == "sandbox" ? BYTheme.Palette.teal : BYTheme.Palette.brand
                ) {
                    Task { await create() }
                }
                .accessibilityIdentifier("supplier-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("supplier-error")
                }
            }
            .padding(16)
        }
    }

    private func doneView(_ message: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(BYTheme.Palette.green)
                .accessibilityIdentifier("supplier-done")
            Text(message)
                .font(.byTitle)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .accessibilityIdentifier("supplier-done-message")
            Text("שליחה לספק במייל או בוואטסאפ — מתוך ההזמנה בטאב הזמנות רכש במלאי.")
                .font(.byCaption)
                .foregroundStyle(BYTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 30)
            BYPrimaryButton(title: "סגירה", icon: "checkmark") { dismiss() }
                .padding(.horizontal, 40)
                .accessibilityIdentifier("supplier-done-close")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func row(_ label: String, text: Binding<String>, id: String,
                     keyboard: UIKeyboardType = .default) -> some View {
        LabeledContent(label) {
            TextField("", text: text)
                .keyboardType(keyboard)
                .multilineTextAlignment(.leading)
                .accessibilityIdentifier(id)
        }
    }

    private func create() async {
        guard !supplierName.trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "יש למלא שם ספק."
            Haptics.error()
            return
        }
        let validItems = items.filter { !$0.description.trimmingCharacters(in: .whitespaces).isEmpty && $0.lineTotal > 0 }
        guard !validItems.isEmpty else {
            errorMessage = "יש למלא לפחות פריט אחד עם כמות ומחיר."
            Haptics.error()
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
            Haptics.success()
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת ההזמנה נכשלה."
            Haptics.error()
        }
    }
}
