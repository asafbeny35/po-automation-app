import SwiftUI

/// טופס גנרי ליצירה/עריכה של רשומה.
struct RecordFormView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    let kind: EditFormKind
    let domain: Domain
    /// רשומה קיימת לעריכה; `nil` = יצירה.
    var existing: DomainRecord?

    @State private var values: [String: String] = [:]
    @State private var isSaving = false
    @State private var validationError: String?

    private var isCreation: Bool { existing == nil }

    var body: some View {
        NavigationStack {
            Form {
                // שגיאת ולידציה בראש הטופס — שתמיד תיראה, גם ב-form sheet של אייפד
                // שבו התחתית מחוץ לחלון העצלני של ה-Form.
                if let validationError {
                    Section {
                        Label(validationError, systemImage: "exclamationmark.triangle.fill")
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(BYTheme.Palette.red)
                            .accessibilityIdentifier("form-error")
                    }
                }
                Section {
                    ForEach(kind.fields) { field in
                        if let options = field.options {
                            // לא LabeledContent — הוא ממזג את התפריט לאלמנט שורה אחד
                            // ואז ההקשה של XCUITest לא פותחת את התפריט.
                            HStack {
                                Text(field.label)
                                    .font(.byBody)
                                Spacer()
                                Menu {
                                    ForEach(options, id: \.value) { option in
                                        Button(option.label) { values[field.key] = option.value }
                                    }
                                } label: {
                                    let current = values[field.key] ?? ""
                                    HStack(spacing: 4) {
                                        Text(options.first { $0.value == current }?.label ?? "בחירה")
                                            .font(.byBody.weight(.medium))
                                        Image(systemName: "chevron.up.chevron.down")
                                            .font(.system(size: 10))
                                    }
                                }
                                .accessibilityIdentifier("form-\(field.key)")
                            }
                        } else if field.multiline {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(field.label)
                                    .font(.byCaption.weight(.medium))
                                    .foregroundStyle(BYTheme.textSecondary)
                                TextField("", text: binding(field.key), axis: .vertical)
                                    .lineLimit(3...6)
                                    .accessibilityIdentifier("form-\(field.key)")
                            }
                        } else {
                            LabeledContent(field.label) {
                                TextField("", text: binding(field.key))
                                    .keyboardType(field.keyboard)
                                    .multilineTextAlignment(.leading)
                                    .accessibilityIdentifier("form-\(field.key)")
                            }
                        }
                    }
                }
            }
            .navigationTitle(isCreation ? "יצירת \(kind.title)" : "עריכת \(kind.title)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("ביטול") { dismiss() }
                        .accessibilityIdentifier("form-cancel")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await save() }
                    } label: {
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("שמירה").bold()
                        }
                    }
                    .disabled(isSaving)
                    .accessibilityIdentifier("form-save")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .onAppear { populate() }
        .accessibilityIdentifier("record-form")
    }

    private func binding(_ key: String) -> Binding<String> {
        Binding(
            get: { values[key] ?? "" },
            set: { values[key] = $0 }
        )
    }

    private func populate() {
        guard values.isEmpty else { return }
        // ברירות מחדל לשדות בחירה ביצירה חדשה.
        for field in kind.fields {
            if let options = field.options, values[field.key, default: ""].isEmpty {
                values[field.key] = options.first?.value ?? ""
            }
        }
        if let existing {
            for field in kind.fields {
                values[field.key] = existing[field.key]
            }
        }
    }

    private func save() async {
        if let requiredKey = kind.requiredKey,
           (values[requiredKey] ?? "").trimmingCharacters(in: .whitespaces).isEmpty {
            validationError = "יש למלא את השדה הראשי בטופס."
            Haptics.error()
            return
        }
        validationError = nil
        isSaving = true
        defer { isSaving = false }

        let api = session.api
        let payloadValues = values
        let existingRecord = existing
        let succeeded: Bool
        switch kind {
        case .customer:
            var customer = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { customer[key] = value }
            let path = isCreation ? "customers-create" : "customers-update"
            succeeded = await session.perform(
                isCreation ? "הלקוח נוצר." : "הלקוח עודכן.",
                refreshing: [.customers, .inactiveCustomers]
            ) {
                try await api.postJSON(path, body: ["customer": customer])
            }

        case .reminder:
            var body: [String: Any] = payloadValues
            if let existingRecord {
                body["reminder_id"] = existingRecord["reminder_id"]
                body["customer"] = ["customer_key": existingRecord["customer_key"],
                                    "customer_id": existingRecord["customer_id"],
                                    "customer_name": payloadValues["customer_name"] ?? ""]
            } else {
                body["customer"] = ["customer_name": payloadValues["customer_name"] ?? ""]
            }
            succeeded = await session.perform("התזכורת נשמרה.", refreshing: [.marketingReminders]) {
                try await api.postJSON("marketing-save-reminder", body: body)
            }

        case .paymentRow:
            if let existingRecord {
                var row = existingRecord.jsonObject
                for (key, value) in payloadValues { row[key] = value }
                succeeded = await session.perform("השורה עודכנה.", refreshing: [.paymentsTransfer]) {
                    try await api.postJSON("payments-transfer-update-row", body: [
                        "sheet_title": existingRecord["_sheet_title"],
                        "row_number": Int(existingRecord["_sheet_row"]) ?? -1,
                        "row": row,
                        "expected_snapshot_hash": existingRecord["_snapshot_hash"],
                        "session_id": AppConfig.sessionID,
                    ])
                }
            } else {
                succeeded = await session.perform("השורה נוספה.", refreshing: [.paymentsTransfer]) {
                    try await api.postJSON("payments-transfer-row", body: ["row": payloadValues])
                }
            }

        case .hrEmployee:
            var row = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { row[key] = value }
            succeeded = await session.perform("פרטי העובד נשמרו.", refreshing: [.hrEmployees]) {
                try await api.postJSON("hr-employee-save", body: ["row": row])
            }

        case .hrHours:
            var row = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { row[key] = value }
            // השרת דורש employee_id — פותרים אותו לפי שם העובד מרשימת העובדים.
            if (row["employee_id"] as? String ?? "").isEmpty {
                await session.loadDomain(.hrEmployees)
                let name = (payloadValues["employee_name"] ?? "").trimmingCharacters(in: .whitespaces)
                if let employee = session.records(for: .hrEmployees).first(where: { $0["full_name"] == name }) {
                    row["employee_id"] = employee["employee_id"]
                } else {
                    validationError = "לא נמצא עובד בשם הזה — יש להזין שם עובד קיים במדויק."
                    Haptics.error()
                    return
                }
            }
            succeeded = await session.perform("דיווח השעות נשמר.", refreshing: [.hrHours]) {
                try await api.postJSON("hr-hours-save", body: ["row": row])
            }

        case .workingOrderNote:
            // השרת מצפה ל-multipart form (תומך גם בצירוף קובץ), לא ל-JSON.
            succeeded = await session.perform("ההערה נשמרה.", refreshing: [.workingOrders]) {
                try await api.postMultipart("working-orders-note-save", fields: [
                    "row_id": existingRecord?["row_id"] ?? "",
                    "note_text": payloadValues["order_note_text"] ?? "",
                ])
            }

        case .workManager:
            var row = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { row[key] = value }
            succeeded = await session.perform("מנהל העבודה נשמר.", refreshing: [.marketingWorkManagers]) {
                try await api.postJSON("marketing-work-managers-save", body: ["row": row])
            }

        case .constructionCompany:
            var row = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { row[key] = value }
            succeeded = await session.perform("חברת הבנייה נשמרה.", refreshing: [.marketingConstructionCompanies]) {
                try await api.postJSON("marketing-construction-companies-save", body: ["row": row])
            }

        case .withholding:
            var row = existingRecord?.jsonObject ?? [:]
            for (key, value) in payloadValues { row[key] = value }
            // השרת דורש גם מספר קבלה וגם מספר חשבונית.
            for (key, message) in [("invoice_number", "יש למלא מספר חשבונית."),
                                   ("receipt_number", "יש למלא מספר קבלה.")] {
                if (row[key] as? String ?? "").trimmingCharacters(in: .whitespaces).isEmpty {
                    validationError = message
                    Haptics.error()
                    return
                }
            }
            succeeded = await session.perform("שורת הניכוי נשמרה.", refreshing: [.financeCustomerWithholdings]) {
                try await api.postJSON("finance-customer-withholdings-save", body: ["row": row])
            }
        }

        if succeeded { dismiss() }
    }
}
