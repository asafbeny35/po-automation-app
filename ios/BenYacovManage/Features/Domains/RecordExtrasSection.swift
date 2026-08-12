import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

/// מקטעים ייעודיים במסך הפירוט — מעבר לפעולות הגנריות.
struct RecordExtrasSection: View {
    let domain: Domain
    let record: DomainRecord

    var body: some View {
        switch domain {
        case .deliveryConfirmations:
            VStack(spacing: 14) {
                SignedDeliveryUploadCard(record: record)
                DeliverySendCard(record: record)
            }
        case .quoteHistory:
            QuoteActionsCard(record: record)
        case .paymentsTransfer:
            PaymentsReceiptSection(record: record)
        case .inventoryPurchaseOrders:
            SupplierPOSendCard(record: record)
        case .supplierDeliveryNotes:
            SupplierNoteSourceCard(record: record)
        case .workingOrders:
            WorkingOrderExtrasSection(record: record)
        case .installationCases:
            InstallationCaseCard(record: record)
        case .customers, .inactiveCustomers:
            CustomerDomainCard(record: record)
        case .financeInvoices:
            InvoiceFileCard(record: record)
        default:
            EmptyView()
        }
    }
}

// MARK: - העלאת תעודת משלוח חתומה

private struct SignedDeliveryUploadCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var showCamera = false
    @State private var showFileImporter = false
    @State private var photoSelection: PhotosPickerItem?
    @State private var isUploading = false
    @State private var confirmDelete = false

    private var hasSignedFile: Bool {
        !record.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty
    }

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 12) {
                Label("תעודת משלוח חתומה", systemImage: "signature")
                    .font(.byRowTitle)
                    .accessibilityIdentifier("signed-upload-card")

                if hasSignedFile {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.seal.fill")
                            .foregroundStyle(BYTheme.Palette.green)
                        Text(record["signed_delivery_name"].isEmpty ? "תעודה חתומה מצורפת" : record["signed_delivery_name"])
                            .font(.byCaption.weight(.semibold))
                            .foregroundStyle(BYTheme.textPrimary)
                            .lineLimit(1)
                            .accessibilityIdentifier("signed-file-name")
                        Spacer()
                        Button {
                            Haptics.tap()
                            confirmDelete = true
                        } label: {
                            Image(systemName: "trash")
                                .font(.system(size: 14))
                                .foregroundStyle(BYTheme.Palette.red)
                                .frame(width: 32, height: 32)
                                .background(BYTheme.Palette.red.opacity(0.1))
                                .clipShape(Circle())
                        }
                        .accessibilityIdentifier("signed-delete")
                    }
                    Text("אפשר להעלות קובץ חדש במקום הקיים:")
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                } else {
                    Text("צלם או העלה את תעודת המשלוח החתומה מהאתר.")
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                }

                if isUploading {
                    HStack(spacing: 8) {
                        ProgressView()
                        Text("מעלה את התעודה…")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                } else {
                    HStack(spacing: 10) {
                        if CameraPicker.isAvailable {
                            uploadButton("צילום", icon: "camera.fill", tint: BYTheme.Palette.brand, id: "signed-camera") {
                                showCamera = true
                            }
                        }
                        PhotosPicker(selection: $photoSelection, matching: .images) {
                            uploadButtonLabel("מהתמונות", icon: "photo.on.rectangle", tint: BYTheme.Palette.teal)
                        }
                        .accessibilityIdentifier("signed-photos")
                        uploadButton("קובץ", icon: "folder.fill", tint: BYTheme.Palette.indigo, id: "signed-file") {
                            showFileImporter = true
                        }
                    }
                    if AppConfig.isUITest {
                        BYPrimaryButton(title: "העלאת קובץ לדוגמה", icon: "wand.and.stars", tint: BYTheme.Palette.teal) {
                            uploadSample()
                        }
                        .accessibilityIdentifier("signed-sample-upload")
                    }
                }
            }
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraPicker { data in
                Task { await upload(data: data, filename: "signed-delivery.jpg", mimeType: "image/jpeg") }
            }
            .ignoresSafeArea()
        }
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf, .image]) { result in
            if case .success(let url) = result {
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                if let data = try? Data(contentsOf: url) {
                    let mime = url.pathExtension.lowercased() == "pdf" ? "application/pdf" : "image/jpeg"
                    Task { await upload(data: data, filename: url.lastPathComponent, mimeType: mime) }
                }
            }
        }
        .onChange(of: photoSelection) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self) {
                    await upload(data: data, filename: "signed-delivery.jpg", mimeType: "image/jpeg")
                }
                photoSelection = nil
            }
        }
        .confirmationDialog("למחוק את התעודה החתומה?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("מחיקת הקובץ", role: .destructive) {
                Task { await deleteUpload() }
            }
            .accessibilityIdentifier("signed-delete-confirm")
            Button("ביטול", role: .cancel) {}
        }
    }

    private func uploadButtonLabel(_ title: String, icon: String, tint: Color) -> some View {
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

    private func uploadButton(_ title: String, icon: String, tint: Color, id: String,
                              action: @escaping () -> Void) -> some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            uploadButtonLabel(title, icon: icon, tint: tint)
        }
        .accessibilityIdentifier(id)
    }

    private func uploadSample() {
        if let url = Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf", subdirectory: "Fixtures")
            ?? Bundle.main.url(forResource: "sample_invoice", withExtension: "pdf"),
           let data = try? Data(contentsOf: url) {
            Task { await upload(data: data, filename: "sample-signed.pdf", mimeType: "application/pdf") }
        }
    }

    private func upload(data: Data, filename: String, mimeType: String) async {
        isUploading = true
        defer { isUploading = false }
        let api = session.api
        let currentRecord = record
        await session.perform("התעודה החתומה הועלתה ושויכה.", refreshing: [.deliveryConfirmations]) {
            try await api.uploadSignedDelivery(
                record: currentRecord, fileData: data, filename: filename, mimeType: mimeType
            )
        }
    }

    private func deleteUpload() async {
        let api = session.api
        let currentRecord = record
        await session.perform("התעודה החתומה נמחקה.", refreshing: [.deliveryConfirmations]) {
            try await api.deleteSignedDelivery(record: currentRecord)
        }
    }
}

