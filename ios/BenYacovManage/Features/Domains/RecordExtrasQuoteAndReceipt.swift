import SwiftUI
import PhotosUI

// MARK: - פעולות הצעת מחיר (צפייה, שליחות, המרה, הצעה חתומה)

struct QuoteActionsCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var showEmailSheet = false
    @State private var showWhatsappSheet = false
    @State private var emailRecipients = ""
    @State private var whatsappPhone = ""
    @State private var whatsappMessage = ""
    @State private var isWorking = false
    @State private var convertData: [String: String]?
    @State private var showSignedImporter = false
    @State private var viewURL: URL?

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("פעולות על ההצעה", systemImage: "doc.text.fill")
                    .font(.byRowTitle)
                    .accessibilityIdentifier("quote-actions-card")

                actionRow("צפייה בהצעה", icon: "eye.fill", tint: BYTheme.Palette.blue, id: "quote-view") {
                    Task { await openQuote() }
                }
                actionRow("שליחה במייל ללקוח", icon: "envelope.fill", tint: BYTheme.Palette.teal, id: "quote-email") {
                    emailRecipients = record["customer_email"]
                    showEmailSheet = true
                }
                actionRow("שליחה בוואטסאפ", icon: "message.fill", tint: BYTheme.Palette.green, id: "quote-whatsapp") {
                    whatsappPhone = record.first(of: ["contact_phone", "customer_phone"])
                    whatsappMessage = "היי, מצורפת הצעת מחיר \(record["quote_number"]) מבן יעקב פתרונות טקסטיל."
                    showWhatsappSheet = true
                }
                actionRow("המרה להזמנת רכש", icon: "arrow.right.doc.on.clipboard", tint: BYTheme.Palette.indigo, id: "quote-convert") {
                    Task { await loadConversion() }
                }
                actionRow("העלאת הצעה חתומה", icon: "signature", tint: BYTheme.Palette.amber, id: "quote-upload-signed") {
                    showSignedImporter = true
                }
                if isWorking {
                    HStack { ProgressView(); Text("עובד…").font(.byCaption).foregroundStyle(BYTheme.textSecondary) }
                }
            }
        }
        .sheet(isPresented: $showEmailSheet) {
            SendMessageSheet(
                title: "שליחת הצעה במייל",
                fieldLabel: "נמענים",
                fieldValue: $emailRecipients,
                fieldKeyboard: .emailAddress,
                showsTestToggle: true,
                submitID: "quote-email-submit"
            ) { testSend in
                let api = session.api
                let historyID = record["history_id"]
                let recipients = emailRecipients
                return try await api.sendQuoteEmail(historyID: historyID, recipients: recipients, testSend: testSend)
            }
        }
        .sheet(isPresented: $showWhatsappSheet) {
            SendWhatsappSheet(
                title: "שליחת הצעה בוואטסאפ",
                phone: $whatsappPhone,
                message: $whatsappMessage,
                submitID: "quote-whatsapp-submit"
            ) {
                let api = session.api
                let phone = whatsappPhone
                let message = whatsappMessage
                let file = record.first(of: ["quote_local_file", "quote_file"])
                try await api.sendQuoteWhatsapp(phone: phone, message: message, quoteFile: file)
                return "ההצעה נשלחה בוואטסאפ."
            }
        }
        .sheet(item: Binding(
            get: { convertData.map { ConvertPayload(fields: $0) } },
            set: { convertData = $0?.fields }
        )) { payload in
            OrderComposerView(initialFields: payload.fields)
        }
        .sheet(isPresented: Binding(get: { viewURL != nil }, set: { if !$0 { viewURL = nil } })) {
            if let viewURL {
                SafariLinkView(url: viewURL)
            }
        }
        .fileImporter(isPresented: $showSignedImporter, allowedContentTypes: [.pdf, .image]) { result in
            if case .success(let url) = result {
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                if let data = try? Data(contentsOf: url) {
                    let mime = url.pathExtension.lowercased() == "pdf" ? "application/pdf" : "image/jpeg"
                    Task { await uploadSigned(data: data, filename: url.lastPathComponent, mimeType: mime) }
                }
            }
        }
    }

    struct ConvertPayload: Identifiable {
        let fields: [String: String]
        var id: String { fields["quote_number"] ?? UUID().uuidString }
    }

    private func actionRow(_ title: String, icon: String, tint: Color, id: String, action: @escaping () -> Void) -> some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(tint)
                    .frame(width: 30, height: 30)
                    .background(tint.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                Text(title)
                    .font(.byBody.weight(.medium))
                    .foregroundStyle(BYTheme.textPrimary)
                Spacer()
                Image(systemName: "chevron.backward")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(BYTheme.textSecondary.opacity(0.5))
            }
            .padding(.vertical, 5)
        }
        .accessibilityIdentifier(id)
    }

    private func openQuote() async {
        isWorking = true
        defer { isWorking = false }
        do {
            let urlText = try await session.api.resolveQuoteURL(historyID: record["history_id"])
            if let url = URL(string: urlText), !urlText.isEmpty {
                viewURL = url
            } else {
                session.showError("לא נמצא קישור זמין להצעה.")
            }
        } catch {
            session.showError((error as? APIError)?.message ?? "פתיחת ההצעה נכשלה.")
        }
    }

    private func loadConversion() async {
        isWorking = true
        defer { isWorking = false }
        do {
            let source = try await session.api.quoteOrderData(historyID: record["history_id"])
            var initial: [String: String] = [:]
            for key in ["customer_name", "customer_id", "po_number", "po_date", "delivery_address",
                        "project", "contact_name", "contact_phone", "payment_terms_label"] {
                initial[key] = source[key].isEmpty ? record[key] : source[key]
            }
            convertData = initial
        } catch {
            session.showError((error as? APIError)?.message ?? "טעינת נתוני ההצעה נכשלה.")
        }
    }

    private func uploadSigned(data: Data, filename: String, mimeType: String) async {
        let api = session.api
        let historyID = record["history_id"]
        await session.perform("ההצעה החתומה הועלתה.", refreshing: [.quoteHistory]) {
            try await api.uploadSignedQuote(historyID: historyID, fileData: data, filename: filename, mimeType: mimeType)
        }
    }
}

