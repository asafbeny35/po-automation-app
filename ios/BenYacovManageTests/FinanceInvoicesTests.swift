import XCTest
@testable import BenYacovManage

/// מיון וסינון חשבוניות ספקים — שיקוף מיון הטבלה וכפתורי הדיווח בדסקטופ.
final class FinanceInvoicesTests: XCTestCase {

    private func row(_ fields: [String: String]) -> DomainRecord {
        DomainRecord(fields: fields.mapValues { .string($0) })
    }

    // MARK: - מפתח מיון תאריכים

    func testDateSortKeyHandlesIsraeliAndISOFormats() {
        XCTAssertEqual(FinanceInvoices.dateSortKey("31/12/2025"), "2025-12-31")
        XCTAssertEqual(FinanceInvoices.dateSortKey("1/7/2026"), "2026-07-01")
        XCTAssertEqual(FinanceInvoices.dateSortKey("2026-06-03T09:14:16"), "2026-06-03T09:14:16")
        XCTAssertEqual(FinanceInvoices.dateSortKey(""), "")
        // ISO מאוחר גדול מ-DD/MM/YYYY מוקדם — שני הפורמטים משתלבים באותו ציר.
        XCTAssertTrue(FinanceInvoices.dateSortKey("2026-06-03") > FinanceInvoices.dateSortKey("31/12/2025"))
    }

    // MARK: - מיון

    func testDefaultSortIsLatestInvoiceFirst() {
        let rows = [
            row(["row_id": "a", "invoice_date": "31/08/2025", "total": "100"]),
            row(["row_id": "b", "invoice_date": "31/05/2026", "total": "200"]),
            row(["row_id": "c", "invoice_date": "31/12/2025", "total": "300"]),
        ]
        let sorted = FinanceInvoices.sorted(rows, by: .dateDesc)
        XCTAssertEqual(sorted.map { $0["row_id"] }, ["b", "c", "a"])
    }

    func testAmountSortBothDirectionsAndDirtyValues() {
        let rows = [
            row(["row_id": "high", "total": "3,313.68"]),
            row(["row_id": "empty", "total": ""]),
            row(["row_id": "low", "total": "₪48.00"]),
        ]
        XCTAssertEqual(FinanceInvoices.sorted(rows, by: .amountAsc).map { $0["row_id"] },
                       ["empty", "low", "high"])
        XCTAssertEqual(FinanceInvoices.sorted(rows, by: .amountDesc).map { $0["row_id"] },
                       ["high", "low", "empty"])
    }

    func testSupplierSortIsHebrewThenLatinCaseInsensitive() {
        let rows = [
            row(["row_id": "paz", "supplier_name": "פז קמעונאות"]),
            row(["row_id": "google", "supplier_name": "google Ads"]),
            row(["row_id": "flaxi", "supplier_name": "פלאקסי ישראל"]),
            row(["row_id": "adobe", "supplier_name": "Adobe"]),
        ]
        let names = FinanceInvoices.sorted(rows, by: .supplierAlphabetical).map { $0["row_id"] }
        // לוקאל עברי: א׳-ב׳ קודם, ואז ABC בלי רגישות לרישיות.
        XCTAssertEqual(names, ["paz", "flaxi", "adobe", "google"])
    }

    // MARK: - מועדי דיווח

    func testDueDatesIncludeOverridesWithoutDuplicates() {
        let record = row([
            "report_due_date": "15/01/2026",
            "report_due_overrides": "15/03/2026, 15/01/2026",
        ])
        XCTAssertEqual(FinanceInvoices.dueDates(of: record), ["15/01/2026", "15/03/2026"])
        XCTAssertTrue(FinanceInvoices.matches(record, dueDate: "15/03/2026"))
        XCTAssertFalse(FinanceInvoices.matches(record, dueDate: "15/05/2026"))
    }

    func testAvailableDueDatesSortedNewestFirstAndSkipEmpty() {
        let rows = [
            row(["row_id": "a", "report_due_date": "15/01/2026"]),
            row(["row_id": "b", "report_due_date": ""]),
            row(["row_id": "c", "report_due_date": "15/07/2026", "report_due_overrides": "15/09/2026"]),
            row(["row_id": "d", "report_due_date": "15/01/2026"]),
        ]
        XCTAssertEqual(FinanceInvoices.availableDueDates(rows),
                       ["15/09/2026", "15/07/2026", "15/01/2026"])
    }

    func testChipLabelShortFormat() {
        XCTAssertEqual(FinanceInvoices.chipLabel("15/07/2026"), "15.7.26")
        XCTAssertEqual(FinanceInvoices.chipLabel("01/09/2026"), "1.9.26")
        XCTAssertEqual(FinanceInvoices.chipLabel("לא-תאריך"), "לא-תאריך")
    }
}