// MARK: - שליחת אישור מסירה

private struct DeliverySendCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var showSheet = false
    @State private var subject = ""
    @State private var message = ""
    @State private var recipients = ""
    @State private var testSend = true
    @State private var sendNewBankDetails = false
    @State private var isSending = false
    /// הנוסח כפי שמולא מראש — אם המשתמש לא נגע, שולחים ריק והשרת ממלא
    /// את הנוסח הקנוני שלו (כך שינויי נוסח עתידיים לא דורשים עדכון אפליקציה).
    @State private var prefilledSubject = ""
    @State private var prefilledMessage = ""

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("שליחת אישור מסירה ללקוח", systemImage: "paperplane.circle.fill")
                    .font(.byRowTitle)
                Text("שולח במייל את החשבונית ותעודת המשלוח החתומה ל\(record["company"]).")
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.textSecondary)
                // השרת דורש חשבונית מס + תעודה חתומה לפני שליחה.
                if record["tax_invoice_number"].isEmpty || record.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty {
                    Label("חסרה חשבונית מס או תעודה חתומה — השליחה תידחה על ידי השרת.",
                          systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.semibold))
                        .foregroundStyle(BYTheme.Palette.amber)
                        .accessibilityIdentifier("delivery-send-warning")
                }
                BYPrimaryButton(title: "שליחה במייל", icon: "envelope.fill", tint: BYTheme.Palette.teal) {
                    // הנוסח הקנוני של הדסקטופ (זהה ל-_build_delivery_confirmation_mail_subject/body בשרת).
                    let invoiceNumber = record["tax_invoice_number"].isEmpty ? "—" : record["tax_invoice_number"]
                    let poNumber = record["po_number"].isEmpty ? "—" : record["po_number"]
                    let orderDate = record["order_date"].isEmpty ? "—" : record["order_date"]
                    let greeting = record["company"].isEmpty ? "שלום" : record["company"]
                    subject = "מצורפת חשבונית \(invoiceNumber) מבן יעקב פתרונות טקסטיל"
                    message = """
                    שלום \(greeting),

                    מצורפת חשבונית \(invoiceNumber) מבן יעקב פתרונות טקסטיל.
                    כמו כן, מצורפת ת.משלוח חתומה.
                    בגין הזמנת רכש \(poNumber),
                    מיום ה-\(orderDate).

                    לקטלוג מוצרי החברה לחץ כאן.

                    בברכה,
                    בן יעקב פתרונות טקסטיל
                    0547720142
                    """
                    prefilledSubject = subject
                    prefilledMessage = message
                    recipients = record["target_email"]
                    showSheet = true
                }
                .accessibilityIdentifier("delivery-send-open")
            }
        }
        .sheet(isPresented: $showSheet) {
            NavigationStack {
                Form {
                    Section("פרטי שליחה") {
                        LabeledContent("נמענים") {
                            TextField("", text: $recipients)
                                .keyboardType(.emailAddress)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("delivery-send-recipients")
                        }
                        LabeledContent("נושא") {
                            TextField("", text: $subject)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("delivery-send-subject")
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text("תוכן ההודעה")
                                .font(.byCaption.weight(.medium))
                                .foregroundStyle(BYTheme.textSecondary)
                            TextField("", text: $message, axis: .vertical)
                                .lineLimit(3...8)
                                .accessibilityIdentifier("delivery-send-message")
                        }
                    }
                    Section {
                        Toggle(isOn: $sendNewBankDetails) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("צרף פרטי חשבון בנק חדשים")
                                Text("מוסיף למייל את הודעת עדכון פרטי הבנק")
                                    .font(.byCaption)
                                    .foregroundStyle(BYTheme.textSecondary)
                            }
                        }
                        .tint(BYTheme.Palette.teal)
                        .accessibilityIdentifier("delivery-send-bank-toggle")
                        Toggle(isOn: $testSend) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("מצב בדיקה")
                                    .font(.byBody)
                                Text("המייל יישלח אליך בלבד, לא ללקוח")
                                    .font(.byCaption)
                                    .foregroundStyle(BYTheme.textSecondary)
                            }
                        }
                        .tint(BYTheme.Palette.amber)
                        .accessibilityIdentifier("delivery-send-test-toggle")
                    }
                }
                .navigationTitle("שליחת אישור מסירה")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("ביטול") { showSheet = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button {
                            Task { await send() }
                        } label: {
                            if isSending { ProgressView() } else { Text("שליחה").bold() }
                        }
                        .disabled(isSending)
                        .accessibilityIdentifier("delivery-send-submit")
                    }
                }
            }
            .environment(\.layoutDirection, .rightToLeft)
            .accessibilityIdentifier("delivery-send-sheet")
        }
    }

    private func send() async {
        isSending = true
        defer { isSending = false }
        let api = session.api
        let currentRecord = record
        // נוסח שלא נערך נשלח ריק — השרת ימלא את הנוסח הקנוני העדכני שלו.
        let currentSubject = subject == prefilledSubject ? "" : subject
        let currentMessage = message == prefilledMessage ? "" : message
        let currentRecipients = recipients
        let currentTest = testSend
        let currentBankDetails = sendNewBankDetails
        do {
            let resultMessage = try await api.sendDeliveryConfirmation(
                record: currentRecord, subject: currentSubject, message: currentMessage,
                recipients: currentRecipients, testSend: currentTest,
                sendNewBankDetails: currentBankDetails
            )
            session.showSuccess(resultMessage)
            showSheet = false
        } catch {
            session.showError((error as? APIError)?.message ?? "השליחה נכשלה.")
        }
    }
}