// MARK: - הפקת קבלה משורת גבייה

struct ReceiptCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var showSheet = false
    @State private var amount = ""
    @State private var method = "bank_transfer"
    @State private var paymentDate = Date()
    @State private var notes = ""
    @State private var withholdingApplied = false
    @State private var checkDetails = APIClient.CheckDetails()
    @State private var paymentAppProvider = "bit"
    @State private var isSending = false

    /// קבלה רלוונטית רק לשורת גבייה פתוחה עם חשבונית מס.
    var isRelevant: Bool {
        !record.bool("paid")
            && record["payment_direction"] != "תשלום"
            && !record["tax_invoice_number"].isEmpty
    }

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("הפקת קבלה", systemImage: "banknote.fill")
                    .font(.byRowTitle)
                Text("סימון גבייה כשולמה דורש קבלה. הקבלה תופק ב-GreenInvoice לחשבונית \(record["tax_invoice_number"]).")
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.textSecondary)
                BYPrimaryButton(title: "הפקת קבלה", icon: "plus.rectangle.on.rectangle", tint: BYTheme.Palette.green) {
                    amount = record["amount"]
                        .replacingOccurrences(of: "₪", with: "")
                        .replacingOccurrences(of: ",", with: "")
                        .trimmingCharacters(in: .whitespaces)
                    showSheet = true
                }
                .accessibilityIdentifier("receipt-open")
            }
        }
        .sheet(isPresented: $showSheet) {
            NavigationStack {
                Form {
                    Section("פרטי התשלום") {
                        LabeledContent("חשבונית מס") {
                            Text(record["tax_invoice_number"]).bold()
                        }
                        LabeledContent("סכום") {
                            TextField("", text: $amount)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("receipt-amount")
                        }
                        Picker("אופן תשלום", selection: $method) {
                            ForEach(APIClient.receiptPaymentMethods, id: \.key) { option in
                                Text(option.label).tag(option.key)
                            }
                        }
                        .accessibilityIdentifier("receipt-method")
                        if method == "check" {
                            // GreenInvoice מחייב את כל פרטי הצ'ק.
                            LabeledContent("מס' צ'ק") {
                                TextField("", text: $checkDetails.checkNumber)
                                    .keyboardType(.numberPad)
                                    .multilineTextAlignment(.leading)
                                    .accessibilityIdentifier("receipt-check-number")
                            }
                            LabeledContent("בנק") {
                                TextField("", text: $checkDetails.bankNumber)
                                    .keyboardType(.numberPad)
                                    .multilineTextAlignment(.leading)
                                    .accessibilityIdentifier("receipt-check-bank")
                            }
                            LabeledContent("סניף") {
                                TextField("", text: $checkDetails.branchNumber)
                                    .keyboardType(.numberPad)
                                    .multilineTextAlignment(.leading)
                                    .accessibilityIdentifier("receipt-check-branch")
                            }
                            LabeledContent("מס' חשבון") {
                                TextField("", text: $checkDetails.accountNumber)
                                    .keyboardType(.numberPad)
                                    .multilineTextAlignment(.leading)
                                    .accessibilityIdentifier("receipt-check-account")
                            }
                        }
                        if method == "payment_app" {
                            Picker("אפליקציית תשלום", selection: $paymentAppProvider) {
                                Text("ביט").tag("bit")
                                Text("פייבוקס").tag("paybox")
                            }
                            .accessibilityIdentifier("receipt-app-provider")
                        }
                        DatePicker("תאריך תשלום", selection: $paymentDate, displayedComponents: .date)
                        LabeledContent("הערות") {
                            TextField("", text: $notes)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    Section("ניכוי מס במקור") {
                        Toggle("הלקוח ניכה במקור", isOn: $withholdingApplied)
                            .accessibilityIdentifier("receipt-withholding-toggle")
                        if withholdingApplied {
                            // הניכוי מחושב אוטומטית (3%) — מציגים לאימות לפני ההפקה.
                            let gross = Double(amount) ?? 0
                            let breakdown = APIClient.withholdingBreakdown(gross: gross)
                            LabeledContent("סכום מלא") {
                                Text(Formatters.currencyValue(gross, detailed: true))
                            }
                            LabeledContent("ניכוי במקור (3%)") {
                                Text(Formatters.currencyValue(breakdown.withheld, detailed: true))
                                    .foregroundStyle(BYTheme.Palette.red)
                                    .accessibilityIdentifier("receipt-withheld")
                            }
                            LabeledContent("סה\"כ ששולם — הקבלה תופק על סכום זה") {
                                Text(Formatters.currencyValue(breakdown.paid, detailed: true))
                                    .bold()
                                    .foregroundStyle(BYTheme.Palette.green)
                                    .accessibilityIdentifier("receipt-net")
                            }
                        }
                    }
                }
                .navigationTitle("הפקת קבלה")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("ביטול") { showSheet = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button {
                            Task { await create() }
                        } label: {
                            if isSending { ProgressView() } else { Text("הפקה").bold() }
                        }
                        .disabled(isSending)
                        .accessibilityIdentifier("receipt-submit")
                    }
                }
            }
            .environment(\.layoutDirection, .rightToLeft)
            .accessibilityIdentifier("receipt-sheet")
        }
    }

    private func create() async {
        guard let amountValue = Double(amount), amountValue > 0 else {
            session.showError("יש להזין סכום תקין לקבלה.")
            return
        }
        isSending = true
        defer { isSending = false }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        let api = session.api
        let invoiceNumber = record["tax_invoice_number"]
        let mode = record["source_mode"].uppercased() == "SB" ? "sandbox" : "prod"
        let dateText = formatter.string(from: paymentDate)
        let currentMethod = method
        let currentNotes = notes
        let applied = withholdingApplied
        let currentCheck = checkDetails
        let currentProvider = paymentAppProvider
        if currentMethod == "check", !currentCheck.isComplete {
            session.showError("בתשלום בצ'ק צריך למלא מספר צ'ק, בנק, סניף ומספר חשבון.")
            isSending = false
            return
        }
        do {
            let message = try await api.createReceipt(
                mode: mode, invoiceNumber: invoiceNumber, grossAmount: amountValue,
                paymentMethod: currentMethod, paymentDate: dateText, notes: currentNotes,
                withholdingApplied: applied,
                checkDetails: currentMethod == "check" ? currentCheck : nil,
                paymentAppProvider: currentProvider
            )
            session.showSuccess(message + " עכשיו אפשר לסמן את השורה כשולמה.")
            await session.loadDomain(.paymentsTransfer, force: true)
            showSheet = false
        } catch {
            session.showError((error as? APIError)?.message ?? "הפקת הקבלה נכשלה.")
        }
    }
}

