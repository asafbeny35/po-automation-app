import XCTest

/// סריקה מלאה: כל 33 הדומיינים נפתחים, מציגים שורות, ופירוט נפתח ונסגר.
/// הכיסוי מפוצל לפי טאב כדי שכל טסט יישאר ממוקד ומהיר.
final class DomainSweepUITests: BYUITestCase {

    private func sweep(_ domains: [String]) {
        for domain in domains {
            tapChip(domain)
            waitForRows(domain)
            openAndCloseFirstRecord(domain)
            assertSearchWorks(domain)
        }
    }

    /// חיפוש בכל דומיין: שאילתה בלי תוצאות מציגה מצב ריק, ומחיקתה מחזירה את הרשימה.
    private func assertSearchWorks(_ domain: String) {
        let search = app.searchFields.firstMatch
        guard search.waitForExistence(timeout: 5) else {
            XCTFail("אין שדה חיפוש בדומיין \(domain)")
            return
        }
        search.tap()
        search.typeText("qqzzqq")
        waitFor(element("empty-state"), timeout: 6)
        search.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 6))
        waitForRows(domain)
        // סוגרים את מצב החיפוש כדי לא להשפיע על הצ'יפ הבא.
        if app.buttons["ביטול"].firstMatch.exists {
            app.buttons["ביטול"].firstMatch.tap()
        } else if app.buttons["Cancel"].firstMatch.exists {
            app.buttons["Cancel"].firstMatch.tap()
        }
    }

    func testOrdersTabDomains() {
        launchApp()
        tapTab("הזמנות")
        sweep(["working_orders", "order_history", "quote_history", "delivery_confirmations", "installation_cases"])
    }

    func testCustomersTabDomains() {
        launchApp()
        tapTab("לקוחות")
        sweep(["customers", "inactive_customers"])
    }

    func testFinanceTabDomains() {
        launchApp()
        tapTab("כספים")
        sweep(["payments_transfer", "finance_invoices", "finance_customer_withholdings", "finance_bank_movements"])
    }

    func testMarketingDomains() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-marketing"], timeout: 6).tap()
        sweep(["marketing_pipeline", "marketing_reminders", "marketing_work_managers",
               "marketing_construction_companies", "marketing_history"])
    }

    func testHRDomains() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-hr"], timeout: 6).tap()
        sweep(["hr_employees", "hr_hours", "hr_payroll", "hr_contributions", "hr_documents", "hr_payslip_prep_history"])
    }

    func testInventoryDomains() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-inventory"], timeout: 6).tap()
        sweep(["inventory_purchase_orders", "inventory_raw", "inventory_finish",
               "inventory_contacts", "supplier_delivery_notes", "pricing_items", "pricing_components"])
    }

    func testAdminDomains() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-admin"], timeout: 6).tap()
        sweep(["pazomat", "sibus", "delivery_contacts", "project_managers", "finance_settings"])
    }
}