// MARK: - ניהול תיק התקנה

private struct InstallationCaseCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var status: String = ""
    @State private var delayReason: String = ""
    @State private var notes: String = ""
    @State private var isSaving = false
    @State private var showVisitSheet = false

    private var visits: [DomainRecord] {
        session.records(for: .installationVisits)
            .filter { $0["installation_id"] == record["installation_id"] }
    }

    /// תיק "ממתין" נבנה מהזמנה בעבודה ועוד לא קיים באמת בשרת — אי אפשר לעדכן אותו.
    private var isPendingCase: Bool {
        record["installation_id"].hasPrefix("pending")
    }

    var body: some View {
        if isPendingCase {
            BYCard {
                Label("התיק ייפתח לניהול אוטומטית אחרי הפקת תעודת המשלוח להזמנה.",
                      systemImage: "hourglass")
                    .font(.byBody)
                    .foregroundStyle(BYTheme.textSecondary)
            }
            .accessibilityIdentifier("installation-pending-info")
        } else {
            managementBody
        }
    }

    private var managementBody: some View {
        VStack(spacing: 14) {
            statusCard
            visitsCard
        }
        .onAppear {
            if status.isEmpty {
                status = record["status"].isEmpty ? APIClient.installationStatusOptions[0] : record["status"]
                delayReason = record["delay_reason"]
                notes = record["notes"]
            }
        }
        .task { await session.loadDomain(.installationVisits) }
        .sheet(isPresented: $showVisitSheet) {
            InstallationVisitFormView(caseRecord: record)
        }
    }

    private var statusCard: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 12) {
                Label("ניהול תיק התקנה", systemImage: "wrench.and.screwdriver.fill")
                    .font(.byRowTitle)
                HStack {
                    Text("סטטוס")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.textSecondary)
                        .frame(width: 90, alignment: .leading)
                    Menu {
                        ForEach(APIClient.installationStatusOptions, id: \.self) { option in
                            Button(option) {
                                status = option
                                Haptics.tap()
                            }
                        }
                    } label: {
                        HStack {
                            Text(status.isEmpty ? "בחירה" : status)
                                .font(.byBody.weight(.semibold))
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.system(size: 11))
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(BYTheme.insetBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    }
                    .accessibilityIdentifier("installation-status-menu")
                    Spacer()
                }
                HStack {
                    Text("סיבת עיכוב")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.textSecondary)
                        .frame(width: 90, alignment: .leading)
                    Menu {
                        Button("ללא") { delayReason = "" }
                        ForEach(APIClient.installationDelayReasons, id: \.self) { option in
                            Button(option) { delayReason = option }
                        }
                    } label: {
                        HStack {
                            Text(delayReason.isEmpty ? "ללא" : delayReason)
                                .font(.byBody)
                                .lineLimit(1)
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.system(size: 11))
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(BYTheme.insetBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    }
                    .accessibilityIdentifier("installation-delay-menu")
                    Spacer()
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("הערות")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.textSecondary)
                    TextField("", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                        .padding(10)
                        .background(BYTheme.insetBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .accessibilityIdentifier("installation-notes")
                }
                BYPrimaryButton(title: "שמירת סטטוס", icon: "checkmark.circle.fill", isLoading: isSaving) {
                    Task { await save() }
                }
                .accessibilityIdentifier("installation-save-status")
            }
        }
    }

    private var visitsCard: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Label("ביקורי התקנה (\(visits.count))", systemImage: "figure.walk.arrival")
                        .font(.byRowTitle)
                    Spacer()
                    Button {
                        Haptics.tap()
                        showVisitSheet = true
                    } label: {
                        Label("ביקור חדש", systemImage: "plus.circle.fill")
                            .font(.byCaption.weight(.bold))
                    }
                    .accessibilityIdentifier("installation-add-visit")
                }
                if visits.isEmpty {
                    Text("עוד לא תועדו ביקורים בתיק הזה.")
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                } else {
                    ForEach(visits) { visit in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(Formatters.dateText(visit["visit_date"]))
                                    .font(.byBody.weight(.semibold))
                                if !visit["summary_text"].isEmpty || !visit["notes"].isEmpty {
                                    Text(visit.first(of: ["summary_text", "notes"]))
                                        .font(.byCaption)
                                        .foregroundStyle(BYTheme.textSecondary)
                                        .lineLimit(2)
                                }
                            }
                            Spacer()
                            if !visit["installed_total_quantity"].isEmpty {
                                Text("הותקנו: \(visit["installed_total_quantity"])")
                                    .font(.byCaption.weight(.semibold))
                                    .foregroundStyle(BYTheme.Palette.green)
                            }
                        }
                        .padding(.vertical, 5)
                        .accessibilityIdentifier("installation-visit-row")
                    }
                }
            }
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        let api = session.api
        let installationID = record["installation_id"]
        let nextVisit = record["next_visit_date"]
        let currentStatus = status
        let currentReason = delayReason
        let currentNotes = notes
        await session.perform("תיק ההתקנה עודכן.", refreshing: [.installationCases]) {
            try await api.updateInstallationCase(
                installationID: installationID, status: currentStatus,
                delayReason: currentReason, nextVisitDate: nextVisit, notes: currentNotes
            )
        }
    }
}

