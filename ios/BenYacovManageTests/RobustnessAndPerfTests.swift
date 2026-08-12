import XCTest
@testable import BenYacovManage

/// עמידות, קצוות דאטה וביצועים — הקטגוריות שסוויטות הפיצ'רים לא מכסות.
final class RobustnessAndPerfTests: XCTestCase {

    /// שכבת תעבורה שמחזירה בתים שרירותיים — לבדיקת עמידות המפענחים.
    private struct StubTransport: Transport {
        let data: Data
        let statusCode: Int

        func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
            (data, HTTPURLResponse(url: request.url!, statusCode: statusCode,
                                   httpVersion: nil, headerFields: nil)!)
        }
    }

    private struct FailingTransport: Transport {
        func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
            throw URLError(.notConnectedToInternet)
        }
    }

    // MARK: - עמידות לתגובות שרת פגומות

    func testGarbageJSONThrowsCleanlyInsteadOfCrashing() async {
        let client = APIClient(
            baseURL: URL(string: "https://stub.test")!,
            transport: StubTransport(data: Data("not-json{{{broken".utf8), statusCode: 200)
        )
        do {
            _ = try await client.domainRows(.customers)
            XCTFail("JSON שבור חייב לזרוק שגיאה")
        } catch {
            // העיקר: שגיאה מסודרת, לא קריסה.
        }
    }

    func testTruncatedJSONThrowsCleanly() async {
        let client = APIClient(
            baseURL: URL(string: "https://stub.test")!,
            transport: StubTransport(data: Data(#"{"status":"ok","rows":[{"customer_na"#.utf8), statusCode: 200)
        )
        do {
            _ = try await client.domainRows(.customers)
            XCTFail("JSON קטוע חייב לזרוק שגיאה")
        } catch { /* צפוי */ }
    }

    func testWrongShapeJSONYieldsEmptyOrThrows() async {
        // מערך במקום אובייקט — לא אמור לקרוס.
        let client = APIClient(
            baseURL: URL(string: "https://stub.test")!,
            transport: StubTransport(data: Data(#"[1,2,3]"#.utf8), statusCode: 200)
        )
        _ = try? await client.domainRows(.customers)
    }

    @MainActor
    func testOfflineErrorShowsFriendlyHebrewMessage() async {
        let session = SessionStore(api: APIClient(
            baseURL: URL(string: "https://stub.test")!,
            transport: FailingTransport()
        ))
        let succeeded = await session.perform("לא אמור להצליח", refreshing: []) {
            try await session.api.postJSON("some-action", body: [:])
        }
        XCTAssertFalse(succeeded)
        let toast = session.toast?.text ?? ""
        XCTAssertTrue(toast.contains("אין חיבור לשרת"), "הודעת אופליין לא ידידותית: \(toast)")
    }

    // MARK: - קצוות דאטה

    func testExtremeFieldValuesDoNotBreakRecord() {
        let longName = String(repeating: "שם ארוך מאוד ", count: 50)
        let record = DomainRecord(fields: [
            "customer_name": .string("לקוח 🎉 עם \"מרכאות\" ו'גרשים' <script>"),
            "notes": .string(longName),
            "amount": .string("₪-1,234.56"),
        ])
        XCTAssertTrue(record["customer_name"].contains("🎉"))
        // הרשומה חותכת רווחים בקצוות (התנהגות רצויה) — משווים אחרי חיתוך.
        XCTAssertEqual(record["notes"], longName.trimmingCharacters(in: .whitespaces))
        XCTAssertEqual(record.number("amount"), -1234.56, "סכום שלילי חייב להיפרסר")
    }

    func testInvalidSheetDatesAreHandledSanely() {
        XCTAssertNil(PaymentsMath.parseSheetDate("31/02/2026"), "תאריך לא קיים")
        XCTAssertNil(PaymentsMath.parseSheetDate("abc"))
        XCTAssertNil(PaymentsMath.parseSheetDate(""))
        XCTAssertNotNil(PaymentsMath.parseSheetDate("27/03/2026"), "תאריך סביב מעבר שעון קיץ")

        // שורה עם תאריך זבל: לא קורסת, נחשבת פתוחה (אין "מועד חלף" בלי תאריך תקין).
        let row = DomainRecord(fields: ["paid": .string("FALSE"), "due_date": .string("99/99/9999")])
        XCTAssertEqual(PaymentsMath.status(of: row), .open)
    }

    func testCategorizeSurvivesGarbageRows() {
        let rows = [
            DomainRecord(fields: [:]),
            DomainRecord(fields: ["_sheet_title": .string("בלי שנה בכלל")]),
            DomainRecord(fields: ["_sheet_title": .string("תשלומים 2026"), "amount": .string("לא מספר")]),
        ]
        let buckets = PaymentsMath.categorize(rows)
        // שורות בלי שנת גיליון תקינה מסוננות; העיקר — בלי קריסה.
        XCTAssertEqual(buckets.collection.count + buckets.payment.count, 1)
    }

    // MARK: - ביצועים על דאטה בגודל אמיתי ומעבר לו

    private func makeSyntheticRows(_ count: Int) -> [DomainRecord] {
        (0..<count).map { index in
            DomainRecord(fields: [
                "customer_name": .string("לקוח ביצועים \(index)"),
                "payment_direction": .string(index % 3 == 0 ? "תשלום" : "גביה"),
                "amount": .string("₪\(100 + index).50"),
                "due_date": .string("0\(1 + index % 9)/0\(1 + index % 9)/2026"),
                "invoice_date": .string("01/01/2026"),
                "paid": .string(index % 5 == 0 ? "TRUE" : "FALSE"),
                "_sheet_title": .string("תשלומים והעברות 2026"),
                "_sheet_row": .string("\(index)"),
            ])
        }
    }

    func testCategorizeTenThousandRowsIsFast() {
        let rows = makeSyntheticRows(10_000)
        let start = Date()
        let buckets = PaymentsMath.categorize(rows)
        let elapsed = Date().timeIntervalSince(start)
        XCTAssertEqual(buckets.collection.count + buckets.payment.count, 10_000)
        XCTAssertLessThan(elapsed, 2.0, "סיווג 10,000 שורות לקח \(elapsed) שניות — איטי מדי")

        measure {
            _ = PaymentsMath.categorize(rows)
        }
    }

    func testDecodeFiveThousandRowsIsFast() throws {
        let rows = (0..<5_000).map { index in
            #"{"customer_name":"לקוח \#(index)","amount":"\#(index).00","po_number":"PO-\#(index)","notes":"הערה עם טקסט ארוך יחסית כדי לדמות דאטה אמיתי"}"#
        }
        let json = Data(#"{"status":"ok","rows":["#.utf8) + Data(rows.joined(separator: ",").utf8) + Data("]}".utf8)

        let start = Date()
        let decoded = try DomainRecord.records(fromRowsJSON: json)
        let elapsed = Date().timeIntervalSince(start)
        XCTAssertEqual(decoded.count, 5_000)
        XCTAssertLessThan(elapsed, 2.0, "פענוח 5,000 שורות לקח \(elapsed) שניות")
    }

    func testOpenTotalOnHugeDatasetMatchesManualSum() {
        let rows = makeSyntheticRows(2_000)
        let expected = rows.filter { !$0.bool("paid") }.compactMap { $0.number("amount") }.reduce(0, +)
        XCTAssertEqual(PaymentsMath.openTotal(rows), expected, accuracy: 0.01)
    }
}
