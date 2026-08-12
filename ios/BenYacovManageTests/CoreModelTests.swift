import XCTest
@testable import BenYacovManage

/// טסטים לשכבת המודלים — JSONValue, DomainRecord, קטלוג הדומיינים ותוויות.
final class CoreModelTests: XCTestCase {

    // MARK: - קטלוג דומיינים

    func testEveryDomainHasSpec() {
        for domain in Domain.allCases {
            let spec = DomainSpec.catalog[domain]
            XCTAssertNotNil(spec, "חסר spec לדומיין \(domain.rawValue)")
        }
        XCTAssertEqual(Domain.allCases.filter(\.isMobileDomain).count, 33,
                       "מספר דומייני המובייל חייב להתאים לשרת")
        XCTAssertEqual(Domain.allCases.count, 35, "33 דומייני מובייל + תיקי התקנות + ביקורים")
    }

    func testEverySpecIsUsable() {
        for domain in Domain.allCases {
            let spec = domain.spec
            XCTAssertFalse(spec.title.isEmpty, "\(domain.rawValue): כותרת ריקה")
            XCTAssertFalse(spec.icon.isEmpty, "\(domain.rawValue): אייקון ריק")
            XCTAssertFalse(spec.titleKeys.isEmpty, "\(domain.rawValue): אין מפתחות כותרת")
            XCTAssertFalse(spec.searchKeys.isEmpty, "\(domain.rawValue): אין מפתחות חיפוש")
            XCTAssertFalse(spec.detailKeys.isEmpty, "\(domain.rawValue): אין שדות פירוט")
        }
    }

    func testDomainTitlesAreUnique() {
        let titles = Domain.allCases.map { $0.spec.title }
        XCTAssertEqual(titles.count, Set(titles).count, "כותרות דומיינים כפולות")
    }

    func testBootstrapSectionIDsMatchServerConvention() {
        XCTAssertEqual(Domain.customers.bootstrapSectionID, "customers-active")
        XCTAssertEqual(Domain.inactiveCustomers.bootstrapSectionID, "customers-inactive")
        XCTAssertEqual(Domain.orderHistory.bootstrapSectionID, "orders-history")
        XCTAssertEqual(Domain.quoteHistory.bootstrapSectionID, "quotes-history")
        XCTAssertEqual(Domain.financeCustomerWithholdings.bootstrapSectionID, "finance-withholdings")
        XCTAssertEqual(Domain.financeBankMovements.bootstrapSectionID, "finance-bank")
        XCTAssertEqual(Domain.paymentsTransfer.bootstrapSectionID, "payments-transfer")
        XCTAssertEqual(Domain.hrPayslipPrepHistory.bootstrapSectionID, "hr-payslip-prep-history")
    }

    // MARK: - JSONValue

    func testJSONValueDecoding() throws {
        let json = """
        {"a": "text", "b": 5, "c": 5.5, "d": true, "e": null, "f": [1, "x"], "g": {"h": 1}}
        """.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: json)
        XCTAssertEqual(decoded["a"], .string("text"))
        XCTAssertEqual(decoded["b"], .number(5))
        XCTAssertEqual(decoded["d"], .bool(true))
        XCTAssertEqual(decoded["e"], .null)
        XCTAssertEqual(decoded["a"]?.displayText, "text")
        XCTAssertEqual(decoded["b"]?.displayText, "5")
        XCTAssertEqual(decoded["c"]?.displayText, "5.5")
        XCTAssertEqual(decoded["d"]?.displayText, "כן")
        XCTAssertEqual(decoded["e"]?.displayText, "")
        XCTAssertTrue(decoded["e"]?.isEmptyDisplay ?? false)
    }

    // MARK: - DomainRecord

    func testRecordIDPrefersKnownKeys() {
        let record = DomainRecord(fields: [
            "row_id": .string("r-1"),
            "customer_name": .string("בדיקה"),
        ])
        XCTAssertEqual(record.id, "row_id:r-1")
    }

    func testRecordIDFallsBackToHash() {
        let record = DomainRecord(fields: ["x": .string("1")])
        XCTAssertTrue(record.id.hasPrefix("hash:"))
        let identical = DomainRecord(fields: ["x": .string("1")])
        XCTAssertEqual(record.id, identical.id, "אותם שדות חייבים לתת אותו מזהה")
    }

    func testRecordNumberParsesCurrencyStrings() {
        let record = DomainRecord(fields: [
            "amount": .string("₪7,009.00"),
            "total": .string("3192.22"),
            "count": .number(12),
            "bad": .string("abc"),
        ])
        XCTAssertEqual(record.number("amount"), 7009.0)
        XCTAssertEqual(record.number("total"), 3192.22)
        XCTAssertEqual(record.number("count"), 12)
        XCTAssertNil(record.number("bad"))
        XCTAssertNil(record.number("missing"))
    }

    func testRecordBoolParsing() {
        let record = DomainRecord(fields: [
            "t1": .string("TRUE"), "t2": .string("כן"), "t3": .bool(true), "t4": .number(1),
            "f1": .string("FALSE"), "f2": .string(""), "f3": .bool(false),
        ])
        for key in ["t1", "t2", "t3", "t4"] {
            XCTAssertTrue(record.bool(key), "\(key) אמור להיות אמת")
        }
        for key in ["f1", "f2", "f3", "missing"] {
            XCTAssertFalse(record.bool(key), "\(key) אמור להיות שקר")
        }
    }

    func testRecordFirstOfKeys() {
        let record = DomainRecord(fields: [
            "empty": .string(""),
            "second": .string("ערך"),
        ])
        XCTAssertEqual(record.first(of: ["empty", "second"]), "ערך")
        XCTAssertEqual(record.first(of: ["missing"]), "")
    }

    func testRecordsFromRowsJSON() throws {
        let json = """
        {"status": "ok", "rows": [{"row_id": "1", "name": "א"}, {"row_id": "2", "name": "ב"}]}
        """.data(using: .utf8)!
        let records = try DomainRecord.records(fromRowsJSON: json)
        XCTAssertEqual(records.count, 2)
        XCTAssertEqual(records[0]["name"], "א")
    }

    func testJSONObjectRoundTrip() {
        let record = DomainRecord(fields: [
            "name": .string("לקוח"),
            "amount": .number(10),
            "flag": .bool(true),
        ])
        let object = record.jsonObject
        XCTAssertEqual(object["name"] as? String, "לקוח")
        XCTAssertEqual(object["amount"] as? Double, 10)
        XCTAssertEqual(object["flag"] as? Bool, true)
    }

    // MARK: - תוויות

    func testFieldLabelsKnownAndFallback() {
        XCTAssertEqual(FieldLabels.label(for: "customer_name"), "שם לקוח")
        XCTAssertEqual(FieldLabels.label(for: "unknown_key"), "unknown key")
        XCTAssertTrue(FieldLabels.hiddenKeys.contains("row_id"))
        XCTAssertTrue(FieldLabels.linkKeys.contains("drive_url"))
    }

    func testDetailKeysAreNotHidden() {
        for domain in Domain.allCases {
            for key in domain.spec.detailKeys {
                XCTAssertFalse(
                    FieldLabels.hiddenKeys.contains(key),
                    "\(domain.rawValue): המפתח \(key) גם בפירוט וגם מוסתר"
                )
            }
        }
    }
}