/// טופס ביקור התקנה — כמויות לפי פריטי התיק.
struct InstallationVisitFormView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    let caseRecord: DomainRecord

    struct VisitItem: Identifiable {
        let key: String
        let description: String
        let remaining: Int
        var quantity: Int = 0
        var id: String { key }
    }

    @State private var visitDate: Date = .now
    @State private var notes = ""
    @State private var items: [VisitItem] = []
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                Section("פרטי ביקור") {
                    DatePicker("תאריך", selection: $visitDate, displayedComponents: .date)
                        .accessibilityIdentifier("visit-date")
                    VStack(alignment: .leading, spacing: 6) {
                        Text("הערות")
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(BYTheme.textSecondary)
                        TextField("", text: $notes, axis: .vertical)
                            .lineLimit(2...4)
                            .accessibilityIdentifier("visit-notes")
                    }
                }
                Section("מה הותקן בביקור") {
                    if items.isEmpty {
                        Text("אין פריטים פתוחים בתיק.")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                    ForEach($items) { $item in
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.description)
                                    .font(.byCaption)
                                    .lineLimit(2)
                                Text("הותקנו \(item.quantity) מתוך \(item.remaining) שנותרו")
                                    .font(.byCaption.weight(.semibold))
                                    .foregroundStyle(item.quantity > 0 ? BYTheme.Palette.green : BYTheme.textSecondary)
                            }
                            Spacer()
                            Button {
                                if item.quantity > 0 { item.quantity -= 1; Haptics.tap() }
                            } label: {
                                Image(systemName: "minus.circle.fill")
                                    .font(.system(size: 24))
                                    .foregroundStyle(item.quantity > 0 ? BYTheme.Palette.red : BYTheme.separator)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("visit-item-minus")
                            Text("\(item.quantity)")
                                .font(.byNumber(17))
                                .frame(minWidth: 26)
                            Button {
                                if item.quantity < max(item.remaining, 0) { item.quantity += 1; Haptics.tap() }
                            } label: {
                                Image(systemName: "plus.circle.fill")
                                    .font(.system(size: 24))
                                    .foregroundStyle(item.quantity < item.remaining ? BYTheme.Palette.green : BYTheme.separator)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("visit-item-plus")
                        }
                    }
                }
            }
            .navigationTitle("ביקור התקנה חדש")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("ביטול") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await save() }
                    } label: {
                        if isSaving { ProgressView() } else { Text("שמירה").bold() }
                    }
                    .disabled(isSaving)
                    .accessibilityIdentifier("visit-save")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .onAppear(perform: loadItems)
        .accessibilityIdentifier("visit-form")
    }

    private func loadItems() {
        guard items.isEmpty else { return }
        // הפריטים שנותרו להתקנה שמורים כ-JSON בתוך שורת התיק.
        let raw = caseRecord.first(of: ["remaining_items_json", "install_items_json"])
        guard let data = raw.data(using: .utf8),
              let list = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return
        }
        items = list.compactMap { item in
            let key = (item["item_key"] as? String) ?? ""
            guard !key.isEmpty else { return nil }
            let description = (item["description"] as? String) ?? key
            let remaining = (item["remaining_quantity"] as? NSNumber)?.intValue
                ?? (item["quantity"] as? NSNumber)?.intValue
                ?? (item["ordered_quantity"] as? NSNumber)?.intValue
                ?? 0
            return VisitItem(key: key, description: description, remaining: remaining)
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        let api = session.api
        let installationID = caseRecord["installation_id"]
        let dateText = formatter.string(from: visitDate)
        let installedItems: [[String: Any]] = items
            .filter { $0.quantity > 0 }
            .map { ["item_key": $0.key, "quantity": $0.quantity] }
        let currentNotes = notes
        let succeeded = await session.perform(
            "הביקור נשמר.", refreshing: [.installationCases, .installationVisits]
        ) {
            try await api.saveInstallationVisit(
                installationID: installationID, visitDate: dateText,
                installedItems: installedItems, notes: currentNotes
            )
        }
        if succeeded { dismiss() }
    }
}

