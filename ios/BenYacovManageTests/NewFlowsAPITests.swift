import XCTest
@testable import BenYacovManage

/// טסטים לזרימות שנוספו בסבב השלמת הפיצ'רים: הצעות מחיר, קבלות,
/// הזמנות רכש לספק, מדבקות, טפסי שיווק/ניכויים ווואטסאפ מנהלה.
final class NewFlowsAPITests: XCTestCase {
    private var client: APIClient!

    override func setUp() {
        super.setUp()
        client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
    }

    // MARK: - הלוואות, משכנתאות וצי רכבים

    func testAdminLendingParsesLoansVehiclesAndTotals() async throws {
        let lending = try await client.adminLending()

        XCTAssertEqual(lending.loans.count, 3)
        XCTAssertEqual(lending.vehicles.count, 2)
        XCTAssertTrue(lending.loansTotal.contains("410,059.43"))
        XCTAssertTrue(lending.mortgagesTotal.contains("629,029.10"))

        let firstLoan = try XCTUnwrap(lending.loans.first)
        XCTAssertEqual(firstLoan.title, "הלוואה 400,000")
        XCTAssertEqual(firstLoan.group, "loan")
        XCTAssertEqual(firstLoan.facts.first?.label, "סה״כ יתרה")
        XCTAssertTrue(firstLoan.facts.first?.value.contains("382,559.42") == true)
        XCTAssertEqual(firstLoan.docs.map(\.key),
                       ["loan-discount-400-summary", "loan-discount-400-amortization"])
        XCTAssertFalse(firstLoan.details.isEmpty)

        let mortgages = lending.loans.filter { $0.group == "mortgage" }
        XCTAssertEqual(mortgages.count, 1)
        XCTAssertTrue(mortgages[0].title.contains("משכנתא"))

        let vehicle = try XCTUnwrap(lending.vehicles.first)
        XCTAssertEqual(vehicle.name, "קיה נירו אפורה")
        XCTAssertEqual(vehicle.plate, "13578301")
        XCTAssertTrue(vehicle.imagePath.hasPrefix("static/admin/vehicles/"))
        XCTAssertEqual(vehicle.docs.first?.key, "vehicle-grey-niro-license")
    }

    func testAdminDriveFileServesBinary() async throws {
        let data = try await client.fetchDocumentData("admin-drive-file/loan-discount-400-summary")
        XCTAssertFalse(data.isEmpty)
    }

    // MARK: - הצעות מחיר

    func testFinalizeQuoteCreatesHistoryRow() async throws {
        let before = try await client.domainRows(.quoteHistory)
        let result = try await client.finalizeQuote(mode: "sandbox", data: [
            "customer_name": "לקוח הצעה",
            "manual_entry": true,
            "items": [["description": "וילון", "quantity": 2, "unit_price": 100, "line_total": 200]],
            "subtotal": 200, "vat": 34, "total": 234,
        ])
        XCTAssertFalse(result.first(of: ["quote_document_number", "quote_number"]).isEmpty)
        let after = try await client.domainRows(.quoteHistory)
        XCTAssertEqual(after.count, before.count + 1)
        XCTAssertNotNil(after.first { $0["customer_name"] == "לקוח הצעה" })
    }

    func testSendQuoteEmailPostsMultipartFields() async throws {
        let rows = try await client.domainRows(.quoteHistory)
        let historyID = try XCTUnwrap(rows.first?["history_id"])
        let message = try await client.sendQuoteEmail(historyID: historyID, recipients: "asafbeny@gmail.com")
        XCTAssertFalse(message.isEmpty)
    }

    func testSendQuoteWhatsappSucceeds() async throws {
        try await client.sendQuoteWhatsapp(phone: "0547720142", message: "הצעה לבדיקה", quoteFile: "")
    }

    func testQuoteOrderDataReturnsConversionFields() async throws {
        let rows = try await client.domainRows(.quoteHistory)
        let historyID = try XCTUnwrap(rows.first?["history_id"])
        let data = try await client.quoteOrderData(historyID: historyID)
        XCTAssertFalse(data["customer_name"].isEmpty, "נתוני המרה צריכים לכלול שם לקוח")
    }

