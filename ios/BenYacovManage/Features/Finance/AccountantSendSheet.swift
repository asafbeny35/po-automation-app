import SwiftUI

/// שליחת ריכוז חשבוניות ספקים לרו"ח — שיקוף הכלי בדסקטופ:
/// בחירת מועדי דיווח, סוגי קבצים, טוגל מע"מ ומצב בדיקה.
struct AccountantSendBar: View {
    @Environment(SessionStore.self) private var session
    @State private var showSheet = false

    var body: some View {
        Button {
            Haptics.tap()
            showSheet = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "envelope.arrow.triangle.branch")
                    .font(.system(size: 14, weight: .semibold))
                Text("ריכוז חשבוניות לרו\"ח")
                    .font(.byCaption.weight(.bold))
                Spacer()
                Image(systemName: "chevron.backward")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(BYTheme.textSecondary.opacity(0.5))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(BYTheme.Palette.indigo.opacity(0.1))
            .foregroundStyle(BYTheme.Palette.indigo)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .accessibilityIdentifier("accountant-send-open")
        .padding(.bottom, 6)
        .sheet(isPresented: $showSheet) {
            AccountantSendSheet()
        }
    }
}

struct AccountantSendSheet: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    @State private var selectedDueDates: Set<String> = []
    @State private var recipients = ""
    @State private var includePDF = true
    @State private var includeXLSX = false
    @State private var includeZip = false
    @State private var includeVatSummary = false
    @State private var testSend = true
    @State private var isSending = false

    /// מועדי הדיווח הקיימים בחשבוניות (כולל overrides) — ממוינים מהחדש לישן.
    private var availableDueDates: [String] {
        FinanceInvoices.availableDueDates(session.records(for: .financeInvoices))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("מועדי דיווח") {
                    if availableDueDates.isEmpty {
                        Text("אין מועדי דיווח בחשבוניות הטעונות.")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                    ForEach(availableDueDates, id: \.self) { date in
                        Button {
                            if selectedDueDates.contains(date) {
                                selectedDueDates.remove(date)
                            } else {
                                selectedDueDates.insert(date)
                            }
                            Haptics.tap()
                        } label: {
                            HStack {
                                Text(date).foregroundStyle(BYTheme.textPrimary)
                                Spacer()
                                if selectedDueDates.contains(date) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(BYTheme.Palette.indigo)
                                }
                            }
                        }
                        .accessibilityIdentifier("accountant-due-\(date.replacingOccurrences(of: "/", with: "-"))")
                    }
                }
                Section("קבצים מצורפים") {
                    Toggle("PDF מרוכז", isOn: $includePDF)
                        .accessibilityIdentifier("accountant-pdf-toggle")
                    Toggle("קובץ אקסל (XLSX)", isOn: $includeXLSX)
                        .accessibilityIdentifier("accountant-xlsx-toggle")
                    Toggle("ZIP עם קבצי המקור", isOn: $includeZip)
                        .accessibilityIdentifier("accountant-zip-toggle")
                    Toggle("כלול סיכום מע\"מ", isOn: $includeVatSummary)
                        .accessibilityIdentifier("accountant-vat-toggle")
                }
                Section("שליחה") {
                    LabeledContent("נמענים") {
                        TextField("", text: $recipients)
                            .keyboardType(.emailAddress)
                            .multilineTextAlignment(.leading)
                            .accessibilityIdentifier("accountant-recipients")
                    }
                    Toggle(isOn: $testSend) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("מצב בדיקה")
                            Text("המייל יישלח אליך בלבד, לא לרו\"ח")
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                        }
                    }
                    .tint(BYTheme.Palette.amber)
                    .accessibilityIdentifier("accountant-test-toggle")
                }
            }
            .navigationTitle("ריכוז חשבוניות לרו\"ח")
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
                    .disabled(isSending || selectedDueDates.isEmpty)
                    .accessibilityIdentifier("accountant-send-submit")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task { await session.loadDomain(.financeInvoices) }
        .accessibilityIdentifier("accountant-send-sheet")
    }

    private func send() async {
        isSending = true
        defer { isSending = false }
        let api = session.api
        let dates = Array(selectedDueDates)
        let currentRecipients = recipients
        let pdf = includePDF, xlsx = includeXLSX, zip = includeZip, vat = includeVatSummary
        let test = testSend
        do {
            let message = try await api.sendAccountantSummary(
                reportDueDates: dates, recipients: currentRecipients,
                includePDF: pdf, includeXLSX: xlsx, includeZip: zip,
                includeVatSummary: vat, testSend: test
            )
            session.showSuccess(message)
            dismiss()
        } catch {
            session.showError((error as? APIError)?.message ?? "שליחת הריכוז נכשלה.")
        }
    }
}
