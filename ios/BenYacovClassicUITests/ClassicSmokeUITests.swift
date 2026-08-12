import XCTest

/// E2E לקלאסיק — אותו mock, אותם קודים (TOTP 123456): התחברות, בית, רשימות,
/// פירוט, פעולה עם נעילה אופטימית, סינון תשלומים וטופס.
final class ClassicSmokeUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    private func launch(authenticated: Bool = true) {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        if authenticated { app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1" }
        app.launch()
    }

    private func element(_ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }

    @discardableResult
    private func waitFor(_ element: XCUIElement, timeout: TimeInterval = 8,
                         file: StaticString = #filePath, line: UInt = #line) -> XCUIElement {
        XCTAssertTrue(element.waitForExistence(timeout: timeout), "לא הופיע: \(element)", file: file, line: line)
        return element
    }

    private func tapTab(_ title: String) {
        let tab = app.tabBars.buttons[title]
        if tab.waitForExistence(timeout: 3) { tab.tap(); return }
        waitFor(app.buttons[title].firstMatch).tap()
    }

    func testLoginWithTOTP() {
        launch(authenticated: false)
        waitFor(element("classic-login"))
        waitFor(app.buttons["classic-user-asaf"]).tap()
        let code = waitFor(app.textFields["classic-code"])
        code.tap()
        code.typeText("123456")
        waitFor(app.buttons["classic-submit"]).tap()
        waitFor(element("classic-home"), timeout: 10)
    }

    func testHomeTilesShowExactAmounts() {
        launch()
        let tile = waitFor(element("classic-tile-collection"), timeout: 10)
        // אותם חישובים כמו האפליקציה הראשית — אותם מספרים מה-fixtures.
        XCTAssertTrue(tile.label.contains("25,452"), "לגבייה: \(tile.label)")
        XCTAssertTrue(tile.label.contains("1,111"), "פיגור: \(tile.label)")
        XCTAssertTrue(element("classic-tile-payment").label.contains("7,009"),
                      "לתשלום: \(element("classic-tile-payment").label)")
    }