    func testResolveQuoteURLReturnsLink() async throws {
        let rows = try await client.domainRows(.quoteHistory)
        let historyID = try XCTUnwrap(rows.first?["history_id"])
        let url = try await client.resolveQuoteURL(historyID: historyID)
        XCTAssertTrue(url.contains("http"), "צפוי קישור, התקבל: \(url)")
    }

    func testUploadSignedQuoteAcceptsFile() async throws {
        let rows = try await client.domainRows(.quoteHistory)
        let historyID = try XCTUnwrap(rows.first?["history_id"])
        try await client.uploadSignedQuote(
            historyID: historyID,
            fileData: Data("signed".utf8),
            filename: "signed.pdf",
            mimeType: "application/pdf"
        )
    }

    // MARK: - קבלות

    func testCreateReceiptReturnsMessage() async throws {
        let message = try await client.createReceipt(
            mode: "sandbox", invoiceNumber: "20233", grossAmount: 1170,
            paymentMethod: "bank_transfer", paymentDate: "2026-07-05", notes: "בדיקה",
            withholdingApplied: false
        )
        XCTAssertFalse(message.isEmpty)
    }

    func testCreateReceiptWithWithholdingComputesThreePercent() async throws {
        // ה-mock דוחה פירוק לא עקבי — הצלחה כאן מוכיחה שהחישוב זהה לדסקטופ.
        let message = try await client.createReceipt(
            mode: "sandbox", invoiceNumber: "20233", grossAmount: 9062.40,
            paymentMethod: "bank_transfer", paymentDate: "2026-07-06", notes: "",
            withholdingApplied: true
        )
        XCTAssertFalse(message.isEmpty)
    }

    func testWithholdingBreakdownMatchesDesktopFormula() {
        let breakdown = APIClient.withholdingBreakdown(gross: 9062.40)
        XCTAssertEqual(breakdown.withheld, 271.87, accuracy: 0.001, "3% מ-9,062.40 בעיגול לאגורה")
        XCTAssertEqual(breakdown.paid, 8790.53, accuracy: 0.001)
        XCTAssertEqual(breakdown.withheld + breakdown.paid, 9062.40, accuracy: 0.001, "הפירוק חייב להסתכם לסכום המלא")
    }

    func testCreateReceiptRejectsMissingInvoice() async {
        do {
            _ = try await client.createReceipt(
                mode: "sandbox", invoiceNumber: "", grossAmount: 100,
                paymentMethod: "cash", paymentDate: "2026-07-05", notes: "",
                withholdingApplied: false
            )
            XCTFail("צפויה שגיאה על חשבונית חסרה")
        } catch { /* צפוי */ }
    }

    func testCreateReceiptRejectsZeroAmount() async {
        do {
            _ = try await client.createReceipt(
                mode: "sandbox", invoiceNumber: "20233", grossAmount: 0,
                paymentMethod: "cash", paymentDate: "2026-07-05", notes: "",
                withholdingApplied: false
            )
            XCTFail("צפויה שגיאה על סכום אפס")
        } catch { /* צפוי */ }
    }

    func testReceiptPaymentMethodsMatchDesktop() {
        let keys = APIClient.receiptPaymentMethods.map(\.key)
        XCTAssertEqual(Set(keys), ["bank_transfer", "check", "cash", "payment_app"])
    }

    // MARK: - הזמנת רכש לספק

    func testCreateSupplierPOInsertsRow() async throws {
        let before = try await client.domainRows(.inventoryPurchaseOrders)
        try await client.createSupplierPO(
            mode: "sandbox",
            supplier: ["supplier_name": "ספק בדיקה", "supplier_email": "asafbeny@gmail.com",
                       "supplier_phone": "0547720142", "supplier_id": ""],
            items: [["description": "בד", "quantity": 5, "unit_price": 40, "line_total": 200]],
            remarks: "בדיקה", subtotal: 200, vat: 34, total: 234
        )
        let after = try await client.domainRows(.inventoryPurchaseOrders)
        XCTAssertEqual(after.count, before.count + 1)
        XCTAssertNotNil(after.first { $0["supplier_name"] == "ספק בדיקה" })
    }

    func testCreateSupplierPORejectsMissingSupplier() async {
        do {
            try await client.createSupplierPO(
                mode: "sandbox", supplier: [:],
                items: [["description": "בד", "quantity": 1, "unit_price": 10]],
                remarks: "", subtotal: 10, vat: 1.7, total: 11.7
            )
            XCTFail("צפויה שגיאה על ספק חסר")
        } catch { /* צפוי */ }
    }

