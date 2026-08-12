import XCTest
@testable import BenYacovManage

/// טסטים לעיצוב ערכים — מטבע, תאריכים, טלפונים וקישורים.
final class FormattersTests: XCTestCase {

    // MARK: - מטבע

    func testCurrencyTextFromPlainNumber() {
        let result = Formatters.currencyText("3192.22", detailed: true)
        XCTAssertTrue(result.contains("3,192.22"), "קיבלנו: \(result)")
        XCTAssertTrue(result.contains("₪"))
    }

    func testCurrencyTextFromDecoratedString() {
        let result = Formatters.currencyText("₪7,009.00")
        XCTAssertTrue(result.contains("7,009"), "קיבלנו: \(result)")
    }

    func testCurrencyTextLeavesGarbageAlone() {
        XCTAssertEqual(Formatters.currencyText("לא מספר"), "לא מספר")
        XCTAssertEqual(Formatters.currencyText(""), "")
    }

    func testCurrencyValue() {
        let result = Formatters.currencyValue(24341)
        XCTAssertTrue(result.contains("24,341"), "קיבלנו: \(result)")
    }

    // MARK: - תאריכים

    func testDateTextISOWithTime() {
        let result = Formatters.dateText("2026-07-02T16:15:35")
        XCTAssertTrue(result.contains("2.7.2026"), "קיבלנו: \(result)")
        XCTAssertTrue(result.contains("16:15"))
    }

    func testDateTextISODateOnly() {
        XCTAssertEqual(Formatters.dateText("2026-05-31"), "31.5.2026")
    }

    func testDateTextIsraeliFormat() {
        XCTAssertEqual(Formatters.dateText("27/05/2026"), "27.5.2026")
    }

    func testDateTextEpoch() {
        // 1719136634 = 23.6.2024
        let result = Formatters.dateText("1719136634")
        XCTAssertTrue(result.contains("2024"), "קיבלנו: \(result)")
    }

    func testDateTextMonthKey() {
        let result = Formatters.dateText("2026-06")
        XCTAssertTrue(result.contains("2026"), "קיבלנו: \(result)")
        XCTAssertTrue(result.contains("יוני"), "קיבלנו: \(result)")
    }

    func testDateTextPassthrough() {
        XCTAssertEqual(Formatters.dateText("טקסט חופשי"), "טקסט חופשי")
        XCTAssertEqual(Formatters.dateText(""), "")
    }

    // MARK: - טלפונים

    func testNormalizedPhoneLocal() {
        XCTAssertEqual(Formatters.normalizedPhone("050-5204010"), "+972505204010")
        XCTAssertEqual(Formatters.normalizedPhone("08-9939000"), "+97289939000")
    }

    func testNormalizedPhoneInternational() {
        XCTAssertEqual(Formatters.normalizedPhone("+972 50 520 4010"), "+972505204010")
    }

    func testWhatsappURL() throws {
        let url = try XCTUnwrap(Formatters.whatsappURL(phone: "050-5204010", message: "שלום"))
        XCTAssertTrue(url.absoluteString.hasPrefix("https://wa.me/972505204010"))
        XCTAssertNil(Formatters.whatsappURL(phone: ""))
    }

    func testCallURL() throws {
        let url = try XCTUnwrap(Formatters.callURL(phone: "055-6818973"))
        XCTAssertEqual(url.scheme, "tel")
        XCTAssertNil(Formatters.callURL(phone: ""))
    }

    func testMailURLTakesFirstAddress() throws {
        let url = try XCTUnwrap(Formatters.mailURL("a@b.co.il, c@d.com"))
        XCTAssertEqual(url.absoluteString, "mailto:a@b.co.il")
        XCTAssertNil(Formatters.mailURL("לא מייל"))
    }
}