    func testDomainsBrowseAndDetail() {
        launch()
        tapTab("הזמנות")
        waitFor(app.buttons["classic-row-working_orders"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-chip-order_history"]).tap()
        app.buttons["classic-row-order_history"].firstMatch.tap()
        waitFor(element("classic-detail"))
        waitFor(app.buttons["classic-close-detail"]).tap()
    }

    func testPaymentsFilterAndPaidActionWithLocking() {
        launch()
        tapTab("כספים")
        waitFor(app.buttons["classic-row-payments_transfer"].firstMatch, timeout: 10)

        // סינון מועד חלף — שורת ה-1,111 היחידה.
        waitFor(app.buttons["classic-status-overdue"]).tap()
        XCTAssertEqual(element("classic-count").label, "1 רשומות")
        waitFor(app.buttons["classic-status-overdue"]).tap()

        // פעולה אמיתית מול ה-mock — עם expected_snapshot_hash (ה-mock מחייב).
        app.buttons["classic-row-payments_transfer"].firstMatch.tap()
        waitFor(element("classic-detail"))
        waitFor(app.buttons["classic-action-toggle-paid"]).tap()
        waitFor(element("classic-toast"), timeout: 8)
    }

    func testCustomerFormValidationAndCreate() {
        launch()
        tapTab("לקוחות")
        waitFor(app.buttons["classic-row-customers"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-add"]).tap()
        waitFor(app.buttons["classic-form-save"]).tap()
        waitFor(element("classic-form-error"), timeout: 5)
        let name = app.textFields["classic-form-customer_name"]
        name.tap()
        name.typeText("לקוח קלאסי TEST")
        waitFor(app.buttons["classic-form-save"]).tap()
        waitFor(element("classic-toast"), timeout: 8)
    }

    func testFinanceInvoicesSortAndReportFilterClassic() {
        launch()
        tapTab("כספים")
        waitFor(app.buttons["classic-row-payments_transfer"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-chip-finance_invoices"]).tap()
        let rows = app.buttons.matching(identifier: "classic-row-finance_invoices")
        waitFor(rows.firstMatch, timeout: 10)

        // ברירת מחדל: תאריך מהחדש לישן — פלאקסי (31/05/2026) ראשונה.
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("פלאקסי"),
                      "השורה הראשונה אינה החשבונית האחרונה: \(rows.element(boundBy: 0).label)")

        // סינון מועד דיווח (label עם bidi isolates — לכן CONTAINS) → 2 רשומות, ביטול → 6.
        let chip = app.buttons.matching(identifier: "classic-finance-report-filter")
            .matching(NSPredicate(format: "label CONTAINS %@", "15.1.26")).firstMatch
        waitFor(chip).tap()
        XCTAssertEqual(element("classic-count").label, "2 רשומות")
        chip.tap()
        XCTAssertEqual(element("classic-count").label, "6 רשומות")

        // מיון: סכום מהגבוה לנמוך — פז (3,579.28) עוברת לראש.
        waitFor(element("classic-finance-sort-menu")).tap()
        waitFor(app.buttons["סכום — מהגבוה לנמוך"]).tap()
        waitFor(rows.firstMatch)
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("פז"),
                      "מיון סכום יורד לא העלה את החשבונית הגבוהה: \(rows.element(boundBy: 0).label)")
    }

    func testLoansAndVehiclesScreensClassic() {
        launch()
        tapTab("עוד")

        // הלוואות ומשכנתאות — סיכומים, כרטיסים, קרא עוד וצפיין מסמכים.
        waitFor(app.buttons["classic-more-loans"]).tap()
        waitFor(element("classic-loans-screen"), timeout: 8)
        waitFor(element("classic-loans-totals"))
        XCTAssertTrue(app.staticTexts["₪ 382,559.42"].waitForExistence(timeout: 6),
                      "היתרה המחושבת לא מוצגת")
        XCTAssertTrue(app.staticTexts["משכנתא - הגורן 34, עתלית"].exists, "כרטיס המשכנתא חסר")
        waitFor(app.buttons["classic-loan-read-more"].firstMatch).tap()
        let accountDetail = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "253594555")).firstMatch
        XCTAssertTrue(accountDetail.waitForExistence(timeout: 4), "פרטי החשבון לא נחשפו")
        waitFor(app.buttons["classic-lending-doc-open"].firstMatch).tap()
        waitFor(element("classic-document-pdf"), timeout: 10)
        waitFor(app.buttons["classic-document-close"]).tap()

        // חזרה ל"עוד" → צי רכבים.
        let backButton = app.navigationBars.buttons.firstMatch
        if backButton.exists { backButton.tap() }
        waitFor(app.buttons["classic-more-vehicles"]).tap()
        waitFor(element("classic-vehicles-screen"), timeout: 8)
        XCTAssertTrue(app.staticTexts["קיה נירו אפורה"].waitForExistence(timeout: 6),
                      "כרטיס הרכב חסר")
        XCTAssertTrue(app.staticTexts["הפניקס"].exists, "פרטי הביטוח חסרים")
        waitFor(app.buttons["classic-lending-doc-open"].firstMatch).tap()
        waitFor(element("classic-document-pdf"), timeout: 10)
        waitFor(app.buttons["classic-document-close"]).tap()
    }

    func testOrderComposerSampleFlowClassic() {
        launch()
        tapTab("הזמנות")
        waitFor(app.buttons["classic-row-working_orders"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-flow-button"]).tap()
        waitFor(element("classic-order-composer"), timeout: 6)
        waitFor(app.buttons["classic-composer-sample-file"]).tap()

        // ההזמנה פורסרה — שדות ופריטים על המסך, יצירה בסנדבוקס.
        let nameField = waitFor(app.textFields["classic-composer-field-customer_name"], timeout: 10)
        XCTAssertFalse((nameField.value as? String ?? "").isEmpty, "שם הלקוח לא מולא מהפרסור")
        let finalize = app.buttons["classic-composer-finalize"]
        var attempts = 0
        while !finalize.isHittable && attempts < 8 { app.swipeUp(); attempts += 1 }
        finalize.tap()
        waitFor(element("classic-composer-done"), timeout: 12)
        waitFor(app.buttons["classic-composer-done-close"]).tap()
    }

    func testWorkingOrderCreateOrderFlowClassic() {
        launch()
        tapTab("הזמנות")
        waitFor(app.buttons["classic-row-working_orders"].firstMatch, timeout: 10).tap()
        waitFor(element("classic-detail"))
        waitFor(app.buttons["classic-working-order-create"]).tap()
        waitFor(element("classic-order-composer"), timeout: 6)

        // הפרטים נטענו מ-payload_json כולל הפריטים.
        let nameField = waitFor(app.textFields["classic-composer-field-customer_name"])
        XCTAssertTrue((nameField.value as? String)?.contains("דמרי") == true,
                      "פרטי ההזמנה לא נטענו: \(String(describing: nameField.value))")
        XCTAssertFalse(app.buttons["classic-composer-park"].exists,
                       "כפתור השמירה לעבודה לא אמור להופיע בהזמנה שכבר בעבודה")

        // יצירה בפרודקשן — השורה יורדת מ"בעבודה".
        waitFor(app.buttons["פרודקשן"].firstMatch).tap()
        let finalize = app.buttons["classic-composer-finalize"]
        var attempts = 0
        while !finalize.isHittable && attempts < 8 { app.swipeUp(); attempts += 1 }
        finalize.tap()
        waitFor(element("classic-composer-done"), timeout: 12)
        app.buttons["classic-composer-done-close"].tap()
        let row = app.buttons["classic-row-working_orders"].firstMatch
        let deadline = Date().addingTimeInterval(10)
        while row.exists && Date() < deadline { usleep(300_000) }
        XCTAssertFalse(row.exists, "ההזמנה בעבודה לא הוסרה אחרי finalize בפרודקשן")
    }

    func testQuoteComposerFlowClassic() {
        launch()
        tapTab("הזמנות")
        waitFor(app.buttons["classic-row-working_orders"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-chip-quote_history"]).tap()
        waitFor(app.buttons["classic-row-quote_history"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-flow-button"]).tap()
        waitFor(element("classic-quote-composer"), timeout: 6)

        // מילוי מלקוחות אחרונים + פריט.
        waitFor(app.buttons["classic-quote-recent-customers"]).tap()
        waitFor(app.buttons["י.ח. דמרי בניה ופיתוח בעמ"].firstMatch).tap()
        let description = waitFor(element("classic-quote-item-description"))
        description.tap()
        description.typeText("וילון גלילה TEST")
        let price = app.textFields["classic-quote-item-price"]
        price.tap()
        price.typeText("250")
        let create = app.buttons["classic-quote-create"]
        var attempts = 0
        while !create.isHittable && attempts < 8 { app.swipeUp(); attempts += 1 }
        create.tap()
        waitFor(element("classic-quote-done"), timeout: 12)
        waitFor(app.buttons["classic-quote-done-close"]).tap()
    }

    func testSupplierPOComposerFlowClassic() {
        launch()
        tapTab("עוד")
        waitFor(app.buttons["מלאי ותמחור"].firstMatch).tap()
        waitFor(app.buttons["classic-row-inventory_purchase_orders"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-flow-button"]).tap()
        waitFor(element("classic-supplier-composer"), timeout: 6)

        let name = waitFor(app.textFields["classic-supplier-field-name"])
        name.tap()
        name.typeText("ספק קלאסי TEST")
        let description = app.textFields["classic-supplier-item-description"].firstMatch
        description.tap()
        description.typeText("בד אקוסטי")
        let quantity = app.textFields["classic-supplier-item-quantity"].firstMatch
        quantity.tap()
        quantity.typeText("2")
        let price = app.textFields["classic-supplier-item-price"].firstMatch
        price.tap()
        price.typeText("100")
        // סוגרים את המקלדת בהקשה על הסגמנט שכבר נבחר (לא משנה מצב), ואז מקישים.
        app.buttons["סנדבוקס (בדיקה)"].firstMatch.tap()
        let create = waitFor(app.buttons["classic-supplier-create"])
        let deadline = Date().addingTimeInterval(5)
        while !create.isHittable && Date() < deadline { usleep(300_000) }
        create.tap()
        waitFor(element("classic-supplier-done"), timeout: 12)
        waitFor(app.buttons["classic-supplier-done-close"]).tap()
    }

    func testInvoiceUploadFlowClassic() {
        launch()
        tapTab("כספים")
        waitFor(app.buttons["classic-row-payments_transfer"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-chip-finance_invoices"]).tap()
        waitFor(app.buttons["classic-row-finance_invoices"].firstMatch, timeout: 10)
        waitFor(app.buttons["classic-flow-button"]).tap()
        waitFor(element("classic-invoice-upload"), timeout: 6)
        waitFor(app.buttons["classic-invoice-sample-file"]).tap()

        // הטיוטה פורסרה — שמירה לטבלת הכספים.
        let supplierField = waitFor(app.textFields["classic-invoice-field-supplier_name"], timeout: 10)
        XCTAssertFalse((supplierField.value as? String ?? "").isEmpty, "הספק לא מולא מהפרסור")
        let save = app.buttons["classic-invoice-save-draft"]
        var attempts = 0
        while !save.isHittable && attempts < 8 { app.swipeUp(); attempts += 1 }
        save.tap()
        waitFor(element("classic-invoice-saved-badge"), timeout: 10)
        waitFor(app.buttons["classic-invoice-close"]).tap()
    }

    func testLabelsFlowClassic() {
        launch()
        tapTab("עוד")
        waitFor(app.buttons["classic-more-labels"]).tap()
        waitFor(element("classic-labels-screen"), timeout: 6)
        let customer = waitFor(app.textFields["classic-labels-customer"])
        customer.tap()
        customer.typeText("לקוח מדבקות TEST")
        waitFor(app.buttons["classic-labels-create"]).tap()
        waitFor(element("classic-labels-done"), timeout: 10)
    }

    func testSearchInDomain() {
        launch()
        tapTab("כספים")
        waitFor(app.buttons["classic-row-payments_transfer"].firstMatch, timeout: 10)
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("550583")
        XCTAssertEqual(element("classic-count").label, "1 רשומות")
    }

    func testTouchIDLockBlocksAndUnlocks() {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
        app.launchEnvironment["BY_UITEST_FACE_ID_ENABLED"] = "1"
        app.launchEnvironment["BY_UITEST_FACE_ID"] = "fail"
        app.launch()

        waitFor(element("classic-lock-screen"), timeout: 8)
        waitFor(app.buttons["classic-unlock"]).tap()
        waitFor(element("classic-lock-failed"), timeout: 6)
        // הקשה מבעד לנעילה לא מגיעה לתוכן.
        let tile = app.buttons["classic-tile-collection"].firstMatch
        if tile.exists { tile.tap() }
        XCTAssertTrue(element("classic-lock-screen").exists, "המסך נשאר נעול אחרי כשל")
    }

    func testTouchIDUnlockSuccessOpens() {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
        app.launchEnvironment["BY_UITEST_FACE_ID_ENABLED"] = "1"
        app.launch()
        // האימות האוטומטי (המזויף) מצליח — הבית נפתח.
        if element("classic-lock-screen").waitForExistence(timeout: 2),
           app.buttons["classic-unlock"].exists {
            app.buttons["classic-unlock"].tap()
        }
        waitFor(element("classic-home"), timeout: 10)
    }

    func testTouchIDToggleInSettings() {
        launch()
        tapTab("עוד")
        let toggle = app.switches["classic-touchid-toggle"].firstMatch
        XCTAssertTrue(toggle.waitForExistence(timeout: 8), "טוגל הנעילה חסר בהגדרות")
        toggle.switches.firstMatch.tap()
        waitFor(element("classic-toast"), timeout: 6)
    }

    func testCustomerTypeFilterClassic() {
        launch()
        tapTab("לקוחות")
        waitFor(app.buttons["classic-row-customers"].firstMatch, timeout: 10)
        let allCount = element("classic-count").label
        waitFor(app.buttons["classic-customer-type-textile"]).tap()
        XCTAssertNotEqual(element("classic-count").label, allCount, "סינון הטקסטיל לא צמצם")
        app.buttons["classic-customer-type-textile"].tap()
        XCTAssertEqual(element("classic-count").label, allCount, "הטוגל לא ביטל")
        let firstTitle = app.buttons["classic-row-customers"].firstMatch.label
        XCTAssertTrue(firstTitle.hasPrefix("א"), "מיון אלפביתי — הראשון: \(firstTitle)")
    }

    func testInstallationsFilterAndDetailsClassic() {
        launch()
        tapTab("הזמנות")
        waitFor(app.buttons["classic-chip-installation_cases"]).tap()
        waitFor(app.buttons["classic-row-installation_cases"].firstMatch, timeout: 10)
        let allCount = element("classic-count").label

        // הפרטים המורחבים על השורה: התקדמות ("מתוך") מוצגת.
        let firstRow = app.buttons["classic-row-installation_cases"].firstMatch
        XCTAssertTrue(firstRow.label.contains("מתוך") || firstRow.label.contains("ביקור"),
                      "חסרים פרטי התקדמות בשורה: \(firstRow.label)")

        // סינון "הושלם" מצמצם; טוגל מבטל.
        let doneChip = app.buttons.matching(NSPredicate(format: "label == %@", "הושלם")).firstMatch
        waitFor(doneChip).tap()
        XCTAssertNotEqual(element("classic-count").label, allCount, "הסינון לא צמצם")
        doneChip.tap()
        XCTAssertEqual(element("classic-count").label, allCount)
    }

    func testLastLoggedInUserIsDefaultSelection() {
        // מדמים "התחברות קודמת של אמא" דרך ה-seed — ובודקים שהיא הדיפולט.
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchEnvironment["BY_UITEST_LAST_USER"] = "reut"
        app.launch()
        waitFor(element("classic-login"))
        let reut = waitFor(app.buttons["classic-user-reut"])
        XCTAssertTrue(reut.isSelected, "המשתמש האחרון שהתחבר חייב להיות מסומן כברירת מחדל")
        XCTAssertFalse(app.buttons["classic-user-asaf"].isSelected)

        // בלי היסטוריה — הראשון נבחר.
        app.terminate()
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launch()
        waitFor(element("classic-login"))
        XCTAssertTrue(app.buttons["classic-user-asaf"].firstMatch.isSelected)
    }
}