// MARK: - גיליונות שליחה גנריים

/// גיליון שליחה עם שדה יעד אחד (מייל/טלפון) — משותף לכמה זרימות.
struct SendMessageSheet: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    let title: String
    let fieldLabel: String
    @Binding var fieldValue: String
    var fieldKeyboard: UIKeyboardType = .default
    /// מציג טוגל "מצב בדיקה" (שליחה אליך בלבד) — דלוק כברירת מחדל, כמו בשאר השליחות.
    var showsTestToggle = false
    let submitID: String
    let action: (_ testSend: Bool) async throws -> String

    @State private var isSending = false
    @State private var testSend = true

    var body: some View {
        NavigationStack {
            Form {
                LabeledContent(fieldLabel) {
                    TextField("", text: $fieldValue)
                        .keyboardType(fieldKeyboard)
                        .multilineTextAlignment(.leading)
                        .accessibilityIdentifier("\(submitID)-field")
                }
                if showsTestToggle {
                    Toggle(isOn: $testSend) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("מצב בדיקה")
                            Text("המייל יישלח אליך בלבד, לא ללקוח")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                        }
                    }
                    .tint(BYTheme.Palette.amber)
                    .accessibilityIdentifier("\(submitID)-test-toggle")
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("ביטול") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task {
                            isSending = true
                            defer { isSending = false }
                            do {
                                let message = try await action(testSend)
                                session.showSuccess(message)
                                dismiss()
                            } catch {
                                session.showError((error as? APIError)?.message ?? "השליחה נכשלה.")
                            }
                        }
                    } label: {
                        if isSending { ProgressView() } else { Text("שליחה").bold() }
                    }
                    .disabled(isSending)
                    .accessibilityIdentifier(submitID)
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
    }
}

