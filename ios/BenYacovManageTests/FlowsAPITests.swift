import XCTest
@testable import BenYacovManage

/// טסטים לזרימות העסקיות המלאות — הזמנת רכש, חשבוניות, אישורי מסירה,
/// התקנות, מסמכים ושיוך תחום.
final class FlowsAPITests: XCTestCase {
    private var client: APIClient!

    override func setUp() {
        super.setUp()
        client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
    }

    // MARK: - הזמנת רכש

    func testProcessPurchaseOrderParsesPDF() async throws {
        let record = try await client.processPurchaseOrder(
            pdf: Data("fake-pdf".utf8), filename: "po.pdf", mode: "sandbox"
        )
        XCTAssertFalse(record["customer_name"].isEmpty)
        XCTAssertFalse(record["po_number"].isEmpty)
        XCTAssertNotNil(record.number("total"))
        if case .array(let items)? = record.fields["items"] {
            XCTAssertFalse(items.isEmpty, "צפויים פריטים בהזמנה המפורסרת")
        } else {
            XCTFail("חסר מערך פריטים")
        }
    }

    func testFinalizeCreatesOrderHistoryRow() async throws {
        let before = try await client.domainRows(.orderHistory)
        let message = try await client.finalizeOrder(
            mode: "sandbox",
            data: ["customer_name": "לקוח פיינלייז", "po_number": "PO-TEST-1"],
            skipWhatsapp: true
        )
        XCTAssertTrue(message.contains("בלי שליחת וואטסאפ"), "הודעה: \(message)")
        let after = try await client.domainRows(.orderHistory)
        XCTAssertEqual(after.count, before.count + 1)
        let created = try XCTUnwrap(after.first { $0["customer_name"] == "לקוח פיינלייז" })
        XCTAssertEqual(created["mode"], "SANDBOX")
    }

    func testFinalizeWithWhatsappMentionsSending() async throws {
        let message = try await client.finalizeOrder(
            mode: "prod",
            data: ["customer_name": "לקוח וואטסאפ"],
            skipWhatsapp: false
        )
        XCTAssertTrue(message.contains("וואטסאפ"), "הודעה: \(message)")
        let rows = try await client.domainRows(.orderHistory)
        XCTAssertEqual(rows.first { $0["customer_name"] == "לקוח וואטסאפ" }?["mode"], "PROD")
    }

    // MARK: - חשבוניות

    func testInvoiceUploadReturnsDrafts() async throws {
        let drafts = try await client.uploadInvoices(files: [("inv.pdf", Data("fake".utf8))])
        XCTAssertFalse(drafts.isEmpty)
        XCTAssertFalse(drafts[0]["supplier_name"].isEmpty)
        XCTAssertNotNil(drafts[0].number("total"))
    }

    func testInvoiceSaveAppearsInFinanceDomain() async throws {
        let before = try await client.domainRows(.financeInvoices)
        let drafts = try await client.uploadInvoices(files: [("inv.pdf", Data("fake".utf8))])
        var row = drafts[0].jsonObject
        row["supplier_name"] = "ספק שנשמר מהמובייל"
        try await client.saveInvoiceDraft(row: row)
        let after = try await client.domainRows(.financeInvoices)
        XCTAssertEqual(after.count, before.count + 1)
        XCTAssertNotNil(after.first { $0["supplier_name"] == "ספק שנשמר מהמובייל" })
    }

    // MARK: - אישורי מסירה