// MARK: - שיוך לקוח לתחום

private struct CustomerDomainCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var isAssigning = false

    private var currentDomainLabel: String {
        APIClient.customerDomains.first { $0.key == record["customer_domain"] }?.label ?? "ללא תחום"
    }

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("תחום הלקוח", systemImage: "square.grid.2x2.fill")
                    .font(.byRowTitle)
                HStack {
                    Text(currentDomainLabel)
                        .font(.byBody.weight(.semibold))
                        .foregroundStyle(record["customer_domain"].isEmpty ? BYTheme.textSecondary : BYTheme.Palette.brand)
                        .accessibilityIdentifier("customer-domain-current")
                    Spacer()
                    Menu {
                        ForEach(APIClient.customerDomains, id: \.key) { option in
                            Button(option.label) {
                                Task { await assign(option.key) }
                            }
                        }
                    } label: {
                        HStack(spacing: 5) {
                            if isAssigning {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.triangle.2.circlepath")
                            }
                            Text("שיוך לתחום")
                        }
                        .font(.byCaption.weight(.bold))
                        .padding(.horizontal, 13)
                        .padding(.vertical, 8)
                        .background(BYTheme.Palette.brand.opacity(0.1))
                        .foregroundStyle(BYTheme.Palette.brand)
                        .clipShape(Capsule())
                    }
                    .disabled(isAssigning)
                    .accessibilityIdentifier("customer-domain-menu")
                }
            }
        }
    }

    private func assign(_ domainKey: String) async {
        isAssigning = true
        defer { isAssigning = false }
        let api = session.api
        let currentRecord = record
        await session.perform("הלקוח שויך לתחום.", refreshing: [.customers, .inactiveCustomers]) {
            try await api.assignCustomerDomain(record: currentRecord, domainKey: domainKey)
        }
    }
}

// MARK: - קובץ חשבונית

private struct InvoiceFileCard: View {
    let record: DomainRecord
    @State private var showPreview = false

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("קובץ החשבונית", systemImage: "doc.text.magnifyingglass")
                    .font(.byRowTitle)
                BYPrimaryButton(title: "צפייה בקובץ", icon: "eye.fill", tint: BYTheme.Palette.green) {
                    showPreview = true
                }
                .accessibilityIdentifier("invoice-view-file")
            }
        }
        .sheet(isPresented: $showPreview) {
            DocumentPreviewView(
                title: record["supplier_name"].isEmpty ? "חשבונית" : record["supplier_name"],
                path: "finance-invoices-file/\(record["row_id"])"
            )
        }
    }
}
