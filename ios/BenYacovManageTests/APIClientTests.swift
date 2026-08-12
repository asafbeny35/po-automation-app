import XCTest
@testable import BenYacovManage

/// טסטים ללקוח ה-API מול השרת המדומה — התחברות, טעינת כל הדומיינים, ופעולות מוטציה.
final class APIClientTests: XCTestCase {
    private var client: APIClient!

    override func setUp() {
        super.setUp()
        client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: false)
        )
    }

    // MARK: - התחברות

    func testAuthBootstrapDecodes() async throws {
        let bootstrap = try await client.authBootstrap()
        XCTAssertFalse(bootstrap.authenticated)
        XCTAssertEqual(bootstrap.selectedUserID, "asaf")
        XCTAssertEqual(bootstrap.authUsers.count, 2)
        let asaf = try XCTUnwrap(bootstrap.authUsers.first { $0.id == "asaf" })
        XCTAssertTrue(asaf.methods.totp)
        XCTAssertTrue(asaf.methods.email)
        XCTAssertFalse(asaf.setupRequired)
    }

    func testTOTPWrongCodeThrowsHebrewError() async {
        do {
            try await client.verifyTOTP(userID: "asaf", code: "000000", rememberMe: true)
            XCTFail("קוד שגוי היה אמור להיכשל")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 400)
            XCTAssertTrue(error.message.contains("קוד"), "הודעה: \(error.message)")
        } catch {
            XCTFail("סוג שגיאה לא צפוי: \(error)")
        }
    }

    func testTOTPCorrectCodeAuthenticates() async throws {
        try await client.verifyTOTP(userID: "asaf", code: MockTransport.validTOTPCode, rememberMe: true)
        let bootstrap = try await client.authBootstrap()
        XCTAssertTrue(bootstrap.authenticated)
    }

    func testEmailCodeFlow() async throws {
        let message = try await client.sendEmailCode(userID: "asaf", rememberMe: false)
        XCTAssertTrue(message.contains("נשלח"), "הודעה: \(message)")
        try await client.verifyEmailCode(code: MockTransport.validEmailCode)
        let bootstrap = try await client.authBootstrap()
        XCTAssertTrue(bootstrap.authenticated)
    }

    func testEmailWrongCodeFails() async throws {
        _ = try await client.sendEmailCode(userID: "asaf", rememberMe: false)
        do {
            try await client.verifyEmailCode(code: "111111")
            XCTFail("קוד מייל שגוי היה אמור להיכשל")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 400)
        }
    }

    func testLogout() async throws {
        try await client.verifyTOTP(userID: "asaf", code: MockTransport.validTOTPCode, rememberMe: true)
        try await client.logout()
        let bootstrap = try await client.authBootstrap()
        XCTAssertFalse(bootstrap.authenticated)
    }

    // MARK: - תקציר

    func testBootstrapHasAllSections() async throws {
        let snapshot = try await client.bootstrap()
        XCTAssertEqual(snapshot.sections.count, Domain.allCases.count)
        for domain in Domain.allCases {
            XCTAssertTrue(
                snapshot.sections.contains { $0.id == domain.bootstrapSectionID },
                "חסר מקטע לדומיין \(domain.rawValue)"
            )
        }
    }

    // MARK: - כל הדומיינים נטענים

    func testEveryDomainLoadsWithRows() async throws {
        for domain in Domain.allCases {
            let records = try await client.domainRows(domain)
            XCTAssertFalse(records.isEmpty, "דומיין \(domain.rawValue) ריק — חסר fixture")
            // לכל רשומה יש כותרת לתצוגה.
            let first = records[0]
            XCTAssertFalse(
                first.first(of: domain.spec.titleKeys).isEmpty,
                "דומיין \(domain.rawValue): לרשומה הראשונה אין כותרת (מפתחות: \(domain.spec.titleKeys))"
            )
        }
    }

    func testUnknownDomainReturns404() async {
        do {
            _ = try await client.getJSON("mobile/domains/not_a_domain")
            XCTFail("דומיין לא קיים אמור להחזיר 404")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 404)
        } catch {
            XCTFail("סוג שגיאה לא צפוי: \(error)")
        }
    }

    // MARK: - פעולות מוטציה

    func testMarkPaidTogglesRow() async throws {
        let before = try await client.domainRows(.paymentsTransfer)
        let target = try XCTUnwrap(before.first { !$0.bool("paid") })
        let sheetRow = target["_sheet_row"]

        try await client.postJSON("payments-transfer-paid", body: [
            "sheet_title": target["_sheet_title"],
            "row_number": Int(sheetRow) ?? -1,
            "paid": true,
            "expected_snapshot_hash": target["_snapshot_hash"],
        ])

        let after = try await client.domainRows(.paymentsTransfer)
        let updated = try XCTUnwrap(after.first { $0["_sheet_row"] == sheetRow })
        XCTAssertTrue(updated.bool("paid"), "השורה הייתה אמורה להיות מסומנת כשולמה")
    }

    func testCompleteReminder() async throws {
        let before = try await client.domainRows(.marketingReminders)
        let open = try XCTUnwrap(before.first { $0["status"].lowercased() != "completed" })

        try await client.postJSON("marketing-complete-reminder", body: [
            "reminder_id": open["reminder_id"],
        ])

        let after = try await client.domainRows(.marketingReminders)
        let updated = try XCTUnwrap(after.first { $0["reminder_id"] == open["reminder_id"] })
        XCTAssertEqual(updated["status"], "completed")
    }

    func testCustomerLifecycle() async throws {
        // יצירה
        try await client.postJSON("customers-create", body: [
            "customer": ["customer_name": "לקוח בדיקה בעמ", "customer_id": "999999999"],
        ])
        var customers = try await client.domainRows(.customers)
        let created = try XCTUnwrap(customers.first { $0["customer_name"] == "לקוח בדיקה בעמ" })

        // עדכון
        var updatedFields = created.jsonObject
        updatedFields["city"] = "חיפה"
        try await client.postJSON("customers-update", body: ["customer": updatedFields])
        customers = try await client.domainRows(.customers)
        XCTAssertEqual(
            customers.first { $0["customer_guid"] == created["customer_guid"] }?["city"], "חיפה"
        )

        // השבתה — עובר ללא פעילים
        try await client.postJSON("customers-set-active", body: [
            "active": false, "rows": [updatedFields],
        ])
        customers = try await client.domainRows(.customers)
        XCTAssertNil(customers.first { $0["customer_guid"] == created["customer_guid"] })
        var inactive = try await client.domainRows(.inactiveCustomers)
        XCTAssertNotNil(inactive.first { $0["customer_guid"] == created["customer_guid"] })

        // מחיקה סופית
        try await client.postJSON("customers-delete", body: ["customer": updatedFields])
        inactive = try await client.domainRows(.inactiveCustomers)
        XCTAssertNil(inactive.first { $0["customer_guid"] == created["customer_guid"] })
    }

    func testDeleteOrderHistoryRow() async throws {
        let before = try await client.domainRows(.orderHistory)
        let target = before[0]
        try await client.postJSON("order-history-delete", body: [
            "history_id": target["history_id"],
        ])
        let after = try await client.domainRows(.orderHistory)
        XCTAssertEqual(after.count, before.count - 1)
        XCTAssertNil(after.first { $0["history_id"] == target["history_id"] })
    }

    func testDeleteQuoteHistoryRow() async throws {
        let before = try await client.domainRows(.quoteHistory)
        try await client.postJSON("quote-history-delete", body: [
            "history_id": before[0]["history_id"],
        ])
        let after = try await client.domainRows(.quoteHistory)
        XCTAssertEqual(after.count, before.count - 1)
    }

    func testWorkingOrderNoteSaveAndDelete() async throws {
        let before = try await client.domainRows(.workingOrders)
        let target = before[0]

        // השרת (וה-mock) מקבלים את ההערה רק כ-multipart form.
        try await client.postMultipart("working-orders-note-save", fields: [
            "row_id": target["row_id"], "note_text": "הערת בדיקה",
        ])
        let afterNote = try await client.domainRows(.workingOrders)
        XCTAssertEqual(afterNote.first { $0["row_id"] == target["row_id"] }?["order_note_text"], "הערת בדיקה")

        try await client.postJSON("working-orders-delete", body: ["row_id": target["row_id"]])
        let afterDelete = try await client.domainRows(.workingOrders)
        XCTAssertNil(afterDelete.first { $0["row_id"] == target["row_id"] })
    }

    func testPaymentRowAddUpdateDelete() async throws {
        let before = try await client.domainRows(.paymentsTransfer)

        try await client.postJSON("payments-transfer-row", body: [
            "row": ["customer_name": "ספק בדיקה", "amount": "100", "payment_direction": "תשלום", "paid": "FALSE"],
        ])
        var rows = try await client.domainRows(.paymentsTransfer)
        XCTAssertEqual(rows.count, before.count + 1)
        let added = try XCTUnwrap(rows.first { $0["customer_name"] == "ספק בדיקה" })

        try await client.postJSON("payments-transfer-update-row", body: [
            "sheet_title": added["_sheet_title"],
            "row_number": Int(added["_sheet_row"]) ?? -1,
            "row": ["amount": "250"],
            "expected_snapshot_hash": added["_snapshot_hash"],
        ])
        rows = try await client.domainRows(.paymentsTransfer)
        XCTAssertEqual(rows.first { $0["customer_name"] == "ספק בדיקה" }?["amount"], "250")

        // אחרי העדכון ה-hash השתנה — חייבים לשלוף מחדש (זה בדיוק החוזה).
        let refreshed = try XCTUnwrap(rows.first { $0["customer_name"] == "ספק בדיקה" })
        try await client.postJSON("payments-transfer-delete-row", body: [
            "sheet_title": refreshed["_sheet_title"],
            "row_number": Int(refreshed["_sheet_row"]) ?? -1,
            "row": refreshed.jsonObject,
            "expected_snapshot_hash": refreshed["_snapshot_hash"],
        ])
        rows = try await client.domainRows(.paymentsTransfer)
        XCTAssertNil(rows.first { $0["customer_name"] == "ספק בדיקה" })
    }

    func testHREmployeeSaveCreatesAndUpdates() async throws {
        let before = try await client.domainRows(.hrEmployees)

        try await client.postJSON("hr-employee-save", body: [
            "row": ["full_name": "עובד בדיקה", "employment_type": "hourly"],
        ])
        var rows = try await client.domainRows(.hrEmployees)
        XCTAssertEqual(rows.count, before.count + 1)
        let created = try XCTUnwrap(rows.first { $0["full_name"] == "עובד בדיקה" })

        var updated = created.jsonObject
        updated["hourly_rate"] = "62"
        try await client.postJSON("hr-employee-save", body: ["row": updated])
        rows = try await client.domainRows(.hrEmployees)
        XCTAssertEqual(rows.count, before.count + 1, "עדכון לא אמור להוסיף שורה")
        XCTAssertEqual(rows.first { $0["employee_id"] == created["employee_id"] }?["hourly_rate"], "62")
    }

    func testFinanceInvoiceDelete() async throws {
        let before = try await client.domainRows(.financeInvoices)
        try await client.postJSON("finance-invoices-delete", body: ["row_id": before[0]["row_id"]])
        let after = try await client.domainRows(.financeInvoices)
        XCTAssertEqual(after.count, before.count - 1)
    }

    func testFailOnceDomainRecoversOnRetry() async throws {
        // סימולציה של תקלת רשת חד-פעמית דרך משתנה סביבה לא זמינה כאן,
        // לכן בודקים ישירות מול MockTransport עם ההגדרה.
        setenv("BY_UITEST_FAIL_ONCE", "customers", 1)
        defer { unsetenv("BY_UITEST_FAIL_ONCE") }
        let failingClient = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        do {
            _ = try await failingClient.domainRows(.customers)
            XCTFail("הטעינה הראשונה הייתה אמורה להיכשל")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 500)
            XCTAssertTrue(error.message.contains("לא הצלחתי"), "הודעה: \(error.message)")
        }
        let recovered = try await failingClient.domainRows(.customers)
        XCTAssertFalse(recovered.isEmpty, "אחרי retry הדומיין אמור להיטען")
    }
}