    func testDeliverySendTestMode() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        let message = try await client.sendDeliveryConfirmation(
            record: rows[0], subject: "בדיקה", message: "הודעה", recipients: "", testSend: true
        )
        XCTAssertTrue(message.contains("בדיקה"), "הודעה: \(message)")
    }

    func testDeliverySendRealMode() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        let message = try await client.sendDeliveryConfirmation(
            record: rows[0], subject: "אישור", message: "הודעה", recipients: "a@b.com", testSend: false
        )
        XCTAssertTrue(message.contains("נשלח"), "הודעה: \(message)")
    }

    // MARK: - מחיקה מדורגת: היסטוריה ⇄ תשלומים ⇄ אישורי מסירה

    func testDeletingOrderHistoryCascadesToPaymentsAndConfirmations() async throws {
        // בונים שלישייה מקושרת לפי מס' הזמנה.
        let po = "CASC-\(Int(Date().timeIntervalSince1970))"
        _ = try await client.finalizeOrder(
            mode: "sandbox",
            data: ["customer_name": "לקוח קסקדה", "po_number": po],
            skipWhatsapp: true
        )
        try await client.postJSON("payments-transfer-row", body: [
            "row": ["customer_name": "לקוח קסקדה", "po_number": po,
                    "payment_direction": "גביה", "amount": "10", "paid": "FALSE"],
        ])
        let history = try await client.domainRows(.orderHistory)
        let created = try XCTUnwrap(history.first { $0["po_number"] == po })

        // מחיקת ההיסטוריה מוחקת גם את שורת התשלומים.
        try await client.postJSON("order-history-delete", body: [
            "history_id": created["history_id"],
            "po_number": po,
        ])
        let payments = try await client.domainRows(.paymentsTransfer)
        XCTAssertNil(payments.first { $0["po_number"] == po },
                     "שורת התשלומים חייבת להימחק יחד עם ההזמנה")
    }

    func testDeletingPaymentRowCascadesToHistoryAndConfirmations() async throws {
        let po = "CASC2-\(Int(Date().timeIntervalSince1970))"
        _ = try await client.finalizeOrder(
            mode: "sandbox",
            data: ["customer_name": "לקוח קסקדה ב", "po_number": po],
            skipWhatsapp: true
        )
        try await client.postJSON("payments-transfer-row", body: [
            "row": ["customer_name": "לקוח קסקדה ב", "po_number": po,
                    "payment_direction": "גביה", "amount": "10", "paid": "FALSE"],
        ])
        let payments = try await client.domainRows(.paymentsTransfer)
        let paymentRow = try XCTUnwrap(payments.first { $0["po_number"] == po })

        // מחיקת שורת התשלומים מוחקת גם את רשומת ההיסטוריה.
        try await client.postJSON("payments-transfer-delete-row", body: [
            "sheet_title": paymentRow["_sheet_title"],
            "row_number": Int(paymentRow["_sheet_row"]) ?? -1,
            "row": paymentRow.jsonObject,
            "expected_snapshot_hash": paymentRow["_snapshot_hash"],
        ])
        let history = try await client.domainRows(.orderHistory)
        XCTAssertNil(history.first { $0["po_number"] == po },
                     "רשומת ההיסטוריה חייבת להימחק יחד עם שורת התשלומים")
    }

    // MARK: - העלאת תעודה חתומה

    func testSignedDeliveryUploadSetsFileFields() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        let target = try XCTUnwrap(
            rows.first { $0.first(of: ["signed_delivery_drive_file_id", "signed_delivery_name"]).isEmpty },
            "צריך שורה בלי תעודה חתומה בנתוני הבדיקה"
        )
        try await client.uploadSignedDelivery(
            record: target, fileData: Data("%PDF-1.4 signed".utf8),
            filename: "signed.pdf", mimeType: "application/pdf"
        )
        let after = try await client.domainRows(.deliveryConfirmations)
        let updated = try XCTUnwrap(after.first { $0.id == target.id })
        XCTAssertFalse(updated["signed_delivery_drive_file_id"].isEmpty,
                       "ההעלאה לא שייכה קובץ לשורה")
    }

    func testSignedDeliveryDeleteClearsFileFields() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        let target = try XCTUnwrap(
            rows.first { !$0["signed_delivery_drive_file_id"].isEmpty || !$0["signed_delivery_name"].isEmpty }
        )
        try await client.deleteSignedDelivery(record: target)
        let after = try await client.domainRows(.deliveryConfirmations)
        let updated = try XCTUnwrap(after.first { $0.id == target.id })
        XCTAssertTrue(updated["signed_delivery_drive_file_id"].isEmpty)
        XCTAssertTrue(updated["signed_delivery_name"].isEmpty)
    }

    func testSignedDeliveryUploadWithoutFileRejected() async throws {
        let rows = try await client.domainRows(.deliveryConfirmations)
        do {
            try await client.postMultipart("delivery-confirmations-upload", query: [
                "po_number": rows[0]["po_number"],
            ])
            XCTFail("העלאה בלי קובץ הייתה אמורה להידחות")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 400)
        }
    }

    func testSignedDeliveryUploadWithoutIdentifiersRejected() async throws {
        do {
            try await client.postMultipart(
                "delivery-confirmations-upload",
                files: [.init(field: "file", filename: "a.pdf", mimeType: "application/pdf", data: Data("x".utf8))]
            )
            XCTFail("העלאה בלי מזהים הייתה אמורה להידחות")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 400)
        }
    }

    // MARK: - התקנות

    func testInstallationDomainsLoad() async throws {
        let cases = try await client.domainRows(.installationCases)
        XCTAssertFalse(cases.isEmpty, "חסרים תיקי התקנה ב-fixture")
        XCTAssertFalse(cases[0]["installation_id"].isEmpty)
        let visits = try await client.domainRows(.installationVisits)
        XCTAssertFalse(visits.isEmpty, "חסרים ביקורים ב-fixture")
    }

    func testInstallationCaseStatusUpdate() async throws {
        let cases = try await client.domainRows(.installationCases)
        let target = cases[0]
        try await client.updateInstallationCase(
            installationID: target["installation_id"], status: "תואם",
            delayReason: "ביקור המשך", nextVisitDate: "2026-07-10", notes: "הערת בדיקה"
        )
        let after = try await client.domainRows(.installationCases)
        let updated = try XCTUnwrap(after.first { $0["installation_id"] == target["installation_id"] })
        XCTAssertEqual(updated["status"], "תואם")
        XCTAssertEqual(updated["delay_reason"], "ביקור המשך")
        XCTAssertEqual(updated["notes"], "הערת בדיקה")
    }

    func testInstallationVisitSaveAndDelete() async throws {
        let cases = try await client.domainRows(.installationCases)
        let target = cases[0]
        let beforeVisits = try await client.domainRows(.installationVisits)

        try await client.saveInstallationVisit(
            installationID: target["installation_id"], visitDate: "2026-07-05",
            installedItems: [["item_key": "k1", "quantity": 3]], notes: "ביקור בדיקה"
        )
        let afterSave = try await client.domainRows(.installationVisits)
        XCTAssertEqual(afterSave.count, beforeVisits.count + 1)
        let created = try XCTUnwrap(afterSave.first { $0["notes"] == "ביקור בדיקה" })
        XCTAssertEqual(created["installed_total_quantity"], "3")

        // מונה הביקורים בתיק עלה.
        let casesAfter = try await client.domainRows(.installationCases)
        let updatedCase = try XCTUnwrap(casesAfter.first { $0["installation_id"] == target["installation_id"] })
        XCTAssertEqual(Int(updatedCase["visit_count"]), Int(target["visit_count"]).map { $0 + 1 })

        try await client.deleteInstallationVisit(visitID: created["visit_id"])
        let afterDelete = try await client.domainRows(.installationVisits)
        XCTAssertEqual(afterDelete.count, beforeVisits.count)
    }

    func testInstallationStatusOptionsMatchServer() {
        XCTAssertEqual(APIClient.installationStatusOptions,
                       ["ממתין לתיאום", "תואם", "הותקן חלקית", "הושלם", "מושהה", "בוטל"])
    }

    // MARK: - שיוך תחום

    func testAssignCustomerDomain() async throws {
        let customers = try await client.domainRows(.customers)
        let target = customers[0]
        try await client.assignCustomerDomain(record: target, domainKey: "construction")
        let after = try await client.domainRows(.customers)
        let updated = try XCTUnwrap(after.first { $0["customer_guid"] == target["customer_guid"] })
        XCTAssertEqual(updated["customer_domain"], "construction")
    }

    func testCustomerDomainCatalog() {
        XCTAssertEqual(APIClient.customerDomains.map(\.key),
                       ["construction", "textile", "supplier", "graphic_web"])
    }

    // MARK: - מסמכים

    func testMarketingDocsLoad() async throws {
        let docs = try await client.marketingDocs()
        XCTAssertFalse(docs.isEmpty)
        XCTAssertFalse(docs[0].label.isEmpty)
    }

    func testMarketingDocPreviewBytesArePNG() async throws {
        let data = try await client.fetchDocumentData("marketing-doc-preview/brochure-hebrew")
        XCTAssertGreaterThan(data.count, 8)
        XCTAssertEqual(data.prefix(4), Data([0x89, 0x50, 0x4E, 0x47]), "צפוי PNG")
    }

    func testFinanceInvoiceFileBytesArePDF() async throws {
        let rows = try await client.domainRows(.financeInvoices)
        let data = try await client.fetchDocumentData("finance-invoices-file/\(rows[0]["row_id"])")
        XCTAssertEqual(String(data: data.prefix(4), encoding: .ascii), "%PDF")
    }

    func testAdminDocSendEmail() async throws {
        let message = try await client.sendAdminDocEmail(
            assetKey: "business-dealer", recipients: "", subject: "בדיקה", body: "תוכן", testSend: true
        )
        XCTAssertTrue(message.contains("נשלח"), "הודעה: \(message)")
    }
}
