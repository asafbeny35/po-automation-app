import Foundation

/// פעולת שרת על רשומה — מוצגת במסך הפירוט.
struct RecordAction: Identifiable {
    enum Style { case normal, destructive, prominent }

    let id: String
    let title: String
    let icon: String
    let style: Style
    /// הודעת אישור לפני הרצה (לפעולות הרסניות).
    let confirmation: String?
    /// הודעת הצלחה לטוסט.
    let successMessage: String
    /// דומיינים לרענון אחרי הפעולה.
    let refreshing: [Domain]
    let run: @Sendable (APIClient, DomainRecord) async throws -> Void

    init(id: String, title: String, icon: String, style: Style = .normal,
         confirmation: String? = nil, successMessage: String, refreshing: [Domain],
         run: @escaping @Sendable (APIClient, DomainRecord) async throws -> Void) {
        self.id = id
        self.title = title
        self.icon = icon
        self.style = style
        self.confirmation = confirmation
        self.successMessage = successMessage
        self.refreshing = refreshing
        self.run = run
    }
}

/// קטלוג הפעולות לכל דומיין.
enum DomainActionCatalog {
    static func actions(for domain: Domain, record: DomainRecord) -> [RecordAction] {
        switch domain {
        case .paymentsTransfer:
            let isPaid = record.bool("paid")
            return [
                RecordAction(
                    id: "toggle-paid",
                    title: isPaid ? "סימון כלא שולם" : "סימון כשולם",
                    icon: isPaid ? "xmark.circle" : "checkmark.circle.fill",
                    style: .prominent,
                    successMessage: isPaid ? "סומן כלא שולם." : "סומן כשולם.",
                    refreshing: [.paymentsTransfer]
                ) { api, record in
                    try await api.postJSON("payments-transfer-paid", body: [
                        "sheet_title": record["_sheet_title"],
                        "row_number": Int(record["_sheet_row"]) ?? -1,
                        "paid": !isPaid,
                        // נעילה אופטימית: אם מישהו שינה את השורה במקביל — השרת יחזיר 409.
                        "expected_snapshot_hash": record["_snapshot_hash"],
                        "session_id": AppConfig.sessionID,
                    ])
                },
                RecordAction(
                    id: "delete-row",
                    title: "מחיקת שורה",
                    icon: "trash",
                    style: .destructive,
                    confirmation: "למחוק את השורה של \(record["customer_name"])?",
                    successMessage: "השורה נמחקה.",
                    refreshing: [.paymentsTransfer]
                ) { api, record in
                    try await api.postJSON("payments-transfer-delete-row", body: [
                        "sheet_title": record["_sheet_title"],
                        "row_number": Int(record["_sheet_row"]) ?? -1,
                        "row": record.jsonObject,
                        "expected_snapshot_hash": record["_snapshot_hash"],
                        "session_id": AppConfig.sessionID,
                    ])
                },
            ]

        case .marketingReminders:
            var actions: [RecordAction] = []
            if record["status"].lowercased() != "completed" {
                actions.append(RecordAction(
                    id: "complete-reminder",
                    title: "סימון כבוצעה",
                    icon: "checkmark.circle.fill",
                    style: .prominent,
                    successMessage: "התזכורת סומנה כבוצעה.",
                    refreshing: [.marketingReminders]
                ) { api, record in
                    try await api.postJSON("marketing-complete-reminder", body: [
                        "reminder_id": record["reminder_id"],
                    ])
                })
            }
            actions.append(RecordAction(
                id: "delete-reminder",
                title: "מחיקת התזכורת",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את התזכורת של \(record["customer_name"])?",
                successMessage: "התזכורת נמחקה.",
                refreshing: [.marketingReminders]
            ) { api, record in
                try await api.postJSON("marketing-reminder-delete", body: [
                    "reminder_id": record["reminder_id"],
                ])
            })
            return actions

        case .orderHistory:
            return [RecordAction(
                id: "delete-order",
                title: "מחיקת רשומה מההיסטוריה",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את ההזמנה של \(record["customer_name"])?",
                successMessage: "הרשומה נמחקה.",
                refreshing: [.orderHistory]
            ) { api, record in
                try await api.postJSON("order-history-delete", body: [
                    "history_id": record["history_id"],
                    "fulfillment_id": record["fulfillment_id"],
                    "po_number": record["po_number"],
                    "customer_name": record["customer_name"],
                    "mode": record["mode"],
                ])
            }]

        case .quoteHistory:
            return [RecordAction(
                id: "delete-quote",
                title: "מחיקת הצעה מההיסטוריה",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את ההצעה \(record["quote_number"])?",
                successMessage: "ההצעה נמחקה.",
                refreshing: [.quoteHistory]
            ) { api, record in
                try await api.postJSON("quote-history-delete", body: [
                    "history_id": record["history_id"],
                ])
            }]

        case .workingOrders:
            return [RecordAction(
                id: "delete-working-order",
                title: "הסרה מהזמנות בעבודה",
                icon: "trash",
                style: .destructive,
                confirmation: "להסיר את ההזמנה של \(record["customer_name"]) מהעבודה?",
                successMessage: "ההזמנה הוסרה.",
                refreshing: [.workingOrders]
            ) { api, record in
                try await api.postJSON("working-orders-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .financeInvoices:
            // סטטוס התשלום נגזר משורת ה"לתשלום"; החלפתו כאן משנה גם אותה.
            let isUnpaid = record["payment_state"] == "unpaid"
            return [RecordAction(
                id: "toggle-invoice-paid",
                title: isUnpaid ? "סימון החשבונית כשולמה" : "סימון החשבונית כטרם שולמה",
                icon: isUnpaid ? "checkmark.circle.fill" : "clock.badge.exclamationmark",
                style: .prominent,
                successMessage: isUnpaid ? "החשבונית סומנה כשולמה." : "החשבונית נוספה לטבלת לתשלום.",
                refreshing: [.financeInvoices, .paymentsTransfer]
            ) { api, record in
                try await api.postJSON("finance-invoice-set-paid", body: [
                    "row_id": record["row_id"],
                    "paid": isUnpaid,
                ])
            },
            RecordAction(
                id: "delete-invoice",
                title: "מחיקת חשבונית",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את החשבונית של \(record["supplier_name"])?",
                successMessage: "החשבונית נמחקה.",
                refreshing: [.financeInvoices]
            ) { api, record in
                try await api.postJSON("finance-invoices-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .installationCases:
            return [RecordAction(
                id: "delete-installation-case",
                title: "מחיקת תיק ההתקנה",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את תיק ההתקנה של \(record["customer_name"])? ביקורי ההתקנה שכבר תועדו יישמרו.",
                successMessage: "תיק ההתקנה נמחק.",
                refreshing: [.installationCases]
            ) { api, record in
                try await api.postJSON("installations-case-delete", body: [
                    "installation_id": record["installation_id"],
                ])
            }]

        case .deliveryConfirmations:
            var actions = [RecordAction(
                id: "mark-sent",
                title: "סימון כנשלח ללקוח",
                icon: "paperplane.fill",
                style: .prominent,
                successMessage: "סומן כנשלח.",
                refreshing: [.deliveryConfirmations]
            ) { api, record in
                try await api.postJSON("delivery-confirmations-mark-sent", body: [
                    "fulfillment_id": record["fulfillment_id"],
                    "po_number": record["po_number"],
                    "tax_invoice_number": record["tax_invoice_number"],
                    "source_mode": record["source_mode"],
                    "company": record["company"],
                ])
            }]
            if !record["coc_drive_file_id"].isEmpty {
                actions.append(RecordAction(
                    id: "send-coc",
                    title: "שליחת תעודת COC במייל",
                    icon: "checkmark.shield.fill",
                    confirmation: "לשלוח את תעודת ה-COC ל-\(record["target_email"])?",
                    successMessage: "תעודת ה-COC נשלחה.",
                    refreshing: [.deliveryConfirmations]
                ) { api, record in
                    try await api.postJSON("delivery-confirmations-send-coc", body: [
                        "fulfillment_id": record["fulfillment_id"],
                        "po_number": record["po_number"],
                        "tax_invoice_number": record["tax_invoice_number"],
                        "source_mode": record["source_mode"],
                        "mode": "prod",
                        "recipients": record["target_email"],
                    ])
                })
            }
            return actions

        case .hrEmployees:
            return [RecordAction(
                id: "delete-employee",
                title: "מחיקת עובד",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את \(record["full_name"]) כולל התיקייה שלו?",
                successMessage: "העובד נמחק.",
                refreshing: [.hrEmployees]
            ) { api, record in
                try await api.postJSON("hr-employee-delete", body: [
                    "employee_id": record["employee_id"],
                ])
            }]

        case .hrHours:
            return [RecordAction(
                id: "delete-hours",
                title: "מחיקת דיווח השעות",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את דיווח השעות של \(record["employee_name"]) לחודש \(record["month_key"])?",
                successMessage: "דיווח השעות נמחק.",
                refreshing: [.hrHours]
            ) { api, record in
                try await api.postJSON("hr-hours-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .hrPayroll:
            let salaryPaid = record.bool("salary_paid")
            return [
                RecordAction(
                    id: "toggle-salary-paid",
                    title: salaryPaid ? "סימון שכר כלא שולם" : "סימון שכר כשולם",
                    icon: salaryPaid ? "xmark.circle" : "checkmark.circle.fill",
                    style: .prominent,
                    successMessage: salaryPaid ? "השכר סומן כלא שולם." : "השכר סומן כשולם.",
                    refreshing: [.hrPayroll]
                ) { api, record in
                    var row = record.jsonObject
                    row["salary_paid"] = salaryPaid ? "FALSE" : "TRUE"
                    try await api.postJSON("hr-payroll-save", body: ["row": row])
                },
                RecordAction(
                    id: "payroll-whatsapp",
                    title: "שליחת התלוש בוואטסאפ לעובד",
                    icon: "message.fill",
                    style: .prominent,
                    confirmation: "לשלוח את תלוש \(record["month_key"]) ל\(record["employee_name"])?",
                    successMessage: "התלוש נשלח בוואטסאפ.",
                    refreshing: [.hrPayroll]
                ) { api, record in
                    // השרת מחייב טלפון — פותרים אותו מרשומת העובד, כמו בדסקטופ.
                    let employees = try await api.domainRows(.hrEmployees)
                    let employee = employees.first { $0["employee_id"] == record["employee_id"] }
                    let phone = employee?.first(of: ["phone", "mobile"]) ?? ""
                    guard !phone.isEmpty else {
                        throw APIError(message: "לעובד אין מספר טלפון שמור — יש להשלים בכרטיס העובד.", statusCode: 400)
                    }
                    try await api.postJSON("hr-payroll-send-whatsapp", body: [
                        "row_id": record["row_id"],
                        "phone": phone,
                    ])
                },
                RecordAction(
                    id: "delete-payroll",
                    title: "מחיקת רשומת שכר",
                    icon: "trash",
                    style: .destructive,
                    confirmation: "למחוק את רשומת השכר של \(record["employee_name"]) לחודש \(record["month_key"])?",
                    successMessage: "רשומת השכר נמחקה.",
                    refreshing: [.hrPayroll]
                ) { api, record in
                    try await api.postJSON("hr-payroll-delete", body: [
                        "row_id": record["row_id"],
                    ])
                },
            ]

        case .hrContributions:
            let contributionPaid = record.bool("paid")
            return [RecordAction(
                id: "toggle-contribution-paid",
                title: contributionPaid ? "סימון הפרשה כלא שולמה" : "סימון הפרשה כשולמה",
                icon: contributionPaid ? "xmark.circle" : "checkmark.circle.fill",
                style: .prominent,
                successMessage: contributionPaid ? "ההפרשה סומנה כלא שולמה." : "ההפרשה סומנה כשולמה.",
                refreshing: [.hrContributions]
            ) { api, record in
                var row = record.jsonObject
                row["paid"] = contributionPaid ? "FALSE" : "TRUE"
                try await api.postJSON("hr-contribution-save", body: ["row": row])
            }]

        case .hrDocuments:
            return [RecordAction(
                id: "delete-hr-document",
                title: "מחיקת המסמך",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את \(record.first(of: ["title", "file_name"]))?",
                successMessage: "המסמך נמחק.",
                refreshing: [.hrDocuments]
            ) { api, record in
                try await api.postJSON("hr-document-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .inventoryPurchaseOrders:
            return [RecordAction(
                id: "delete-supplier-po",
                title: "מחיקת הזמנת הרכש",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את הזמנת הרכש \(record["po_number"]) של \(record["supplier_name"])?",
                successMessage: "הזמנת הרכש נמחקה.",
                refreshing: [.inventoryPurchaseOrders]
            ) { api, record in
                try await api.postJSON("inventory-purchase-orders-delete", body: [
                    "history_id": record["history_id"],
                ])
            }]

        case .supplierDeliveryNotes:
            return [RecordAction(
                id: "delete-supplier-note",
                title: "מחיקת תעודת המשלוח",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את תעודת המשלוח \(record["delivery_note_number"]) של \(record["supplier_name"])?",
                successMessage: "תעודת המשלוח נמחקה.",
                refreshing: [.supplierDeliveryNotes]
            ) { api, record in
                try await api.postJSON("supplier-delivery-notes-delete-row", body: [
                    "record_id": record.first(of: ["record_id", "row_id"]),
                ])
            }]

        case .marketingWorkManagers:
            return [RecordAction(
                id: "delete-work-manager",
                title: "מחיקת מנהל העבודה",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את \(record["full_name"]) מרשימת מנהלי העבודה?",
                successMessage: "מנהל העבודה נמחק.",
                refreshing: [.marketingWorkManagers]
            ) { api, record in
                try await api.postJSON("marketing-work-managers-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .marketingConstructionCompanies:
            return [RecordAction(
                id: "delete-construction-company",
                title: "מחיקת חברת הבנייה",
                icon: "trash",
                style: .destructive,
                confirmation: "למחוק את \(record["company_name"]) מהרשימה?",
                successMessage: "חברת הבנייה נמחקה.",
                refreshing: [.marketingConstructionCompanies]
            ) { api, record in
                try await api.postJSON("marketing-construction-companies-delete", body: [
                    "row_id": record["row_id"],
                ])
            }]

        case .marketingPipeline:
            return [RecordAction(
                id: "delete-pipeline-entry",
                title: "הסרה מתהליך השיווק",
                icon: "trash",
                style: .destructive,
                confirmation: "להסיר את \(record["customer_name"]) מתהליך השיווק?",
                successMessage: "הוסר מתהליך השיווק.",
                refreshing: [.marketingPipeline]
            ) { api, record in
                try await api.postJSON("marketing-pipeline-delete", body: [
                    "customer_key": record["customer_key"],
                ])
            }]

        case .customers, .inactiveCustomers:
            let isActive = domain == .customers
            return [
                RecordAction(
                    id: "toggle-active",
                    title: isActive ? "העברה ללא פעילים" : "החזרה לפעילים",
                    icon: isActive ? "person.fill.xmark" : "person.fill.checkmark",
                    style: isActive ? .normal : .prominent,
                    confirmation: isActive ? "להעביר את \(record["customer_name"]) ללקוחות לא פעילים?" : nil,
                    successMessage: isActive ? "הלקוח הועבר ללא פעילים." : "הלקוח חזר לפעילים.",
                    refreshing: [.customers, .inactiveCustomers]
                ) { api, record in
                    try await api.postJSON("customers-set-active", body: [
                        "active": !isActive,
                        "rows": [record.jsonObject],
                    ])
                },
                RecordAction(
                    id: "delete-customer",
                    title: "מחיקת לקוח",
                    icon: "trash",
                    style: .destructive,
                    confirmation: "למחוק לצמיתות את \(record["customer_name"])?",
                    successMessage: "הלקוח נמחק.",
                    refreshing: [.customers, .inactiveCustomers]
                ) { api, record in
                    try await api.postJSON("customers-delete", body: [
                        "customer": record.jsonObject,
                    ])
                },
            ]

        default:
            return []
        }
    }
}
