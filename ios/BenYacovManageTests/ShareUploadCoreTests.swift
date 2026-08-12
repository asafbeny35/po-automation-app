import XCTest
@testable import BenYacovManage

/// טסטים לליבת ההעלאה של ה-Share Extension — בניית בקשות, זרימות ושגיאות.
final class ShareUploadCoreTests: XCTestCase {
    private let baseURL = URL(string: "https://mock.share")!

    /// שולח מזויף שמקליט בקשות ומחזיר תגובות מוכנות לפי נתיב.
    private final class FakeSender: @unchecked Sendable {
        var requests: [URLRequest] = []
        var responses: [String: (Int, [String: Any])] = [:]

        func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
            requests.append(request)
            let path = request.url!.lastPathComponent
            let (status, body) = responses[path] ?? (404, ["error": "אין תגובה מוכנה ל-\(path)"])
            let data = try JSONSerialization.data(withJSONObject: body)
            let response = HTTPURLResponse(url: request.url!, statusCode: status,
                                           httpVersion: nil, headerFields: nil)!
            return (data, response)
        }
    }

    // MARK: - הזמנת רכש

    func testOrderUploadPostsMultipartToWorkingOrders() async throws {
        let sender = FakeSender()
        sender.responses["working-orders-upload"] = (200, ["status": "ok"])

        let message = try await ShareUploadCore.upload(
            kind: .order, fileData: Data("pdf".utf8), filename: "po.pdf", mimeType: "application/pdf",
            baseURL: baseURL, cookieHeader: "po_session=abc", send: sender.send
        )
        XCTAssertTrue(message.contains("הזמנות בעבודה"), "הודעה: \(message)")

        let request = try XCTUnwrap(sender.requests.first)
        XCTAssertEqual(request.url?.lastPathComponent, "working-orders-upload")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Cookie"), "po_session=abc")
        let body = String(decoding: request.httpBody ?? Data(), as: UTF8.self)
        XCTAssertTrue(body.contains("name=\"file\"; filename=\"po.pdf\""), "גוף הבקשה לא תקין")
        XCTAssertTrue(body.contains("name=\"requires_installation\""))
    }

    func testOrderRequiresInstallationSendsFlag() async throws {
        let sender = FakeSender()
        sender.responses["working-orders-upload"] = (200, ["status": "ok"])
        let message = try await ShareUploadCore.upload(
            kind: .order, fileData: Data("pdf".utf8), filename: "po.pdf", mimeType: "application/pdf",
            requiresInstallation: true,
            baseURL: baseURL, cookieHeader: "c=1", send: sender.send
        )
        XCTAssertTrue(message.contains("התקנה"), "הודעה: \(message)")
        let body = String(decoding: sender.requests[0].httpBody ?? Data(), as: UTF8.self)
        XCTAssertTrue(body.contains("name=\"requires_installation\"\r\n\r\ntrue"),
                      "דגל ההתקנה לא נשלח")
    }

    // MARK: - חשבונית: העלאה → טיוטות → שמירה

    func testInvoiceUploadSavesAllDrafts() async throws {
        let sender = FakeSender()
        sender.responses["finance-invoices-upload"] = (200, ["drafts": [
            ["supplier_name": "ספק א", "amount": "100"],
            ["supplier_name": "ספק ב", "amount": "200"],
        ]])
        sender.responses["finance-invoices-save"] = (200, ["status": "ok"])

        let message = try await ShareUploadCore.upload(
            kind: .invoice, fileData: Data("pdf".utf8), filename: "invoice.pdf", mimeType: "application/pdf",
            baseURL: baseURL, cookieHeader: "po_session=abc", send: sender.send
        )
        XCTAssertTrue(message.contains("כספים"), "הודעה: \(message)")
        XCTAssertTrue(message.contains("ספק א") && message.contains("ספק ב"))

        // בקשה אחת להעלאה + שמירה לכל טיוטה.
        XCTAssertEqual(sender.requests.count, 3)
        XCTAssertEqual(sender.requests[0].url?.lastPathComponent, "finance-invoices-upload")
        XCTAssertEqual(sender.requests[1].url?.lastPathComponent, "finance-invoices-save")
        let saveBody = try JSONSerialization.jsonObject(with: sender.requests[1].httpBody!) as? [String: Any]
        let row = saveBody?["row"] as? [String: Any]
        XCTAssertEqual(row?["supplier_name"] as? String, "ספק א")
    }

    func testInvoiceMarkUnpaidSendsPayableFlag() async throws {
        let sender = FakeSender()
        sender.responses["finance-invoices-upload"] = (200, ["drafts": [
            ["supplier_name": "ספק א", "total": "1170.00", "reference_number": "INV-555"],
        ]])
        sender.responses["finance-invoices-save"] = (200, ["status": "ok"])

        let message = try await ShareUploadCore.upload(
            kind: .invoice, fileData: Data("pdf".utf8), filename: "invoice.pdf", mimeType: "application/pdf",
            markUnpaid: true,
            baseURL: baseURL, cookieHeader: "po_session=abc", send: sender.send
        )
        XCTAssertTrue(message.contains("לתשלום"), "הודעה: \(message)")

        let saveBody = try JSONSerialization.jsonObject(with: sender.requests[1].httpBody!) as? [String: Any]
        let row = saveBody?["row"] as? [String: Any]
        XCTAssertEqual(row?["create_payable_row"] as? String, "TRUE")
        // ה-endpoint קורא supplier_invoice_number מהשורה — חייב להיות מושלם מ-reference_number.
        XCTAssertEqual(row?["supplier_invoice_number"] as? String, "INV-555")
    }

    func testInvoiceWithoutUnpaidDoesNotSendFlag() async throws {
        let sender = FakeSender()
        sender.responses["finance-invoices-upload"] = (200, ["drafts": [["supplier_name": "ספק א"]]])
        sender.responses["finance-invoices-save"] = (200, ["status": "ok"])
        _ = try await ShareUploadCore.upload(
            kind: .invoice, fileData: Data("pdf".utf8), filename: "invoice.pdf", mimeType: "application/pdf",
            baseURL: baseURL, cookieHeader: "po_session=abc", send: sender.send
        )
        let saveBody = try JSONSerialization.jsonObject(with: sender.requests[1].httpBody!) as? [String: Any]
        let row = saveBody?["row"] as? [String: Any]
        XCTAssertNil(row?["create_payable_row"], "בלי הטוגל אסור לשלוח את הדגל")
    }

    func testInvoiceUploadWithoutDraftsFails() async {
        let sender = FakeSender()
        sender.responses["finance-invoices-upload"] = (200, ["drafts": [] as [[String: Any]]])
        do {
            _ = try await ShareUploadCore.upload(
                kind: .invoice, fileData: Data("x".utf8), filename: "a.pdf", mimeType: "application/pdf",
                baseURL: baseURL, cookieHeader: "c=1", send: sender.send
            )
            XCTFail("צפויה שגיאה כשאין טיוטות")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("פרסור"), "\(error.localizedDescription)")
        }
    }

    // MARK: - שגיאות session

    func testMissingCookieFailsBeforeNetwork() async {
        let sender = FakeSender()
        do {
            _ = try await ShareUploadCore.upload(
                kind: .order, fileData: Data("x".utf8), filename: "a.pdf", mimeType: "application/pdf",
                baseURL: baseURL, cookieHeader: "", send: sender.send
            )
            XCTFail("צפויה שגיאת התחברות")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("התחבר"), "\(error.localizedDescription)")
            XCTAssertTrue(sender.requests.isEmpty, "אסור לפנות לרשת בלי עוגייה")
        }
    }

    func testExpiredSessionShowsHebrewMessage() async {
        let sender = FakeSender()
        sender.responses["working-orders-upload"] = (401, ["error": "auth required"])
        do {
            _ = try await ShareUploadCore.upload(
                kind: .order, fileData: Data("x".utf8), filename: "a.pdf", mimeType: "application/pdf",
                baseURL: baseURL, cookieHeader: "c=1", send: sender.send
            )
            XCTFail("צפויה שגיאת פקיעת התחברות")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("ההתחברות פגה"), "\(error.localizedDescription)")
        }
    }

    func testServerErrorMessagePropagates() async {
        let sender = FakeSender()
        sender.responses["working-orders-upload"] = (400, ["error": "קובץ לא נתמך."])
        do {
            _ = try await ShareUploadCore.upload(
                kind: .order, fileData: Data("x".utf8), filename: "a.pdf", mimeType: "application/pdf",
                baseURL: baseURL, cookieHeader: "c=1", send: sender.send
            )
            XCTFail("צפויה שגיאת שרת")
        } catch {
            XCTAssertEqual(error.localizedDescription, "קובץ לא נתמך.")
        }
    }

    // MARK: - שיתוף session דרך App Group

    func testSessionSyncRoundTrip() {
        // האחסון המשותף הוא Keychain (קבוצת PRY2S55YGY.* מהפרופיל הקיים) עם נפילה חיננית בטסטים.
        let url = URL(string: "https://poautomationapp.vercel.app")!
        ShareUploadCore.syncSessionToAppGroup(baseURL: url)
        XCTAssertEqual(ShareUploadCore.sharedBaseURL(), url)

        ShareUploadCore.clearSharedSession()
        XCTAssertEqual(ShareUploadCore.sharedCookieHeader(), "")
    }

    // MARK: - שיתוף → אישור מסירה

    func testFetchOpenConfirmationsFiltersSentRows() async throws {
        let sender = FakeSender()
        sender.responses["delivery_confirmations"] = (200, ["rows": [
            ["fulfillment_id": "f1", "po_number": "111", "company": "לקוח פתוח",
             "tax_invoice_number": "550001", "source_mode": "PROD", "sent": "FALSE", "target_email": "a@b.co"],
            ["fulfillment_id": "f2", "po_number": "222", "company": "לקוח שנשלח",
             "sent": "TRUE"],
            ["fulfillment_id": "f3", "po_number": "333", "company": "לקוח בלי דגל"],
        ]])
        let targets = try await ShareUploadCore.fetchOpenDeliveryConfirmations(
            baseURL: baseURL, cookieHeader: "c=1", send: sender.send
        )
        XCTAssertEqual(targets.map(\.poNumber), ["111", "333"], "רק רשומות שטרם נשלחו")
        XCTAssertEqual(targets[0].displayTitle, "לקוח פתוח")
        XCTAssertTrue(targets[0].displaySubtitle.contains("550001"))
    }

    func testFetchOpenConfirmationsRequiresSession() async {
        let sender = FakeSender()
        do {
            _ = try await ShareUploadCore.fetchOpenDeliveryConfirmations(
                baseURL: baseURL, cookieHeader: "", send: sender.send
            )
            XCTFail("בלי עוגייה — חסום לפני רשת")
        } catch {
            XCTAssertTrue(sender.requests.isEmpty)
        }
    }

    func testUploadSignedDeliverySendsQueryAndFile() async throws {
        let sender = FakeSender()
        sender.responses["delivery-confirmations-upload"] = (200, ["status": "ok"])
        let target = ShareUploadCore.DeliveryTarget(
            fulfillmentID: "f9", poNumber: "999", taxInvoiceNumber: "550009",
            sourceMode: "PROD", company: "לקוח", targetEmail: "x@y.co"
        )
        try await ShareUploadCore.uploadSignedDelivery(
            to: target, fileData: Data("img".utf8), filename: "signed.jpg", mimeType: "image/jpeg",
            baseURL: baseURL, cookieHeader: "c=1", send: sender.send
        )
        let url = try XCTUnwrap(sender.requests.first?.url?.absoluteString)
        XCTAssertTrue(url.contains("fulfillment_id=f9") && url.contains("po_number=999"),
                      "פרמטרי הזיהוי חייבים לעבור ב-query: \(url)")
        let body = String(decoding: sender.requests[0].httpBody ?? Data(), as: UTF8.self)
        XCTAssertTrue(body.contains("filename=\"signed.jpg\""))
    }

    func testSendConfirmationUsesCanonicalDefaults() async throws {
        let sender = FakeSender()
        sender.responses["delivery-confirmations-send"] = (200, ["status": "ok", "message": "נשלח."])
        let target = ShareUploadCore.DeliveryTarget(
            fulfillmentID: "f9", poNumber: "999", taxInvoiceNumber: "550009",
            sourceMode: "PROD", company: "לקוח", targetEmail: "x@y.co"
        )
        _ = try await ShareUploadCore.sendDeliveryConfirmation(
            for: target, baseURL: baseURL, cookieHeader: "c=1", send: sender.send
        )
        let body = try JSONSerialization.jsonObject(with: sender.requests[0].httpBody!) as? [String: Any]
        XCTAssertEqual(body?["subject"] as? String, "", "נושא ריק ⇒ הנוסח הקנוני של השרת")
        XCTAssertEqual(body?["recipients"] as? String, "", "נמענים ריקים ⇒ target_email של הרשומה")
        XCTAssertEqual(body?["test_send"] as? Bool, false, "שליחה אמיתית ללקוח, לא בדיקה")
    }

    func testUploadWithoutSendMakesNoSendRequest() async throws {
        // הזרימה שביקש אסף: העלאה בלבד — שום בקשת שליחה לא יוצאת מעצמה.
        let sender = FakeSender()
        sender.responses["delivery-confirmations-upload"] = (200, ["status": "ok"])
        let target = ShareUploadCore.DeliveryTarget(
            fulfillmentID: "f1", poNumber: "111", taxInvoiceNumber: "",
            sourceMode: "PROD", company: "", targetEmail: ""
        )
        try await ShareUploadCore.uploadSignedDelivery(
            to: target, fileData: Data("x".utf8), filename: "a.jpg", mimeType: "image/jpeg",
            baseURL: baseURL, cookieHeader: "c=1", send: sender.send
        )
        XCTAssertEqual(sender.requests.count, 1)
        XCTAssertFalse(sender.requests.contains { $0.url!.path.contains("send") },
                       "העלאה בלי שליחה — אסור שתצא בקשת send")
    }
}
