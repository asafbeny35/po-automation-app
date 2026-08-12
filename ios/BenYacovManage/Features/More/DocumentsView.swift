import SwiftUI

/// מסמכי העסק — מסמכי שיווק (עם תצוגה מקדימה) ומסמכי מנהלה (שליחה במייל).
struct DocumentsView: View {
    @Environment(SessionStore.self) private var session

    @State private var marketingDocs: LoadState<[APIClient.MarketingDoc]> = .idle
    @State private var previewDoc: APIClient.MarketingDoc?
    @State private var adminDocToSend: AdminDoc?
    @State private var adminDocToWhatsapp: AdminDoc?
    @State private var whatsappPhone = ""
    @State private var whatsappMessage = ""

    struct AdminDoc: Identifiable {
        let key: String
        let label: String
        var id: String { key }
    }

    /// מסמכי המנהלה המרכזיים (מפתחות מהשרת).
    private let adminDocs: [AdminDoc] = [
        AdminDoc(key: "business-dealer", label: "תעודת עוסק מורשה"),
        AdminDoc(key: "business-tax-books", label: "אישור ניהול ספרים"),
        AdminDoc(key: "business-account-confirmation", label: "אישור ניהול חשבון"),
        AdminDoc(key: "bank-discount-confirmation", label: "דיסקונט — אישור ניהול חשבון"),
        AdminDoc(key: "bank-mercantile-confirmation", label: "מרכנתיל — אישור ניהול חשבון"),
        AdminDoc(key: "business-id-copy", label: "צילום תעודת זהות"),
        AdminDoc(key: "business-void-check", label: "צ'ק מבוטל"),
        AdminDoc(key: "iso-hebrew-cert", label: "תעודת ISO בעברית"),
        AdminDoc(key: "iso-english-cert", label: "תעודת ISO באנגלית"),
        AdminDoc(key: "customer-onboarding-package", label: "חבילת קליטת לקוח"),
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // עוגן זיהוי לטסטים — לא על המיכל, כדי לא לדרוס מזהי ילדים.
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("documents-screen")
                marketingSection
                adminSection
            }
            .padding(16)
        }
        .background(BYTheme.screenBackground)
        .navigationTitle("מסמכים")
        .navigationBarTitleDisplayMode(.large)
        .task { await loadMarketing() }
        .refreshable { await loadMarketing(force: true) }
        .sheet(item: $previewDoc) { doc in
            DocumentPreviewView(title: doc.label, path: "marketing-doc-preview/\(doc.assetKey)")
        }
        .sheet(item: $adminDocToSend) { doc in
            AdminDocSendSheet(doc: doc)
        }
        .sheet(item: $adminDocToWhatsapp) { doc in
            SendWhatsappSheet(
                title: "וואטסאפ — \(doc.label)",
                phone: $whatsappPhone,
                message: $whatsappMessage,
                submitID: "admin-whatsapp-submit"
            ) {
                let api = session.api
                let assetKey = doc.key
                let phone = whatsappPhone
                let message = whatsappMessage
                return try await api.sendAdminDocWhatsapp(assetKey: assetKey, phone: phone, message: message)
            }
        }
    }

    // MARK: - מסמכי שיווק

    private var marketingSection: some View {
        VStack(spacing: 8) {
            SectionHeader(title: "מסמכי שיווק", subtitle: "תצוגה מקדימה ושיתוף ללקוחות")
            switch marketingDocs {
            case .idle, .loading:
                ShimmerList(rows: 2)
            case .failed(let message):
                ErrorStateView(message: message) {
                    Task { await loadMarketing(force: true) }
                }
            case .loaded(let docs):
                if docs.isEmpty {
                    EmptyStateView(icon: "doc.richtext", title: "אין מסמכי שיווק זמינים")
                } else {
                    ForEach(docs) { doc in
                        BYCard(padding: 12) {
                            HStack(spacing: 12) {
                                Image(systemName: "doc.richtext.fill")
                                    .font(.system(size: 18))
                                    .foregroundStyle(BYTheme.Palette.pink)
                                    .frame(width: 38, height: 38)
                                    .background(BYTheme.Palette.pink.opacity(0.1))
                                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(doc.label)
                                        .font(.byRowTitle)
                                        .foregroundStyle(BYTheme.textPrimary)
                                    if !doc.category.isEmpty {
                                        Text(doc.category)
                                            .font(.byCaption)
                                            .foregroundStyle(BYTheme.textSecondary)
                                    }
                                }
                                Spacer()
                                Button {
                                    Haptics.tap()
                                    previewDoc = doc
                                } label: {
                                    Image(systemName: "eye.fill")
                                        .font(.system(size: 15))
                                        .foregroundStyle(BYTheme.Palette.brand)
                                        .frame(width: 34, height: 34)
                                        .background(BYTheme.Palette.brand.opacity(0.1))
                                        .clipShape(Circle())
                                }
                                .accessibilityIdentifier("marketing-doc-preview")
                                if let url = URL(string: doc.shareURL), !doc.shareURL.isEmpty {
                                    ShareLink(item: url) {
                                        Image(systemName: "square.and.arrow.up")
                                            .font(.system(size: 15))
                                            .foregroundStyle(BYTheme.Palette.green)
                                            .frame(width: 34, height: 34)
                                            .background(BYTheme.Palette.green.opacity(0.1))
                                            .clipShape(Circle())
                                    }
                                    .accessibilityIdentifier("marketing-doc-share")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - מסמכי מנהלה

    private var adminSection: some View {
        VStack(spacing: 8) {
            SectionHeader(title: "מסמכי מנהלה", subtitle: "שליחה במייל ללקוחות וספקים")
            ForEach(adminDocs) { doc in
                BYCard(padding: 12) {
                    HStack(spacing: 12) {
                        Image(systemName: "doc.badge.gearshape.fill")
                            .font(.system(size: 18))
                            .foregroundStyle(BYTheme.Palette.indigo)
                            .frame(width: 38, height: 38)
                            .background(BYTheme.Palette.indigo.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        Text(doc.label)
                            .font(.byRowTitle)
                            .foregroundStyle(BYTheme.textPrimary)
                        Spacer()
                        Button {
                            Haptics.tap()
                            adminDocToSend = doc
                        } label: {
                            Label("שליחה", systemImage: "envelope.fill")
                                .font(.byCaption.weight(.bold))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(BYTheme.Palette.brand.opacity(0.1))
                                .foregroundStyle(BYTheme.Palette.brand)
                                .clipShape(Capsule())
                        }
                        .accessibilityIdentifier("admin-doc-send")
                        Button {
                            Haptics.tap()
                            whatsappPhone = ""
                            whatsappMessage = "שלום, מצורף \(doc.label) של בן יעקב פתרונות טקסטיל."
                            adminDocToWhatsapp = doc
                        } label: {
                            Image(systemName: "message.fill")
                                .font(.system(size: 15))
                                .foregroundStyle(BYTheme.Palette.green)
                                .frame(width: 34, height: 34)
                                .background(BYTheme.Palette.green.opacity(0.1))
                                .clipShape(Circle())
                        }
                        .accessibilityIdentifier("admin-doc-whatsapp")
                    }
                }
            }
        }
    }

    private func loadMarketing(force: Bool = false) async {
        if !force, case .loaded = marketingDocs { return }
        if !force { marketingDocs = .loading }
        do {
            marketingDocs = .loaded(try await session.api.marketingDocs())
        } catch {
            marketingDocs = .failed((error as? APIError)?.message ?? "לא הצלחתי לטעון את מסמכי השיווק.")
        }
    }
}

/// שליחת מסמך מנהלה במייל — עם מצב בדיקה (אליך בלבד).
private struct AdminDocSendSheet: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss
    let doc: DocumentsView.AdminDoc

    @State private var recipients = ""
    @State private var subject = ""
    @State private var bodyText = ""
    @State private var testSend = true
    @State private var isSending = false

    var body: some View {
        NavigationStack {
            Form {
                Section("פרטי שליחה") {
                    LabeledContent("נמענים") {
                        TextField("", text: $recipients)
                            .keyboardType(.emailAddress)
                            .multilineTextAlignment(.leading)
                            .accessibilityIdentifier("admin-send-recipients")
                    }
                    LabeledContent("נושא") {
                        TextField("", text: $subject)
                            .multilineTextAlignment(.leading)
                            .accessibilityIdentifier("admin-send-subject")
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text("תוכן")
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(BYTheme.textSecondary)
                        TextField("", text: $bodyText, axis: .vertical)
                            .lineLimit(3...6)
                            .accessibilityIdentifier("admin-send-body")
                    }
                }
                Section {
                    Toggle(isOn: $testSend) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("מצב בדיקה")
                            Text("יישלח אליך בלבד")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                        }
                    }
                    .tint(BYTheme.Palette.amber)
                    .accessibilityIdentifier("admin-send-test-toggle")
                }
            }
            .navigationTitle("שליחת \(doc.label)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("ביטול") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await send() }
                    } label: {
                        if isSending { ProgressView() } else { Text("שליחה").bold() }
                    }
                    .disabled(isSending)
                    .accessibilityIdentifier("admin-send-submit")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .onAppear {
            if subject.isEmpty {
                subject = doc.label + " — בן יעקב פתרונות טקסטיל"
                bodyText = "שלום,\nמצורף \(doc.label).\nבברכה, בן יעקב פתרונות טקסטיל."
            }
        }
        .accessibilityIdentifier("admin-send-sheet")
    }

    private func send() async {
        isSending = true
        defer { isSending = false }
        let api = session.api
        let assetKey = doc.key
        let currentRecipients = recipients
        let currentSubject = subject
        let currentBody = bodyText
        let currentTest = testSend
        do {
            let message = try await api.sendAdminDocEmail(
                assetKey: assetKey, recipients: currentRecipients,
                subject: currentSubject, body: currentBody, testSend: currentTest
            )
            session.showSuccess(message)
            dismiss()
        } catch {
            session.showError((error as? APIError)?.message ?? "השליחה נכשלה.")
        }
    }
}