    func testSendSupplierPOEmailAndWhatsapp() async throws {
        let rows = try await client.domainRows(.inventoryPurchaseOrders)
        let historyID = try XCTUnwrap(rows.first?.first(of: ["history_id", "row_id"]))
        let message = try await client.sendSupplierPOEmail(historyID: historyID, recipients: "asafbeny@gmail.com")
        XCTAssertFalse(message.isEmpty)
        try await client.sendSupplierPOWhatsapp(historyID: historyID, phone: "0547720142", message: "הזמנה לבדיקה")
    }

    // MARK: - מדבקות

    func testLabelsOnlyReturnsMessage() async throws {
        let message = try await client.createLabelsOnly(labels: [[
            "customer": "לקוח מדבקות", "address": "רחוב 1", "contact_name": "אסף",
            "phone": "0547720142", "label_count": 2,
        ]])
        XCTAssertFalse(message.isEmpty)
    }

    func testLabelsOnlyRejectsEmptyList() async {
        do {
            _ = try await client.createLabelsOnly(labels: [])
            XCTFail("צפויה שגיאה על רשימה ריקה")
        } catch { /* צפוי */ }
    }

    // MARK: - עזרי קומפוזר ומנהלה

    func testRecentManualCustomersReturnsRows() async throws {
        let customers = try await client.recentManualCustomers()
        XCTAssertFalse(customers.isEmpty)
        XCTAssertFalse(customers[0]["customer_name"].isEmpty)
    }

    func testSendAdminDocWhatsappReturnsMessage() async throws {
        let message = try await client.sendAdminDocWhatsapp(
            assetKey: "business-dealer", phone: "0547720142", message: "מסמך לבדיקה"
        )
        XCTAssertFalse(message.isEmpty)
    }

    // MARK: - טפסי שמירה חדשים (שיווק + ניכויים)

    func testWorkManagerSaveRequiresFullName() async {
        do {
            try await client.postJSON("marketing-work-managers-save", body: ["row": ["company_name": "חברה בלי שם"]])
            XCTFail("צפויה שגיאה על שם מלא חסר")
        } catch { /* צפוי */ }
    }

    func testWorkManagerSaveUpserts() async throws {
        let before = try await client.domainRows(.marketingWorkManagers)
        try await client.postJSON("marketing-work-managers-save", body: [
            "row": ["full_name": "מנהל עבודה בדיקה", "phone_1": "0547720142"],
        ])
        let after = try await client.domainRows(.marketingWorkManagers, forceRefresh: true)
        XCTAssertEqual(after.count, before.count + 1)
    }

    func testConstructionCompanySaveRequiresCompanyName() async {
        do {
            try await client.postJSON("marketing-construction-companies-save", body: ["row": ["phone": "03-0000000"]])
            XCTFail("צפויה שגיאה על שם חברה חסר")
        } catch { /* צפוי */ }
    }

    func testWithholdingSaveRequiresReceiptAndInvoice() async {
        do {
            try await client.postJSON("finance-customer-withholdings-save", body: [
                "row": ["customer_name": "לקוח ניכוי", "invoice_number": "1"],
            ])
            XCTFail("צפויה שגיאה על מספר קבלה חסר")
        } catch { /* צפוי */ }
    }

    func testWithholdingSaveUpserts() async throws {
        try await client.postJSON("finance-customer-withholdings-save", body: [
            "row": ["customer_name": "לקוח ניכוי", "invoice_number": "20233",
                    "receipt_number": "555", "gross_amount": "1170"],
        ])
        let rows = try await client.domainRows(.financeCustomerWithholdings, forceRefresh: true)
        XCTAssertNotNil(rows.first { $0["customer_name"] == "לקוח ניכוי" })
    }

    // MARK: - ריכוז חשבוניות לרו"ח

    func testAccountantSummaryRequiresDueDates() async {
        do {
            _ = try await client.sendAccountantSummary(
                reportDueDates: [], recipients: "", includePDF: true, includeXLSX: false,
                includeZip: false, includeVatSummary: false, testSend: true
            )
            XCTFail("צפויה שגיאה בלי מועדי דיווח")
        } catch { /* צפוי */ }
    }