/// גיליון וואטסאפ: טלפון + הודעה.
struct SendWhatsappSheet: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    let title: String
    @Binding var phone: String
    @Binding var message: String
    let submitID: String
    let action: () async throws -> String

    @State private var isSending = false

    var body: some View {
        NavigationStack {
            Form {
                LabeledContent("טלפון") {
                    TextField("", text: $phone)
                        .keyboardType(.phonePad)
                        .multilineTextAlignment(.leading)
                        .accessibilityIdentifier("\(submitID)-phone")
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("הודעה")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.textSecondary)
                    TextField("", text: $message, axis: .vertical)
                        .lineLimit(3...6)
                        .accessibilityIdentifier("\(submitID)-message")
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("ביטול") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task {
                            isSending = true
                            defer { isSending = false }
                            do {
                                let result = try await action()
                                session.showSuccess(result)
                                dismiss()
                            } catch {
                                session.showError((error as? APIError)?.message ?? "השליחה נכשלה.")
                            }
                        }
                    } label: {
                        if isSending { ProgressView() } else { Text("שליחה").bold() }
                    }
                    .disabled(isSending)
                    .accessibilityIdentifier(submitID)
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
    }
}

/// פתיחת קישור חיצוני (Drive) בתוך האפליקציה.
import SafariServices

struct SafariLinkView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        SFSafariViewController(url: url)
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}
