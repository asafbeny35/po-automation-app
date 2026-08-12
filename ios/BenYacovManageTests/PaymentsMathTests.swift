import XCTest
@testable import BenYacovManage

/// טסטים לחישובי ריבועי הבית — שיקוף מדויק של סינון הדסקטופ.
final class PaymentsMathTests: XCTestCase {

    private func row(_ fields: [String: String]) -> DomainRecord {
        DomainRecord(fields: fields.mapValues { .string($0) })
    }

    // MARK: - כלי עזר

    func testSheetYearExtraction() {
        XCTAssertEqual(PaymentsMath.sheetYear("תשלומים והעברות 2026"), 2026)
        XCTAssertEqual(PaymentsMath.sheetYear("תשלומים והעברות 2024"), 2024)
        XCTAssertNil(PaymentsMath.sheetYear("גיליון בלי שנה"))
    }

    func testParseSheetDate() {
        XCTAssertNotNil(PaymentsMath.parseSheetDate("01/08/2026"))
        XCTAssertNil(PaymentsMath.parseSheetDate(""))
        XCTAssertNil(PaymentsMath.parseSheetDate("2026-08-01"))
    }

    // MARK: - סיווג

    func testDirectionSplitsPaymentVersusCollection() {
        let rows = [
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "תשלום",
                 "amount": "100", "invoice_date": "01/06/2026"]),
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "200", "invoice_date": "01/06/2026"]),
            // כיוון ריק נחשב גבייה — כמו בדסקטופ.
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "",
                 "amount": "300", "invoice_date": "01/06/2026"]),
        ]
        let result = PaymentsMath.categorize(rows)
        XCTAssertEqual(result.payment.count, 1)
        XCTAssertEqual(result.collection.count, 2)
    }

    func testOldSheetYearIsExcluded() {
        let rows = [
            row(["_sheet_title": "תשלומים והעברות 2024", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "99999", "invoice_date": "01/04/2024"]),
        ]
        let result = PaymentsMath.categorize(rows)
        XCTAssertTrue(result.collection.isEmpty)
        XCTAssertTrue(result.payment.isEmpty)
    }

    func testOldInvoiceDateIsExcluded() {
        let rows = [
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "88888", "invoice_date": "15/06/2024"]),
        ]
        XCTAssertTrue(PaymentsMath.categorize(rows).collection.isEmpty)
    }

    func testPaidRowFromCurrentSeasonIsCategorizedButNotSummed() {
        let rows = [
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "TRUE", "payment_direction": "גביה",
                 "amount": "50000", "invoice_date": "01/02/2026"]),
        ]
        let result = PaymentsMath.categorize(rows)
        XCTAssertEqual(result.collection.count, 1, "שורה ששולמה בעונה הנוכחית נשארת ברשימה")
        XCTAssertEqual(PaymentsMath.openTotal(result.collection), 0, "אבל לא נספרת בסכום הפתוח")
    }

    func testUnpaidRowWithoutDatesIsIncluded() {
        let rows = [
            row(["_sheet_title": "תשלומים והעברות 2025", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "500"]),
        ]
        XCTAssertEqual(PaymentsMath.categorize(rows).collection.count, 1)
    }

    /// הדרישה המרכזית: "לגבייה" כולל גם שורות שמועד הגבייה שלהן חלף.
    func testOpenTotalIncludesOverdueRows() {
        let rows = [
            // פתוחה עתידית.
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "100", "invoice_date": "01/06/2026", "due_date": "01/12/2026"]),
            // פתוחה שמועדה חלף — חייבת להיכלל.
            row(["_sheet_title": "תשלומים והעברות 2026", "paid": "FALSE", "payment_direction": "גביה",
                 "amount": "250", "invoice_date": "01/02/2026", "due_date": "01/03/2026"]),
        ]
        let collection = PaymentsMath.categorize(rows).collection
        XCTAssertEqual(collection.count, 2)
        XCTAssertEqual(PaymentsMath.openTotal(collection), 350,
                       "שורה שמועדה חלף חייבת להיכלל בסכום לגבייה")
        XCTAssertEqual(PaymentsMath.overdueTotal(collection), 250,
                       "פירוט 'מועד הגבייה חלף' חייב לסכום רק את הפיגורים")
    }

    func testOverdueTotalIgnoresPaidAndFutureRows() {
        let rows = [
            row(["paid": "TRUE", "amount": "999", "due_date": "01/01/2026"]),
            row(["paid": "FALSE", "amount": "50", "due_date": "01/01/2030"]),
            row(["paid": "FALSE", "amount": "70"]),
        ]
        XCTAssertEqual(PaymentsMath.overdueTotal(rows), 0)
    }

    func testOpenTotalParsesCurrencyStrings() {
        let rows = [
            row(["paid": "FALSE", "amount": "₪7,009.00"]),
            row(["paid": "FALSE", "amount": "2,331.68"]),
            row(["paid": "TRUE", "amount": "₪50,000.00"]),
        ]
        XCTAssertEqual(PaymentsMath.openTotal(rows), 9340.68, accuracy: 0.01)
    }

    // MARK: - הסכומים מול נתוני הבדיקה המלאים (כמו שמוצג בריבועי הבית)

    func testHomeTileAmountsFromFixtures() async throws {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        let rows = try await client.domainRows(.paymentsTransfer)
        // ה-fixture כולל שורות מלכודת: שולם (50,000), גיליון 2024 (99,999), חשבונית 2024 (88,888),
        // ושורת פיגור (1,111) שחייבת להיכלל.
        XCTAssertEqual(rows.count, 10)

        let categories = PaymentsMath.categorize(rows)
        let collect = PaymentsMath.openTotal(categories.collection)
        let pay = PaymentsMath.openTotal(categories.payment)

        XCTAssertEqual(collect, 25452.04, accuracy: 0.01,
                       "לגבייה = שורות גבייה פתוחות ותקפות, כולל מועד גבייה שחלף")
        XCTAssertEqual(PaymentsMath.overdueTotal(categories.collection), 1111.0, accuracy: 0.01,
                       "פירוט הפיגור חייב לשקף את שורת הפיגור בנתוני הבדיקה")
        XCTAssertEqual(pay, 7009.0, accuracy: 0.01,
                       "לתשלום חייב לסכום רק שורות תשלום פתוחות ותקפות")
    }

    // MARK: - סטטוס שורה לסינון (התקבל / לגבייה / מועד חלף)

    func testRowStatusPaid() {
        let row = DomainRecord(fields: ["paid": .string("TRUE"), "due_date": .string("01/01/2020")])
        XCTAssertEqual(PaymentsMath.status(of: row), .paid, "שורה ששולמה היא תמיד ירוקה — גם אם המועד עבר")
    }

    func testRowStatusOverdueWhenDuePassed() {
        let row = DomainRecord(fields: ["paid": .string("FALSE"), "due_date": .string("01/06/2026")])
        let today = DateComponents(calendar: .init(identifier: .gregorian), year: 2026, month: 7, day: 6).date!
        XCTAssertEqual(PaymentsMath.status(of: row, today: today), .overdue)
    }

    func testRowStatusOpenWhenDueInFuture() {
        let row = DomainRecord(fields: ["paid": .string("FALSE"), "due_date": .string("01/09/2026")])
        let today = DateComponents(calendar: .init(identifier: .gregorian), year: 2026, month: 7, day: 6).date!
        XCTAssertEqual(PaymentsMath.status(of: row, today: today), .open)
    }

    func testRowStatusOpenWithoutDueDate() {
        let row = DomainRecord(fields: ["paid": .string("FALSE")])
        XCTAssertEqual(PaymentsMath.status(of: row), .open, "בלי תאריך יעד אין 'מועד חלף' — השורה פתוחה")
    }
}
