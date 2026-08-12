import Foundation

/// זרימות עסקיות מלאות — הזמנות רכש, חשבוניות, אישורי מסירה, התקנות, מסמכים ושיוך תחום.
extension APIClient {

    // MARK: - multipart

    struct MultipartFile {
        let field: String
        let filename: String
        let mimeType: String
        let data: Data
    }

    func postMultipart(_ path: String, query: [String: String] = [:],
                       fields: [String: String] = [:], files: [MultipartFile] = []) async throws -> Data {
        let boundary = "BYBoundary-\(UUID().uuidString)"
        var body = Data()
        func append(_ text: String) { body.append(text.data(using: .utf8)!) }
        for (name, value) in fields {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            append("\(value)\r\n")
        }
        for file in files {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"\(file.field)\"; filename=\"\(file.filename)\"\r\n")
            append("Content-Type: \(file.mimeType)\r\n\r\n")
            body.append(file.data)
            append("\r\n")
        }
        append("--\(boundary)--\r\n")

        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = body
        request.timeoutInterval = 180
        return try await performRaw(request)
    }

    /// הורדת קובץ (PDF/תמונה) עם עוגיית ההתחברות של האפליקציה.
    func fetchDocumentData(_ path: String) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        request.timeoutInterval = 120
        return try await performRaw(request)
    }

    // MARK: - הזמנת רכש: פרסור ויצירת מסמכים

    /// מעלה PDF של הזמנת רכש ומחזיר את השדות המפורסרים.
    func processPurchaseOrder(pdf: Data, filename: String, mode: String) async throws -> DomainRecord {
        let data = try await postMultipart(
            "process",
            fields: ["mode": mode],
            files: [MultipartFile(field: "file", filename: filename, mimeType: "application/pdf", data: pdf)]
        )
        let fields = try JSONDecoder().decode([String: JSONValue].self, from: data)
        return DomainRecord(fields: fields)
    }

    /// יוצר את מסמכי ההזמנה (תעודת משלוח, חשבונית, מדבקה) ושולח לפי המצב שנבחר.
    /// מחזיר את הודעת הסיכום מהשרת.
    /// `documentMode`: מלא / תעודת משלוח בלבד / חשבונית בלבד — נשלח ברמה העליונה
    /// לצד `data`, כפי שהשרת קורא אותו (ולא בתוך `data`).
    func finalizeOrder(mode: String, data orderData: [String: Any], skipWhatsapp: Bool,
                       documentMode: String = "full") async throws -> String {
        let data = try await postJSON("finalize", body: [
            "mode": mode,
            "data": orderData,
            "document_mode": documentMode,
            "skip_whatsapp": skipWhatsapp,
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let message = object["message"] as? String, !message.isEmpty { return message }
            if let status = object["status"] as? String, status == "ok" { return "המסמכים נוצרו בהצלחה." }
        }
        return "המסמכים נוצרו בהצלחה."
    }

    /// שומר הזמנת רכש ל"הזמנות בעבודה" בלי יצירת מסמכים — חנייה לטיפול בהמשך.
    func uploadWorkingOrder(pdf: Data, filename: String, requiresInstallation: Bool) async throws {
        try await postMultipart(
            "working-orders-upload",
            fields: ["requires_installation": requiresInstallation ? "true" : ""],
            files: [MultipartFile(field: "file", filename: filename, mimeType: "application/pdf", data: pdf)]
        )
    }

    // MARK: - חשבוניות ספקים

    /// מעלה קובצי חשבוניות ומחזיר טיוטות מפורסרות לאישור.
    func uploadInvoices(files: [(filename: String, data: Data)]) async throws -> [DomainRecord] {
        let data = try await postMultipart(
            "finance-invoices-upload",
            files: files.map { MultipartFile(field: "files", filename: $0.filename, mimeType: "application/pdf", data: $0.data) }
        )
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: data)
        guard case .array(let drafts)? = decoded["drafts"] else { return [] }
        return drafts.compactMap {
            if case .object(let fields) = $0 { return DomainRecord(fields: fields) }
            return nil
        }
    }

    func saveInvoiceDraft(row: [String: Any]) async throws {
        try await postJSON("finance-invoices-save", body: ["row": row])
    }

    // MARK: - הצעות מחיר

    /// יוצר הצעת מחיר ב-GreenInvoice ומחזיר את תוצאת השרת (מספר הצעה, קישורי Drive).
    func finalizeQuote(mode: String, data orderData: [String: Any]) async throws -> DomainRecord {
        let data = try await postJSON("finalize-quote", body: ["mode": mode, "data": orderData])
        let fields = try JSONDecoder().decode([String: JSONValue].self, from: data)
        return DomainRecord(fields: fields)
    }

    /// שולח הצעת מחיר במייל. נושא/גוף ריקים → השרת ממלא את הנוסח הקנוני.
    /// `testSend` — כמו בדסקטופ: שליחה אליך בלבד לבדיקת הנוסח.
    func sendQuoteEmail(historyID: String, recipients: String,
                        subject: String = "", body bodyText: String = "",
                        testSend: Bool = false) async throws -> String {
        let data = try await postMultipart("quote-send-email", fields: [
            "history_id": historyID,
            "recipients": recipients,
            "subject": subject,
            "plain_body": bodyText,
            "test_send": testSend ? "true" : "false",
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String, !message.isEmpty {
            return message
        }
        return "ההצעה נשלחה במייל."
    }

    func sendQuoteWhatsapp(phone: String, message: String, quoteFile: String) async throws {
        try await postJSON("quote-send-whatsapp", body: [
            "phone": phone, "message": message, "quote_file": quoteFile,
        ])
    }

    /// נתוני ההצעה כבסיס להזמנה (המרה להזמנת רכש).
    func quoteOrderData(historyID: String) async throws -> DomainRecord {
        let data = try await postJSON("quote-history-order-data", body: ["history_id": historyID])
        let fields = try JSONDecoder().decode([String: JSONValue].self, from: data)
        // השרת מחזיר את שורת ההצעה תחת row (עם items בצד); פורמים לרשומה שטוחה.
        if case .object(var inner)? = fields["row"] {
            inner["items"] = fields["items"]
            return DomainRecord(fields: inner)
        }
        return DomainRecord(fields: fields)
    }

    func uploadSignedQuote(historyID: String, fileData: Data, filename: String, mimeType: String) async throws {
        try await postMultipart(
            "quote-history-upload-signed",
            fields: ["history_id": historyID],
            files: [MultipartFile(field: "file", filename: filename, mimeType: mimeType, data: fileData)]
        )
    }

    /// קישור פתיחה להצעה (Drive או קובץ מקומי) — כמו בדסקטופ.
    func resolveQuoteURL(historyID: String) async throws -> String {
        let data = try await getJSON("quote-history-quote-resolve", query: ["history_id": historyID])
        let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return (object?["url"] as? String) ?? ""
    }

    // MARK: - הפקת קבלה

    static let receiptPaymentMethods: [(key: String, label: String)] = [
        ("bank_transfer", "העברה בנקאית"),
        ("check", "צ'ק"),
        ("cash", "מזומן"),
        ("payment_app", "ביט / אפליקציית תשלום"),
    ]

    /// מפיק קבלה לחשבונית ב-GreenInvoice. השרת משלים את פרטי החשבונית לפי המספר.
    /// אחוז ניכוי המס במקור — כמו ברירת המחדל בדסקטופ.
    static let withholdingPercent = 3.0

    /// חישוב הניכוי מהסכום המלא — אותה נוסחה כמו בדסקטופ (עיגול לאגורה).
    static func withholdingBreakdown(gross: Double, percent: Double = withholdingPercent)
        -> (withheld: Double, paid: Double) {
        let withheld = (gross * percent / 100 * 100).rounded() / 100
        let paid = ((gross - withheld) * 100).rounded() / 100
        return (withheld, paid)
    }

    /// פרטי צ'ק לקבלה — כל הארבעה חובה כשאמצעי התשלום הוא צ'ק (כמו ב-GreenInvoice).
    struct CheckDetails {
        var checkNumber = ""
        var bankNumber = ""
        var branchNumber = ""
        var accountNumber = ""

        var isComplete: Bool {
            ![checkNumber, bankNumber, branchNumber, accountNumber]
                .contains { $0.trimmingCharacters(in: .whitespaces).isEmpty }
        }
    }

    /// מפיק קבלה. `grossAmount` הוא הסכום המלא; כשהלקוח ניכה במקור, הניכוי
    /// מחושב אוטומטית (3%) והקבלה מופקת על הסכום ששולם בפועל — כמו בדסקטופ.
    func createReceipt(mode: String, invoiceNumber: String, grossAmount: Double,
                       paymentMethod: String, paymentDate: String, notes: String,
                       withholdingApplied: Bool,
                       checkDetails: CheckDetails? = nil,
                       paymentAppProvider: String = "") async throws -> String {
        if paymentMethod == "check" {
            guard let checkDetails, checkDetails.isComplete else {
                throw APIError(message: "בתשלום בצ'ק צריך למלא מספר צ'ק, בנק, סניף ומספר חשבון.", statusCode: 400)
            }
        }
        let breakdown = APIClient.withholdingBreakdown(gross: grossAmount)
        let withheld = withholdingApplied ? breakdown.withheld : 0
        let paid = withholdingApplied ? breakdown.paid : grossAmount
        var payment: [String: Any] = [
            "payment_method": paymentMethod,
            "amount": paid,
            "payment_date": paymentDate,
            "notes": notes,
        ]
        if paymentMethod == "check", let checkDetails {
            payment["check_number"] = checkDetails.checkNumber
            payment["bank_number"] = checkDetails.bankNumber
            payment["branch_number"] = checkDetails.branchNumber
            payment["account_number"] = checkDetails.accountNumber
        }
        if paymentMethod == "payment_app" {
            payment["payment_app_provider"] = paymentAppProvider.isEmpty ? "bit" : paymentAppProvider
        }
        let data = try await postJSON("greeninvoice-create-receipt", body: [
            "mode": mode,
            "invoice": ["number": invoiceNumber],
            "payment": payment,
            "withholding": [
                "applied": withholdingApplied,
                "gross_amount": grossAmount,
                "percent": APIClient.withholdingPercent,
                "withheld_amount": withheld,
                "paid_amount": paid,
            ],
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            let receipt = (object["receipt_number"] as? String)
                ?? ((object["sync_result"] as? [String: Any])?["receipt_number"] as? String) ?? ""
            if !receipt.isEmpty { return "קבלה \(receipt) הופקה." }
            if let message = object["message"] as? String, !message.isEmpty { return message }
        }
        return "הקבלה הופקה."
    }

    // MARK: - הזמנת רכש לספק

    func createSupplierPO(mode: String, supplier: [String: String],
                          items: [[String: Any]], remarks: String,
                          subtotal: Double, vat: Double, total: Double) async throws {
        var body: [String: Any] = [
            "mode": mode,
            "remarks": remarks,
            "items": items,
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
        ]
        for (key, value) in supplier { body[key] = value }
        try await postJSON("inventory-purchase-orders-create", body: body)
    }

    func sendSupplierPOEmail(historyID: String, recipients: String,
                             subject: String = "", body bodyText: String = "") async throws -> String {
        let data = try await postMultipart("inventory-purchase-orders-send-email", fields: [
            "history_id": historyID,
            "recipients": recipients,
            "subject": subject,
            "plain_body": bodyText,
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String, !message.isEmpty {
            return message
        }
        return "הזמנת הרכש נשלחה במייל."
    }

    func sendSupplierPOWhatsapp(historyID: String, phone: String, message: String) async throws {
        try await postJSON("inventory-purchase-orders-send-whatsapp", body: [
            "history_id": historyID, "phone": phone, "message": message,
        ])
    }

    // MARK: - מדבקות משלוח (ללא הזמנה)

    func createLabelsOnly(labels: [[String: Any]]) async throws -> String {
        let data = try await postJSON("labels-only", body: ["labels": labels])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String, !message.isEmpty {
            return message
        }
        return "המדבקות נוצרו ונשלחו."
    }

    // MARK: - עזרי קומפוזר

    /// לקוחות אחרונים למילוי מהיר בקומפוזרים.
    func recentManualCustomers() async throws -> [DomainRecord] {
        let data = try await getJSON("manual-order-recent-customers")
        return (try? DomainRecord.records(fromRowsJSON: data)) ?? []
    }

    func sendAdminDocWhatsapp(assetKey: String, phone: String, message: String) async throws -> String {
        let data = try await postMultipart("admin-business-doc-send-whatsapp", fields: [
            "asset_key": assetKey, "phone": phone, "message": message,
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let text = object["message"] as? String, !text.isEmpty {
            return text
        }
        return "המסמך נשלח בוואטסאפ."
    }

    // MARK: - ריכוז חשבוניות לרו"ח

    /// שולח ריכוז חשבוניות ספקים לרו"ח לפי מועדי דיווח — כמו הכלי בדסקטופ.
    /// נושא/גוף ריקים → השרת בונה את הנוסח הקנוני.
    func sendAccountantSummary(reportDueDates: [String], recipients: String,
                               includePDF: Bool, includeXLSX: Bool, includeZip: Bool,
                               includeVatSummary: Bool, testSend: Bool) async throws -> String {
        let data = try await postJSON("finance-invoices-send-email", body: [
            "report_due_dates": reportDueDates,
            "recipients": recipients,
            "include_pdf": includePDF,
            "include_xlsx": includeXLSX,
            "include_zip": includeZip,
            "include_vat_summary": includeVatSummary,
            "test_send": testSend,
            "subject": "",
            "message": "",
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String, !message.isEmpty {
            return message
        }
        return testSend ? "ריכוז החשבוניות נשלח אליך (מצב בדיקה)." : "ריכוז החשבוניות נשלח לרו\"ח."
    }

    // MARK: - אישורי מסירה

    func sendDeliveryConfirmation(record: DomainRecord, subject: String, message: String,
                                  recipients: String, testSend: Bool,
                                  sendNewBankDetails: Bool = false) async throws -> String {
        let data = try await postJSON("delivery-confirmations-send", body: [
            "fulfillment_id": record["fulfillment_id"],
            "po_number": record["po_number"],
            "tax_invoice_number": record["tax_invoice_number"],
            "source_mode": record["source_mode"],
            "mode": "prod",
            "test_send": testSend,
            "send_new_bank_details": sendNewBankDetails,
            "subject": subject,
            "message": message,
            "recipients": recipients,
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let text = object["message"] as? String, !text.isEmpty {
            return text
        }
        return testSend ? "אישור המסירה נשלח אליך (מצב בדיקה)." : "אישור המסירה נשלח."
    }

    /// מעלה תעודת משלוח חתומה (צילום/קובץ) ומשייך אותה לאישור המסירה.
    func uploadSignedDelivery(record: DomainRecord, fileData: Data,
                              filename: String, mimeType: String) async throws {
        try await postMultipart(
            "delivery-confirmations-upload",
            query: [
                "fulfillment_id": record["fulfillment_id"],
                "po_number": record["po_number"],
                "tax_invoice_number": record["tax_invoice_number"],
                "source_mode": record["source_mode"],
            ],
            files: [MultipartFile(field: "file", filename: filename, mimeType: mimeType, data: fileData)]
        )
    }

    /// מוחק את התעודה החתומה שהועלתה לאישור המסירה.
    func deleteSignedDelivery(record: DomainRecord) async throws {
        try await postJSON("delivery-confirmations-delete-upload", body: [
            "fulfillment_id": record["fulfillment_id"],
            "po_number": record["po_number"],
            "tax_invoice_number": record["tax_invoice_number"],
            "source_mode": record["source_mode"],
        ])
    }

    // MARK: - התקנות

    static let installationStatusOptions = ["ממתין לתיאום", "תואם", "הותקן חלקית", "הושלם", "מושהה", "בוטל"]
    static let installationDelayReasons = ["ממתין לתיאום מול שטח", "מחכים לדלתות באתר", "ביקור המשך", "גישה לאתר / לוגיסטיקה", "לקוח דחה", "הזמנה בוטלה", "אחר"]

    func updateInstallationCase(installationID: String, status: String, delayReason: String,
                                nextVisitDate: String, notes: String) async throws {
        try await postJSON("installations-case-update", body: [
            "installation_id": installationID,
            "row": [
                "installation_id": installationID,
                "status": status,
                "delay_reason": delayReason,
                "next_visit_date": nextVisitDate,
                "notes": notes,
            ],
        ])
    }

    func saveInstallationVisit(installationID: String, visitDate: String,
                               installedItems: [[String: Any]], notes: String) async throws {
        try await postJSON("installations-visit-save", body: [
            "visit": [
                "installation_id": installationID,
                "visit_date": visitDate,
                "installed_items": installedItems,
                "notes": notes,
            ],
        ])
    }

    func deleteInstallationVisit(visitID: String) async throws {
        try await postJSON("installations-visit-delete", body: ["visit_id": visitID])
    }

    // MARK: - שיוך לקוח לתחום

    /// תחומי לקוח תקפים בשרת.
    static let customerDomains: [(key: String, label: String)] = [
        ("construction", "תחום הבנייה"),
        ("textile", "עיבוד טכני בטקסטיל"),
        ("supplier", "ספק"),
        ("graphic_web", "עיצוב גרפי ואינטרנט"),
    ]

    func assignCustomerDomain(record: DomainRecord, domainKey: String) async throws {
        try await postJSON("customers-assign-domain", body: [
            "rows": [record.jsonObject],
            "customer_domain": domainKey,
        ])
    }

    // MARK: - הלוואות, משכנתאות וצי רכבים (מנהלה)

    struct AdminLendingFact: Identifiable, Equatable {
        let label: String
        let value: String
        var id: String { label }
    }

    struct AdminLendingDoc: Identifiable, Equatable {
        let key: String
        let label: String
        var id: String { key }
    }

    struct AdminCreditCard: Identifiable, Equatable {
        let title: String
        let kicker: String
        let group: String   // loan / mortgage
        let blurb: String
        let facts: [AdminLendingFact]
        let details: [String]
        let docs: [AdminLendingDoc]
        var id: String { title }
    }

    struct AdminVehicleCard: Identifiable, Equatable {
        let name: String
        let plate: String
        let title: String
        let subtitle: String
        let imagePath: String
        let facts: [AdminLendingFact]
        let docs: [AdminLendingDoc]
        var id: String { name + plate }
    }

    struct AdminLending: Equatable {
        let loans: [AdminCreditCard]
        let vehicles: [AdminVehicleCard]
        let loansTotal: String
        let mortgagesTotal: String
    }

    private static func lendingFacts(_ value: JSONValue?) -> [AdminLendingFact] {
        guard case .array(let items)? = value else { return [] }
        return items.compactMap {
            guard case .object(let fields) = $0 else { return nil }
            let record = DomainRecord(fields: fields)
            guard !record["label"].isEmpty else { return nil }
            return AdminLendingFact(label: record["label"], value: record["value"])
        }
    }

    private static func lendingDocs(_ value: JSONValue?) -> [AdminLendingDoc] {
        guard case .array(let items)? = value else { return [] }
        return items.compactMap {
            guard case .object(let fields) = $0 else { return nil }
            let record = DomainRecord(fields: fields)
            guard !record["key"].isEmpty else { return nil }
            return AdminLendingDoc(key: record["key"], label: record["label"])
        }
    }

    /// הלוואות, משכנתאות וצי הרכבים — שיקוף הסקשנים מטאב המנהלה בדסקטופ.
    /// הנתונים נפרסרים בשרת מתבנית הדסקטופ (מקור אמת יחיד) כולל יתרות מחושבות.
    func adminLending() async throws -> AdminLending {
        let data = try await getJSON("mobile/admin-lending")
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: data)

        var loans: [AdminCreditCard] = []
        if case .array(let cards)? = decoded["loans"] {
            for value in cards {
                guard case .object(let fields) = value else { continue }
                let record = DomainRecord(fields: fields)
                var details: [String] = []
                if case .array(let items)? = fields["details"] {
                    details = items.compactMap {
                        if case .string(let text) = $0 {
                            return text.trimmingCharacters(in: .whitespacesAndNewlines)
                        }
                        return nil
                    }
                }
                loans.append(AdminCreditCard(
                    title: record["title"], kicker: record["kicker"],
                    group: record["group"], blurb: record["blurb"],
                    facts: Self.lendingFacts(fields["facts"]),
                    details: details,
                    docs: Self.lendingDocs(fields["docs"])
                ))
            }
        }

        var vehicles: [AdminVehicleCard] = []
        if case .array(let cards)? = decoded["vehicles"] {
            for value in cards {
                guard case .object(let fields) = value else { continue }
                let record = DomainRecord(fields: fields)
                vehicles.append(AdminVehicleCard(
                    name: record["name"], plate: record["plate"],
                    title: record["title"], subtitle: record["subtitle"],
                    imagePath: record["image_path"],
                    facts: Self.lendingFacts(fields["facts"]),
                    docs: Self.lendingDocs(fields["docs"])
                ))
            }
        }

        var loansTotal = ""
        var mortgagesTotal = ""
        if case .object(let totals)? = decoded["totals"] {
            let record = DomainRecord(fields: totals)
            loansTotal = record["loans"]
            mortgagesTotal = record["mortgages"]
        }
        return AdminLending(loans: loans, vehicles: vehicles, loansTotal: loansTotal, mortgagesTotal: mortgagesTotal)
    }

    // MARK: - מסמכי שיווק ומנהלה

    struct MarketingDoc: Identifiable, Equatable {
        let assetKey: String
        let label: String
        let category: String
        let shareURL: String
        var id: String { assetKey }
    }

    func marketingDocs() async throws -> [MarketingDoc] {
        let data = try await getJSON("marketing-docs-state")
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: data)
        guard case .array(let docs)? = decoded["docs"] else { return [] }
        return docs.compactMap { value in
            guard case .object(let fields) = value else { return nil }
            let record = DomainRecord(fields: fields)
            let key = record["asset_key"]
            guard !key.isEmpty else { return nil }
            return MarketingDoc(
                assetKey: key,
                label: record["label"].isEmpty ? key : record["label"],
                category: record["category"],
                shareURL: record.first(of: ["share_link_url", "drive_url"])
            )
        }
    }

    func sendAdminDocEmail(assetKey: String, recipients: String, subject: String,
                           body bodyText: String, testSend: Bool) async throws -> String {
        let data = try await postMultipart("admin-business-doc-send-email", fields: [
            "asset_key": assetKey,
            "recipients": recipients,
            "subject": subject,
            "plain_body": bodyText,
            "test_send": testSend ? "true" : "false",
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let text = object["message"] as? String, !text.isEmpty {
            return text
        }
        return testSend ? "המסמך נשלח אליך (מצב בדיקה)." : "המסמך נשלח."
    }
}
