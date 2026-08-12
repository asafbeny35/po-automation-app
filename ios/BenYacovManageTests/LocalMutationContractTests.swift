import XCTest
@testable import BenYacovManage

/// מוטציות אמיתיות מול שרת מקומי — מחזורי צור→אמת→נקה, לפי מוסכמות
/// TEST_PRE_RUN_AND_CLEANUP_STRATEGY.md: כל ישות בדיקה מסומנת "TEST" + "נעלולי פלא",
/// יצירת מסמכים רק בסנדבוקס, וואטסאפ רק ל-0547720142.
/// הרצה: שרת על 8017 + `TEST_RUNNER_BY_CONTRACT_MUTATIONS=1`.
final class LocalMutationContractTests: XCTestCase {
    private static var didLogin = false
    private var client: APIClient!
    private var baseURL: URL!

    static let testMarker = "TEST נעלולי פלא"

    override func setUp() async throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["BY_CONTRACT_MUTATIONS"] == "1"
                || FileManager.default.fileExists(atPath: "/tmp/by_contract_mutation_tests"),
            "טסטי מוטציות אמיתיים רצים רק עם BY_CONTRACT_MUTATIONS=1 ושרת על 8017"
        )
        baseURL = URL(string: ProcessInfo.processInfo.environment["BY_CONTRACT_URL"] ?? "http://127.0.0.1:8017")!
        client = APIClient(baseURL: baseURL, transport: LiveTransport())
        if !Self.didLogin {
            var request = URLRequest(url: baseURL.appendingPathComponent("auth/dev-login"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("1", forHTTPHeaderField: "x-po-debug-auth")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["user_id": "asaf"])
            _ = try await URLSession.shared.data(for: request)
            Self.didLogin = true
        }
    }

    /// רשת ביטחון: אחרי כל טסט — סריקה ומחיקה של כל שריד "נעלולי פלא",
    /// כולל שורות שנוצרו כתופעת לוואי (finalize מוסיף שורת גבייה לטבלת התשלומים)
    /// ושרידים של טסטים שנקטעו באמצע.
    override func tearDown() async throws {
        guard client != nil else { return }

        // שורות תשלומים.
        let payments = (try? await client.domainRows(.paymentsTransfer, forceRefresh: true)) ?? []
        let paymentLeftovers = payments
            .filter { $0["customer_name"].contains("נעלולי פלא") }
            .sorted { (Int($0["_sheet_row"]) ?? 0) > (Int($1["_sheet_row"]) ?? 0) }
        for row in paymentLeftovers {
            try? await client.postJSON("payments-transfer-delete-row", body: [
                "sheet_title": row["_sheet_title"],
                "row_number": Int(row["_sheet_row"]) ?? -1,
                "row": row.jsonObject,
            ])
        }

        // תזכורות שיווק.
        let reminders = (try? await client.domainRows(.marketingReminders, forceRefresh: true)) ?? []
        for reminder in reminders where reminder["customer_name"].contains("נעלולי פלא")
            || reminder["note_text"].contains("נעלולי פלא") {
            try? await client.postJSON("marketing-reminder-delete", body: [
                "reminder_id": reminder["reminder_id"],
            ])
        }

        // שורות שעות של חודש הבדיקה העתידי.
        let hours = (try? await client.domainRows(.hrHours, forceRefresh: true)) ?? []
        for row in hours where row["month_key"] == "2030-01" {
            try? await client.postJSON("hr-hours-delete", body: ["row_id": row["row_id"]])
        }

        // רשומות היסטוריה של הזמנות בדיקה (finalize שנקטע באמצע).
        let history = (try? await client.domainRows(.orderHistory, forceRefresh: true)) ?? []
        for row in history where row["customer_name"].contains("נעלולי פלא") {
            try? await client.postJSON("order-history-delete", body: [
                "history_id": row["history_id"],
                "fulfillment_id": row["fulfillment_id"],
                "po_number": row["po_number"],
                "customer_name": row["customer_name"],
                "mode": row["mode"],
            ])
        }

        // הצעות מחיר של בדיקה.
        let quotes = (try? await client.domainRows(.quoteHistory, forceRefresh: true)) ?? []
        for row in quotes where row["customer_name"].contains("נעלולי פלא") {
            try? await client.postJSON("quote-history-delete", body: ["history_id": row["history_id"]])
        }

        // הזמנות רכש לספק של בדיקה.
        let supplierPOs = (try? await client.domainRows(.inventoryPurchaseOrders, forceRefresh: true)) ?? []
        for row in supplierPOs where row["supplier_name"].contains("נעלולי פלא") {
            try? await client.postJSON("inventory-purchase-orders-delete", body: ["history_id": row["history_id"]])
        }

        // מנהלי עבודה של בדיקה.
        let managers = (try? await client.domainRows(.marketingWorkManagers, forceRefresh: true)) ?? []
        for row in managers where row["full_name"].contains("נעלולי פלא") {
            try? await client.postJSON("marketing-work-managers-delete", body: ["row_id": row["row_id"]])
        }

        if !paymentLeftovers.isEmpty {
            print("CONTRACT-CLEANUP: נוקו \(paymentLeftovers.count) שורות תשלומים של בדיקה")
        }
    }

    // MARK: - תזכורת שיווק: שמירה → אימות → מחיקה

    func testReminderLifecycle() async throws {
        let marker = "\(Self.testMarker) תזכורת \(Int(Date().timeIntervalSince1970))"
        try await client.postJSON("marketing-save-reminder", body: [
            "customer": ["customer_name": marker],
            "customer_name": marker,
            "note_text": "\(Self.testMarker) — נוצר אוטומטית מטסט האפליקציה",
            "due_date": "2030-01-01",
            "channel": "whatsapp",
            "status": "פתוח",
        ])
        let created = try await client.domainRows(.marketingReminders, forceRefresh: true)
            .first { $0["customer_name"].lowercased() == marker.lowercased() }
        let reminder = try XCTUnwrap(created, "התזכורת לא נוצרה בשרת האמיתי")
        XCTAssertFalse(reminder["reminder_id"].isEmpty)
        XCTAssertEqual(reminder["channel"], "whatsapp", "ערוץ התזכורת חייב להישמר בשרת")

        // ניקוי + אימות.
        try await client.postJSON("marketing-reminder-delete", body: [
            "reminder_id": reminder["reminder_id"],
        ])
        let after = try await client.domainRows(.marketingReminders, forceRefresh: true)
        XCTAssertNil(after.first { $0["reminder_id"] == reminder["reminder_id"] },
                     "התזכורת לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - שורת תשלומים בגיליון האמיתי: הוספה → עדכון → שולם/לא → מחיקה

    func testPaymentRowFullLifecycle() async throws {
        let marker = "\(Self.testMarker) תשלומים \(Int(Date().timeIntervalSince1970))"
        try await client.postJSON("payments-transfer-row", body: [
            "row": [
                "customer_name": marker,
                "payment_direction": "תשלום",
                "amount": "1",
                "due_date": "01/01/2030",
                "notes": Self.testMarker,
                "paid": "FALSE",
            ],
        ])
        var rows = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        var row = try XCTUnwrap(rows.first { $0["customer_name"].lowercased() == marker.lowercased() },
                                "השורה לא נוספה לגיליון האמיתי")
        defer {
            // רשת ביטחון: אם משהו נכשל באמצע — עדיין מנקים.
        }

        // עדכון סכום.
        var updated = row.jsonObject
        updated["amount"] = "2"
        try await client.postJSON("payments-transfer-update-row", body: [
            "sheet_title": row["_sheet_title"],
            "row_number": Int(row["_sheet_row"]) ?? -1,
            "row": updated,
        ])
        rows = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        row = try XCTUnwrap(rows.first { $0["customer_name"].lowercased() == marker.lowercased() })
        XCTAssertEqual(row.number("amount"), 2, "עדכון הסכום לא נקלט בגיליון")

        // סימון שולם ואז ביטול — הפעולה הקריטית של המסך.
        for paid in [true, false] {
            try await client.postJSON("payments-transfer-paid", body: [
                "sheet_title": row["_sheet_title"],
                "row_number": Int(row["_sheet_row"]) ?? -1,
                "paid": paid,
            ])
            rows = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
            row = try XCTUnwrap(rows.first { $0["customer_name"].lowercased() == marker.lowercased() })
            XCTAssertEqual(row.bool("paid"), paid, "סימון שולם=\(paid) לא נקלט")
        }

        // מחיקה + אימות.
        try await client.postJSON("payments-transfer-delete-row", body: [
            "sheet_title": row["_sheet_title"],
            "row_number": Int(row["_sheet_row"]) ?? -1,
            "row": row.jsonObject,
        ])
        rows = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertNil(rows.first { $0["customer_name"].lowercased() == marker.lowercased() },
                     "שורת הבדיקה לא נמחקה מהגיליון — נשאר זבל!")
    }

    // MARK: - הערת הזמנה בעבודה: שמירה (multipart!) → אימות → שחזור המקור

    func testWorkingOrderNoteSaveAndRestore() async throws {
        let orders = try await client.domainRows(.workingOrders)
        try XCTSkipIf(orders.isEmpty, "אין הזמנות בעבודה בדאטה האמיתי")
        let target = orders[0]
        let originalNote = target["order_note_text"]
        let testNote = "\(Self.testMarker) הערה \(Int(Date().timeIntervalSince1970))"

        try await client.postMultipart("working-orders-note-save", fields: [
            "row_id": target["row_id"],
            "note_text": testNote,
        ])
        var rows = try await client.domainRows(.workingOrders, forceRefresh: true)
        XCTAssertEqual(rows.first { $0["row_id"] == target["row_id"] }?["order_note_text"], testNote,
                       "ההערה לא נשמרה — חוזה ה-multipart שבור")

        // שחזור המקור.
        try await client.postMultipart("working-orders-note-save", fields: [
            "row_id": target["row_id"],
            "note_text": originalNote,
        ])
        rows = try await client.domainRows(.workingOrders, forceRefresh: true)
        XCTAssertEqual(rows.first { $0["row_id"] == target["row_id"] }?["order_note_text"], originalNote,
                       "ההערה המקורית לא שוחזרה!")
    }

    // MARK: - תיק התקנה: עדכון → אימות → שחזור

    func testInstallationCaseUpdateAndRestore() async throws {
        let cases = try await client.domainRows(.installationCases)
        // בוחרים תיק אמיתי (לא pending שנבנה מהזמנות בעבודה).
        let target = try XCTUnwrap(cases.first { $0["installation_id"].hasPrefix("installation") },
                                   "אין תיקי התקנה בדאטה האמיתי")
        let original = (status: target["status"], reason: target["delay_reason"],
                        next: target["next_visit_date"], notes: target["notes"])
        let testNotes = "\(Self.testMarker) \(Int(Date().timeIntervalSince1970))"

        try await client.updateInstallationCase(
            installationID: target["installation_id"], status: original.status,
            delayReason: original.reason, nextVisitDate: original.next, notes: testNotes
        )
        var rows = try await client.domainRows(.installationCases, forceRefresh: true)
        XCTAssertEqual(rows.first { $0["installation_id"] == target["installation_id"] }?["notes"],
                       testNotes, "עדכון תיק ההתקנה לא נקלט")

        try await client.updateInstallationCase(
            installationID: target["installation_id"], status: original.status,
            delayReason: original.reason, nextVisitDate: original.next, notes: original.notes
        )
        rows = try await client.domainRows(.installationCases, forceRefresh: true)
        XCTAssertEqual(rows.first { $0["installation_id"] == target["installation_id"] }?["notes"],
                       original.notes, "הערות התיק המקוריות לא שוחזרו!")
    }

    // MARK: - שעות עבודה: שמירה → אימות → מחיקה

    func testHRHoursLifecycle() async throws {
        // השרת דורש employee_id אמיתי — לוקחים עובד קיים ומסמנים בחודש עתידי ייעודי.
        let employees = try await client.domainRows(.hrEmployees)
        let employee = try XCTUnwrap(employees.first, "אין עובדים בדאטה האמיתי")
        let marker = employee["full_name"]
        try await client.postJSON("hr-hours-save", body: [
            "row": [
                "employee_id": employee["employee_id"],
                "employee_name": marker,
                "month_key": "2030-01",
                "regular_hours": "1",
                "overtime_hours": "0",
            ],
        ])
        let created = try await client.domainRows(.hrHours, forceRefresh: true).first { $0["employee_name"] == marker && $0["month_key"] == "2030-01" }
        let row = try XCTUnwrap(created, "שורת השעות לא נוצרה")

        try await client.postJSON("hr-hours-delete", body: ["row_id": row["row_id"]])
        let after = try await client.domainRows(.hrHours, forceRefresh: true)
        XCTAssertNil(after.first { $0["row_id"] == row["row_id"] },
                     "שורת השעות לא נמחקה — נשאר זבל!")
    }

    // MARK: - לקוח: יצירה בסנדבוקס → אימות → מחיקה

    func testCustomerLifecycleSandbox() async throws {
        let marker = "\(Self.testMarker) לקוח \(Int(Date().timeIntervalSince1970))"
        // רשימת הלקוחות באפליקציה משקפת פרוד — לקוח סנדבוקס מאומת דרך תשובת היצירה.
        let data = try await client.postJSON("customers-create", body: [
            "mode": "sandbox",
            "customer": [
                "customer_name": marker,
                "name": marker,
                "customer_id": "999999998",
                "idNumber": "999999998",
                "emails": "asafbeny@gmail.com",
            ],
        ])
        let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(payload["status"] as? String, "ok")
        let createdPayload = try XCTUnwrap(payload["created"] as? [String: Any], "אין אובייקט created בתשובה")
        let guid = (createdPayload["customer_guid"] as? String)
            ?? (createdPayload["id"] as? String) ?? ""
        XCTAssertFalse(guid.isEmpty, "ללקוח שנוצר אין מזהה: \(createdPayload)")

        // ניקוי: מחיקת לקוח הסנדבוקס.
        var toDelete = createdPayload
        toDelete["customer_guid"] = guid
        toDelete["mode"] = "sandbox"
        try await client.postJSON("customers-delete", body: ["customer": toDelete, "mode": "sandbox"])
    }

    // MARK: - הזרימה הגדולה: פרסור PDF אמיתי → finalize סנדבוקס → מחיקה מההיסטוריה

    func testProcessAndFinalizeSandboxWithRealPDF() async throws {
        // PDF אמיתי של הזמנת רכש מהמערכת.
        let uploadsDir = URL(fileURLWithPath: "/Users/asafbeny/Downloads/po_automation_app/uploads/working_orders")
        let pdfs = (try? FileManager.default.contentsOfDirectory(at: uploadsDir, includingPropertiesForKeys: nil))?
            .filter { $0.pathExtension.lowercased() == "pdf" } ?? []
        let pdfURL = try XCTUnwrap(pdfs.first, "אין PDF אמיתי של הזמנת רכש ב-uploads")
        let pdfData = try Data(contentsOf: pdfURL)

        // פרסור אמיתי בשרת — עצם הפרסור חייב להצליח (איכות החילוץ תלויה בפרסר של הלקוח).
        let parsed = try await client.processPurchaseOrder(
            pdf: pdfData, filename: pdfURL.lastPathComponent, mode: "sandbox"
        )
        XCTAssertFalse(parsed.fields.isEmpty, "הפרסור האמיתי לא החזיר שדות")
        if parsed["customer_name"].isEmpty {
            print("CONTRACT: הפרסר לא זיהה לקוח בקובץ \(pdfURL.lastPathComponent) — ממשיכים כהזמנה ידנית")
        }

        // finalize בסנדבוקס עם payload ידני מלא ומסומן TEST, בלי וואטסאפ.
        let poMarker = "TEST-PLA-\(Int(Date().timeIntervalSince1970))"
        var data = parsed.jsonObject
        data["customer_name"] = "\(Self.testMarker) בעמ"
        data["customer_id"] = "999999998"
        data["po_number"] = poMarker
        data["po_date"] = "01/01/2030"
        data["delivery_address"] = "אתר בדיקות, נעלולי פלא"
        data["manual_entry"] = true
        data["payment_terms_label"] = "שוטף + 30"
        data["payment_terms_days"] = "30"
        data["items"] = [[
            "description": "\(Self.testMarker) פריט בדיקה",
            "sku": "TEST-SKU",
            "unit": "יחידה",
            "quantity": 1,
            "unit_price": 1,
            "line_total": 1,
            "generate_label": false,
        ]]
        data["subtotal"] = 1
        data["vat"] = 0.17
        data["total"] = 1.17
        let message = try await client.finalizeOrder(mode: "sandbox", data: data, skipWhatsapp: true)
        XCTAssertFalse(message.isEmpty)

        // הרשומה נכנסה להיסטוריה האמיתית.
        let history = try await client.domainRows(.orderHistory, forceRefresh: true)
        let created = try XCTUnwrap(history.first { $0["po_number"] == poMarker },
                                    "הזמנת הסנדבוקס לא נרשמה בהיסטוריה")
        XCTAssertTrue(["SB", "SANDBOX"].contains(created["mode"].uppercased()),
                      "המסמכים חייבים להיווצר בסנדבוקס בלבד! mode=\(created["mode"])")
        let documentEvidence = created.first(of: ["delivery_number", "delivery_document_number",
                                                  "delivery_document_id", "tax_invoice_number",
                                                  "tax_invoice_document_id", "fulfillment_id"])
        XCTAssertFalse(documentEvidence.isEmpty,
                       "לא נוצרו מסמכים בסנדבוקס. שדות הרשומה: \(created.fields.keys.sorted())")

        // ניקוי: מחיקת הרשומה מההיסטוריה.
        try await client.postJSON("order-history-delete", body: [
            "history_id": created["history_id"],
            "fulfillment_id": created["fulfillment_id"],
            "po_number": created["po_number"],
            "customer_name": created["customer_name"],
            "mode": created["mode"],
        ])
        let after = try await client.domainRows(.orderHistory, forceRefresh: true)
        XCTAssertNil(after.first { $0["po_number"] == poMarker },
                     "רשומת הסנדבוקס לא נמחקה מההיסטוריה!")

        // הקסקדה החדשה: שורת הגבייה ש-finalize יצר נמחקה יחד עם ההיסטוריה,
        // בלי להסתמך על ניקוי ה-tearDown.
        let paymentsAfter = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertNil(paymentsAfter.first { $0["po_number"] == poMarker },
                     "מחיקת ההיסטוריה חייבת למחוק גם את שורת התשלומים המשויכת (קסקדה)")
    }

    // MARK: - תעודה חתומה: העלאה אמיתית → אימות → מחיקה

    func testSignedDeliveryUploadCycleOnRealRow() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        // שורה אמיתית בלי תעודה חתומה — מעלים ומוחקים, בלי להשאיר עקבות.
        guard let target = rows.first(where: {
            $0.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty
                && !$0["po_number"].isEmpty
        }) else {
            throw XCTSkip("אין אישור מסירה בלי תעודה חתומה בדאטה האמיתי")
        }

        try await client.uploadSignedDelivery(
            record: target,
            fileData: Data("%PDF-1.4 TEST נעלולי פלא".utf8),
            filename: "TEST-נעלולי-פלא-חתומה.pdf",
            mimeType: "application/pdf"
        )
        var after = try await client.domainRows(.deliveryConfirmations, forceRefresh: true)
        let updated = try XCTUnwrap(after.first { $0["po_number"] == target["po_number"] })
        XCTAssertFalse(updated.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty,
                       "ההעלאה האמיתית לא שייכה את הקובץ")

        // ניקוי מלא.
        try await client.deleteSignedDelivery(record: updated)
        after = try await client.domainRows(.deliveryConfirmations, forceRefresh: true)
        let restored = try XCTUnwrap(after.first { $0["po_number"] == target["po_number"] })
        XCTAssertTrue(restored.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty,
                      "התעודה לא נמחקה — נשאר קובץ בדיקה משויך לשורה אמיתית!")
    }

    // MARK: - וואטסאפ — אך ורק למספר הבדיקות 0547720142

    static let whatsappTestNumber = "0547720142"

    func testMarketingWhatsappGoesToTestNumberOnly() async throws {
        let data = try await client.postJSON("marketing-send-whatsapp", body: [
            "phone": Self.whatsappTestNumber,
            "message": "\(Self.testMarker) — הודעת בדיקה מסוויטת האפליקציה. אפשר להתעלם.",
            "customer_name": Self.testMarker,
        ])
        let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(payload["status"] as? String, "ok",
                       "שליחת וואטסאפ למספר הבדיקות נכשלה: \(payload)")
        XCTAssertEqual(payload["phone"] as? String, Self.whatsappTestNumber,
                       "הוואטסאפ חייב לצאת אך ורק למספר הבדיקות!")
    }

    /// הזרימה המלאה כולל וואטסאפ: PDF → פרסור → finalize סנדבוקס →
    /// המסמכים נשלחים בוואטסאפ למספר הבדיקות בלבד → ניקוי.
    func testFinalizeSandboxSendsWhatsappToTestNumber() async throws {
        let uploadsDir = URL(fileURLWithPath: "/Users/asafbeny/Downloads/po_automation_app/uploads/working_orders")
        let pdfs = (try? FileManager.default.contentsOfDirectory(at: uploadsDir, includingPropertiesForKeys: nil))?
            .filter { $0.pathExtension.lowercased() == "pdf" } ?? []
        let pdfURL = try XCTUnwrap(pdfs.first, "אין PDF אמיתי של הזמנת רכש ב-uploads")
        let parsed = try await client.processPurchaseOrder(
            pdf: try Data(contentsOf: pdfURL), filename: pdfURL.lastPathComponent, mode: "sandbox"
        )

        let poMarker = "TEST-WA-\(Int(Date().timeIntervalSince1970))"
        var data = parsed.jsonObject
        data["customer_name"] = "\(Self.testMarker) וואטסאפ בעמ"
        data["customer_id"] = "999999998"
        data["po_number"] = poMarker
        data["po_date"] = "01/01/2030"
        data["delivery_address"] = "אתר בדיקות, נעלולי פלא"
        data["manual_entry"] = true
        // כל הטלפונים = מספר הבדיקות בלבד, לפי האסטרטגיה.
        data["customer_phone"] = Self.whatsappTestNumber
        data["contact_phone"] = Self.whatsappTestNumber
        data["secondary_contact_phone"] = ""
        data["send_to_dad"] = false
        data["payment_terms_label"] = "שוטף + 30"
        data["payment_terms_days"] = "30"
        data["items"] = [[
            "description": "\(Self.testMarker) פריט וואטסאפ",
            "sku": "TEST-WA", "unit": "יחידה",
            "quantity": 1, "unit_price": 1, "line_total": 1, "generate_label": false,
        ]]
        data["subtotal"] = 1
        data["vat"] = 0.17
        data["total"] = 1.17

        // skipWhatsapp=false — השליחה האמיתית היא לב הטסט.
        let message = try await client.finalizeOrder(mode: "sandbox", data: data, skipWhatsapp: false)
        XCTAssertFalse(message.isEmpty)

        // ניקוי רשומת ההיסטוריה (שורת התשלומים מנוקה ב-tearDown).
        let history = try await client.domainRows(.orderHistory, forceRefresh: true)
        if let created = history.first(where: { $0["po_number"] == poMarker }) {
            try await client.postJSON("order-history-delete", body: [
                "history_id": created["history_id"],
                "fulfillment_id": created["fulfillment_id"],
                "po_number": created["po_number"],
                "customer_name": created["customer_name"],
                "mode": created["mode"],
            ])
        }
    }

    // MARK: - אישור מסירה במייל — מצב בדיקה (אליך בלבד)

    func testDeliveryConfirmationTestSendReachesAsaf() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        // השרת דורש חשבונית מס + תעודה חתומה — בוחרים שורה כשירה.
        let eligible = rows.first {
            !$0["tax_invoice_number"].isEmpty
                && !$0.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty
        }
        guard let record = eligible else {
            throw XCTSkip("אין אישור מסירה כשיר לשליחה בדאטה האמיתי")
        }
        let message = try await client.sendDeliveryConfirmation(
            record: record,
            subject: "\(Self.testMarker) — אישור מסירה מטסט האפליקציה",
            message: "בדיקת מערכת. אפשר להתעלם.",
            recipients: "",
            testSend: true
        )
        XCTAssertTrue(message.contains("בדיק") || message.contains("נשלח"),
                      "שליחת הבדיקה נכשלה: \(message)")
    }

    // MARK: - הצעת מחיר בסנדבוקס: יצירה → אימות → נתוני המרה → מחיקה

    func testQuoteLifecycleSandbox() async throws {
        let marker = "\(Self.testMarker) הצעה בעמ"
        let result = try await client.finalizeQuote(mode: "sandbox", data: [
            "customer_name": marker,
            "customer_id": "999999998",
            "manual_entry": true,
            "payment_terms_label": "שוטף + 30",
            "payment_terms_days": "30",
            "items": [[
                "description": "\(Self.testMarker) פריט הצעה",
                "sku": "TEST-SKU", "unit": "יחידה",
                "quantity": 1, "unit_price": 1, "line_total": 1,
                "generate_label": false,
            ]],
            "subtotal": 1, "vat": 0.17, "total": 1.17,
        ])
        XCTAssertFalse(result.first(of: ["quote_document_number", "quote_number"]).isEmpty,
                       "יצירת הצעה בסנדבוקס חייבת להחזיר מספר מסמך. תגובה: \(result.fields.keys.sorted())")

        // הרשומה בהיסטוריית ההצעות האמיתית, בסנדבוקס בלבד.
        let history = try await client.domainRows(.quoteHistory, forceRefresh: true)
        let created = try XCTUnwrap(history.first { $0["customer_name"].contains("נעלולי פלא") },
                                    "ההצעה לא נרשמה בהיסטוריה")
        XCTAssertTrue(["SB", "SANDBOX"].contains(created["mode"].uppercased()),
                      "ההצעה חייבת להיווצר בסנדבוקס בלבד! mode=\(created["mode"])")

        // נתוני ההמרה להזמנה זמינים.
        let orderData = try await client.quoteOrderData(historyID: created["history_id"])
        XCTAssertTrue(orderData["customer_name"].contains("נעלולי פלא"),
                      "נתוני ההמרה לא כוללים את הלקוח: \(orderData.fields.keys.sorted())")

        // ניקוי + אימות.
        try await client.postJSON("quote-history-delete", body: ["history_id": created["history_id"]])
        let after = try await client.domainRows(.quoteHistory, forceRefresh: true)
        XCTAssertNil(after.first { $0["history_id"] == created["history_id"] },
                     "הצעת הבדיקה לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - קבלה בסנדבוקס: חשבונית סנדבוקס אמיתית → קבלה → ניקוי בקסקדה

    func testReceiptForSandboxInvoice() async throws {
        // יוצרים הזמנה בסנדבוקס כדי לקבל חשבונית סנדבוקס אמיתית.
        let poMarker = "TEST-RCPT-\(Int(Date().timeIntervalSince1970))"
        let message = try await client.finalizeOrder(mode: "sandbox", data: [
            "customer_name": "\(Self.testMarker) בעמ",
            "customer_id": "999999998",
            "po_number": poMarker,
            "po_date": "01/01/2030",
            "manual_entry": true,
            "payment_terms_label": "שוטף + 30",
            "payment_terms_days": "30",
            "items": [[
                "description": "\(Self.testMarker) פריט קבלה",
                "sku": "TEST-SKU", "unit": "יחידה",
                "quantity": 1, "unit_price": 1, "line_total": 1,
                "generate_label": false,
            ]],
            "subtotal": 1, "vat": 0.17, "total": 1.17,
        ], skipWhatsapp: true)
        XCTAssertFalse(message.isEmpty)

        let history = try await client.domainRows(.orderHistory, forceRefresh: true)
        let created = try XCTUnwrap(history.first { $0["po_number"] == poMarker },
                                    "הזמנת הסנדבוקס לא נרשמה")
        let invoiceNumber = created["tax_invoice_number"]
        try XCTSkipIf(invoiceNumber.isEmpty,
                      "הסנדבוקס לא החזיר מספר חשבונית מס — אין על מה להפיק קבלה")

        // הפקת קבלה אמיתית בסנדבוקס על החשבונית שנוצרה הרגע.
        // GreenInvoice דוחה תאריכי תשלום עתידיים — חייבים תאריך אמיתי של היום.
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        let receiptMessage = try await client.createReceipt(
            mode: "sandbox", invoiceNumber: invoiceNumber, grossAmount: 1.17,
            paymentMethod: "bank_transfer", paymentDate: formatter.string(from: Date()),
            notes: Self.testMarker, withholdingApplied: false
        )
        XCTAssertFalse(receiptMessage.isEmpty, "הפקת הקבלה בסנדבוקס לא החזירה אישור")

        // ניקוי מפורש (הקסקדה מוחקת גם את שורת הגבייה); ה-tearDown מגבה בכל מקרה.
        try await client.postJSON("order-history-delete", body: [
            "history_id": created["history_id"],
            "po_number": poMarker,
            "mode": created["mode"],
        ])
        let after = try await client.domainRows(.orderHistory, forceRefresh: true)
        XCTAssertNil(after.first { $0["po_number"] == poMarker },
                     "הזמנת הקבלה לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - הזמנת רכש לספק בסנדבוקס: יצירה → אימות → מחיקה

    func testSupplierPOLifecycleSandbox() async throws {
        let supplierMarker = "\(Self.testMarker) ספק"
        try await client.createSupplierPO(
            mode: "sandbox",
            supplier: ["supplier_name": supplierMarker, "supplier_id": "999999998",
                       "supplier_email": "asafbeny@gmail.com", "supplier_phone": "0547720142"],
            items: [["description": "\(Self.testMarker) חומר גלם", "sku": "TEST-SKU",
                     "unit": "יח׳", "quantity": 1, "unit_price": 1, "line_total": 1]],
            remarks: Self.testMarker, subtotal: 1, vat: 0.17, total: 1.17
        )

        let rows = try await client.domainRows(.inventoryPurchaseOrders, forceRefresh: true)
        let created = try XCTUnwrap(rows.first { $0["supplier_name"].contains("נעלולי פלא") },
                                    "הזמנת הרכש לספק לא נרשמה")
        XCTAssertFalse(created["po_number"].isEmpty, "להזמנת ספק חייב להיות מספר")

        try await client.postJSON("inventory-purchase-orders-delete", body: [
            "history_id": created["history_id"],
        ])
        let after = try await client.domainRows(.inventoryPurchaseOrders, forceRefresh: true)
        XCTAssertNil(after.first { $0["history_id"] == created["history_id"] },
                     "הזמנת הספק לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - נעילה אופטימית מול השרת האמיתי: hash ישן נדחה, hash נכון עובר

    func testPaymentsOptimisticLockingLive() async throws {
        let marker = "\(Self.testMarker) נעילה \(Int(Date().timeIntervalSince1970))"
        try await client.postJSON("payments-transfer-row", body: [
            "row": [
                "customer_name": marker,
                "payment_direction": "תשלום",
                "amount": "1",
                "due_date": "01/01/2030",
                "notes": Self.testMarker,
                "paid": "FALSE",
            ],
        ])
        let rows = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        let created = try XCTUnwrap(rows.first { $0["customer_name"].lowercased().contains("נעילה") && $0["customer_name"].contains("נעלולי פלא") },
                                    "שורת הבדיקה לא נוצרה")
        XCTAssertFalse(created["_snapshot_hash"].isEmpty,
                       "השרת חייב להעשיר את שורות המובייל ב-_snapshot_hash — בלעדיו אין נעילה")

        // hash ישן → השרת חייב לדחות ב-409 בלי לגעת בשורה.
        do {
            try await client.postJSON("payments-transfer-paid", body: [
                "sheet_title": created["_sheet_title"],
                "row_number": Int(created["_sheet_row"]) ?? -1,
                "paid": true,
                "expected_snapshot_hash": "stale-hash",
                "session_id": AppConfig.sessionID,
            ])
            XCTFail("hash ישן חייב להידחות בשרת האמיתי")
        } catch {
            XCTAssertEqual((error as? APIError)?.statusCode, 409, "צפוי קונפליקט 409, התקבל: \(error)")
        }

        // hash נכון → עובר.
        try await client.postJSON("payments-transfer-paid", body: [
            "sheet_title": created["_sheet_title"],
            "row_number": Int(created["_sheet_row"]) ?? -1,
            "paid": true,
            "expected_snapshot_hash": created["_snapshot_hash"],
            "session_id": AppConfig.sessionID,
        ])

        // ניקוי.
        let after = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        if let row = after.first(where: { $0["customer_name"] == created["customer_name"] }) {
            try await client.postJSON("payments-transfer-delete-row", body: [
                "sheet_title": row["_sheet_title"],
                "row_number": Int(row["_sheet_row"]) ?? -1,
                "row": row.jsonObject,
                "expected_snapshot_hash": row["_snapshot_hash"],
                "session_id": AppConfig.sessionID,
            ])
        }
        let final = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertNil(final.first { $0["customer_name"] == created["customer_name"] },
                     "שורת הנעילה לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - חשבונית "טרם שולמה" → שורת לתשלום בשרת האמיתי

    func testUnpaidInvoiceCreatesPayableRowLive() async throws {
        let stamp = Int(Date().timeIntervalSince1970)
        let supplierMarker = "\(Self.testMarker) ספק חוב \(stamp)"
        let invoiceMarker = "TST-UNPAID-\(stamp)"

        try await client.saveInvoiceDraft(row: [
            "supplier_name": supplierMarker,
            "service_or_product": "\(Self.testMarker) בדיקת טרם שולמה",
            "total": "1.17", "subtotal": "1.00", "vat": "0.17",
            "invoice_date": "01/07/2026",
            "supplier_invoice_number": invoiceMarker,
            "create_payable_row": "TRUE",
        ])

        // שורת ה"לתשלום" נוצרה בגיליון האמיתי.
        let payments = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        // השרת שומר את מספר החשבונית ב-po_number של שורת התשלום.
        let payable = try XCTUnwrap(
            payments.first { $0["po_number"] == invoiceMarker },
            "החשבונית סומנה טרם שולמה אבל לא נוצרה שורת לתשלום"
        )
        XCTAssertEqual(payable["payment_direction"], "תשלום")
        XCTAssertFalse(payable.bool("paid"))

        // ניקוי: גם החשבונית וגם שורת התשלומים.
        let invoices = try await client.domainRows(.financeInvoices, forceRefresh: true)
        if let invoice = invoices.first(where: { $0["supplier_name"].contains("נעלולי פלא") }) {
            try? await client.postJSON("finance-invoices-delete", body: ["row_id": invoice["row_id"]])
        }
        try await client.postJSON("payments-transfer-delete-row", body: [
            "sheet_title": payable["_sheet_title"],
            "row_number": Int(payable["_sheet_row"]) ?? -1,
            "row": payable.jsonObject,
            "expected_snapshot_hash": payable["_snapshot_hash"],
            "session_id": AppConfig.sessionID,
        ])
        let after = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertNil(after.first { $0["po_number"] == invoiceMarker },
                     "שורת הלתשלום של הבדיקה לא נמחקה — נשאר זבל בדאטה!")
    }

    // MARK: - מנהל עבודה: שמירה → אימות → מחיקה

    func testWorkManagerLifecycle() async throws {
        let marker = "\(Self.testMarker) מנהל עבודה"
        try await client.postJSON("marketing-work-managers-save", body: [
            "row": ["full_name": marker, "company_name": "\(Self.testMarker) בניה",
                    "phone_1": "0547720142"],
        ])
        let rows = try await client.domainRows(.marketingWorkManagers, forceRefresh: true)
        let created = try XCTUnwrap(rows.first { $0["full_name"].contains("נעלולי פלא") },
                                    "מנהל העבודה לא נשמר בשרת")
        XCTAssertFalse(created["row_id"].isEmpty)

        try await client.postJSON("marketing-work-managers-delete", body: ["row_id": created["row_id"]])
        let after = try await client.domainRows(.marketingWorkManagers, forceRefresh: true)
        XCTAssertNil(after.first { $0["row_id"] == created["row_id"] },
                     "מנהל העבודה לא נמחק — נשאר זבל בדאטה!")
    }
}