    func testAccountantSummaryRequiresRecipientsWhenNotTest() async {
        do {
            _ = try await client.sendAccountantSummary(
                reportDueDates: ["15/07/2026"], recipients: "", includePDF: true, includeXLSX: false,
                includeZip: false, includeVatSummary: true, testSend: false
            )
            XCTFail("שליחה אמיתית בלי נמענים חייבת להיחסם")
        } catch { /* צפוי */ }
    }

    func testAccountantSummaryTestSendSucceeds() async throws {
        let message = try await client.sendAccountantSummary(
            reportDueDates: ["15/07/2026"], recipients: "", includePDF: true, includeXLSX: true,
            includeZip: false, includeVatSummary: true, testSend: true
        )
        XCTAssertFalse(message.isEmpty)
    }

    // MARK: - חשבונית "טרם שולמה" → שורת לתשלום

    func testUnpaidInvoiceSaveCreatesPayableRow() async throws {
        let before = try await client.domainRows(.paymentsTransfer)
        try await client.saveInvoiceDraft(row: [
            "supplier_name": "ספק טרם שולם", "service_or_product": "בדים",
            "total": "2340.00", "supplier_invoice_number": "INV-999",
            "create_payable_row": "TRUE",
        ])
        let after = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertEqual(after.count, before.count + 1, "חשבונית טרם שולמה חייבת להוסיף שורת לתשלום")
        let created = try XCTUnwrap(after.first { $0["customer_name"] == "ספק טרם שולם" })
        XCTAssertEqual(created["payment_direction"], "תשלום")
        XCTAssertFalse(created.bool("paid"))
        // כמו בשרת: מספר החשבונית יושב ב-po_number של שורת התשלום.
        XCTAssertEqual(created["po_number"], "INV-999")
    }

    func testInvoiceSaveWithoutFlagDoesNotTouchPayments() async throws {
        let before = try await client.domainRows(.paymentsTransfer)
        try await client.saveInvoiceDraft(row: [
            "supplier_name": "ספק רגיל", "service_or_product": "בדים", "total": "100",
        ])
        let after = try await client.domainRows(.paymentsTransfer, forceRefresh: true)
        XCTAssertEqual(after.count, before.count)
    }

    // MARK: - סוגי לקוחות ומיון (שיקוף הדסקטופ)

    func testCustomerDomainNormalizationMatchesDesktop() {
        XCTAssertEqual(CustomerDomains.normalized("Construction"), "construction")
        XCTAssertEqual(CustomerDomains.normalized(" textile "), "textile")
        XCTAssertEqual(CustomerDomains.normalized("משהו לא מוכר"), "", "ערך לא מוכר ⇒ ללא שיוך")
        XCTAssertEqual(CustomerDomains.label(for: "graphic_web"), "עיצוב גרפי ואינטרנט")
        XCTAssertEqual(CustomerDomains.label(for: ""), "ללא שיוך")
    }

    func testCustomerSortingIsHebrewAlphabetical() {
        let rows = ["תמר בעמ", "אלף בנייה", "מרכז הבד"].map {
            DomainRecord(fields: ["customer_name": .string($0)])
        }
        let sorted = CustomerDomains.sorted(rows).map { $0["customer_name"] }
        XCTAssertEqual(sorted, ["אלף בנייה", "מרכז הבד", "תמר בעמ"])
    }

    // MARK: - נעילה אופטימית בתשלומים

    func testPaymentsMutationRequiresSnapshotHash() async {
        do {
            try await client.postJSON("payments-transfer-paid", body: [
                "sheet_title": "תשלומים והעברות 2026", "row_number": 179, "paid": true,
            ])
            XCTFail("מוטציה בלי hash חייבת להיחסם")
        } catch { /* צפוי */ }
    }

    func testPaymentsMutationWithCorrectHashSucceeds() async throws {
        let rows = try await client.domainRows(.paymentsTransfer)
        let row = try XCTUnwrap(rows.first { !$0["_snapshot_hash"].isEmpty })
        try await client.postJSON("payments-transfer-paid", body: [
            "sheet_title": row["_sheet_title"],
            "row_number": Int(row["_sheet_row"]) ?? -1,
            "paid": !row.bool("paid"),
            "expected_snapshot_hash": row["_snapshot_hash"],
            "session_id": AppConfig.sessionID,
        ])
    }

    func testPaymentsMutationWithStaleHashConflicts() async throws {
        let rows = try await client.domainRows(.paymentsTransfer)
        let row = try XCTUnwrap(rows.first)
        do {
            try await client.postJSON("payments-transfer-paid", body: [
                "sheet_title": row["_sheet_title"],
                "row_number": Int(row["_sheet_row"]) ?? -1,
                "paid": true,
                "expected_snapshot_hash": "stale-hash-from-yesterday",
                "session_id": AppConfig.sessionID,
            ])
            XCTFail("hash ישן חייב להחזיר קונפליקט")
        } catch {
            XCTAssertEqual((error as? APIError)?.statusCode, 409, "\(error)")
        }
    }

    // MARK: - קבלה בצ'ק ובאפליקציית תשלום

    func testReceiptCheckRequiresAllFourFields() async {
        do {
            _ = try await client.createReceipt(
                mode: "sandbox", invoiceNumber: "20233", grossAmount: 100,
                paymentMethod: "check", paymentDate: "2026-07-06", notes: "",
                withholdingApplied: false,
                checkDetails: .init(checkNumber: "123", bankNumber: "20", branchNumber: "", accountNumber: "")
            )
            XCTFail("פרטי צ'ק חלקיים חייבים להיחסם")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("צ'ק") || error.localizedDescription.contains("צ׳ק"),
                          "\(error.localizedDescription)")
        }
    }

    func testReceiptCheckWithFullDetailsSucceeds() async throws {
        let message = try await client.createReceipt(
            mode: "sandbox", invoiceNumber: "20233", grossAmount: 500,
            paymentMethod: "check", paymentDate: "2026-07-06", notes: "",
            withholdingApplied: false,
            checkDetails: .init(checkNumber: "1234", bankNumber: "20", branchNumber: "577", accountNumber: "226943")
        )
        XCTAssertFalse(message.isEmpty)
    }

    func testReceiptPaymentAppSendsProvider() async throws {
        let message = try await client.createReceipt(
            mode: "sandbox", invoiceNumber: "20233", grossAmount: 250,
            paymentMethod: "payment_app", paymentDate: "2026-07-06", notes: "",
            withholdingApplied: false, paymentAppProvider: "paybox"
        )
        XCTAssertFalse(message.isEmpty)
    }

    // MARK: - תלוש בוואטסאפ — השרת מחייב טלפון

    func testPayrollWhatsappRequiresPhone() async {
        do {
            try await client.postJSON("hr-payroll-send-whatsapp", body: ["row_id": "some-row"])
            XCTFail("צפויה שגיאה על טלפון חסר — כמו בשרת האמיתי")
        } catch { /* צפוי */ }
    }

    func testPayrollWhatsappSucceedsWithPhone() async throws {
        try await client.postJSON("hr-payroll-send-whatsapp", body: [
            "row_id": "some-row", "phone": "0547720142",
        ])
    }

    // MARK: - watch חי לחשבוניות ספק

    func testFinanceInvoicesEpochChangesAfterSave() async throws {
        let first = try await client.getJSON("finance-invoices-epoch")
        let firstObject = try XCTUnwrap(try JSONSerialization.jsonObject(with: first) as? [String: Any])
        let firstCount = firstObject["count"] as? Int ?? -1

        try await client.postJSON("finance-invoices-save", body: [
            "row": ["supplier_name": "ספק epoch", "invoice_number": "88888", "amount": "100"],
        ])

        let second = try await client.getJSON("finance-invoices-epoch")
        let secondObject = try XCTUnwrap(try JSONSerialization.jsonObject(with: second) as? [String: Any])
        XCTAssertEqual(secondObject["count"] as? Int, firstCount + 1,
                       "שמירת חשבונית חייבת לשנות את ה-epoch — זה מה שמניע את העדכון החי")
    }

    // MARK: - מחיקת תעודת משלוח ספק

    func testSupplierDeliveryNoteDeleteRemovesRow() async throws {
        let before = try await client.domainRows(.supplierDeliveryNotes)
        let target = try XCTUnwrap(before.first)
        try await client.postJSON("supplier-delivery-notes-delete-row", body: [
            "record_id": target.first(of: ["record_id", "row_id"]),
        ])
        let after = try await client.domainRows(.supplierDeliveryNotes, forceRefresh: true)
        XCTAssertEqual(after.count, before.count - 1)
    }
}
