import XCTest

/// E2E לפיצ'רים שהושלמו בסבב הפאריטי: הצעות מחיר, קבלות, רכש ספק,
/// מדבקות, טפסים חדשים, צפיינים ווואטסאפ מנהלה.
final class NewFeaturesUITests: BYUITestCase {

    /// מגלגל את המסך עד שהכפתור בר-לחיצה ואז מקיש עליו.
    private func scrollAndTap(_ button: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(button.waitForExistence(timeout: 8), "הכפתור לא קיים: \(button)", file: file, line: line)
        var attempts = 0
        while !button.isHittable && attempts < 8 {
            app.swipeUp()
            attempts += 1
        }
        button.tap()
    }

    // MARK: - קומפוזר הצעות מחיר

    func testQuoteComposerFullFlow() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("quote_history")
        waitForRows("quote_history")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("quote-composer"), timeout: 6)

        // מילוי מהיר מלקוחות אחרונים.
        waitFor(app.buttons["quote-recent-customers"]).tap()
        waitFor(app.buttons["י.ח. דמרי בניה ופיתוח בעמ"].firstMatch).tap()
        let nameField = app.textFields["quote-field-customer_name"]
        XCTAssertTrue((nameField.value as? String)?.contains("דמרי") == true,
                      "הלקוח האחרון לא מולא: \(String(describing: nameField.value))")

        // שדות החובה שהדסקטופ אוכף גם הוא לפני יצירת הצעה.
        let poField = app.textFields["quote-field-po_number"]
        poField.tap()
        poField.typeText("PO26TEST")
        let addressField = app.textFields["quote-field-delivery_address"]
        addressField.tap()
        addressField.typeText("הגורן 34 עתלית")

        // פריט מוצע — השדות ממוספרים כי אפשר להוסיף כמה פריטים.
        let description = waitFor(element("quote-item-description-0"))
        description.tap()
        description.typeText("וילון גלילה TEST")
        let price = app.textFields["quote-item-price-0"]
        price.tap()
        price.typeText("250")

        // יצירה בסנדבוקס (ברירת המחדל).
        scrollAndTap(app.buttons["quote-create"])
        waitFor(element("quote-done"), timeout: 12)
        let doneText = element("quote-done-message").label
        XCTAssertTrue(doneText.contains("הצעת מחיר"), "הודעת הסיום: \(doneText)")
        app.buttons["quote-done-close"].tap()

        // ההצעה החדשה ברשימה.
        waitForRows("quote_history")
    }

    func testQuoteComposerValidatesEmptyItem() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("quote_history")
        waitForRows("quote_history")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("quote-composer"), timeout: 6)
        let nameField = waitFor(app.textFields["quote-field-customer_name"])
        nameField.tap()
        nameField.typeText("לקוח בלי פריט")
        scrollAndTap(app.buttons["quote-create"])
        waitFor(element("quote-error"), timeout: 5)
    }

    // MARK: - פעולות על הצעה קיימת

    func testQuoteEmailSendFromDetail() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("quote_history")
        waitForRows("quote_history")
        app.buttons["row-quote_history"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(element("quote-actions-card"))
        waitFor(app.buttons["quote-email"]).tap()
        let recipients = waitFor(element("quote-email-submit-field"), timeout: 6)
        recipients.tap()
        recipients.typeText("asafbeny@gmail.com")
        waitFor(app.buttons["quote-email-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testQuoteWhatsappSendFromDetail() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("quote_history")
        waitForRows("quote_history")
        app.buttons["row-quote_history"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(app.buttons["quote-whatsapp"]).tap()
        let phone = waitFor(element("quote-whatsapp-submit-phone"), timeout: 6)
        phone.tap()
        phone.typeText("0547720142")
        waitFor(app.buttons["quote-whatsapp-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testQuoteConvertToOrderOpensComposer() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("quote_history")
        waitForRows("quote_history")
        app.buttons["row-quote_history"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(app.buttons["quote-convert"]).tap()

        // הקומפוזר נפתח ישר במצב עריכה עם נתוני ההצעה.
        waitFor(element("order-composer"), timeout: 8)
        let nameField = waitFor(app.textFields["composer-field-customer_name"], timeout: 8)
        XCTAssertFalse(((nameField.value as? String) ?? "").isEmpty, "שם הלקוח לא הועבר מההצעה")
    }

    // MARK: - הפקת קבלה

    func testReceiptCreationFromCollectionRow() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")

        // מאתרים שורת גבייה עם חשבונית מס.
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("550583")
        waitForRows("payments_transfer")
        app.buttons["row-payments_transfer"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)

        waitFor(app.buttons["receipt-open"]).tap()
        waitFor(element("receipt-sheet"), timeout: 6)
        // הסכום ממולא מראש מהשורה.
        let amount = app.textFields["receipt-amount"]
        XCTAssertTrue(((amount.value as? String) ?? "").contains("9062"),
                      "הסכום לא מולא מראש: \(String(describing: amount.value))")
        // הפעלת "הלקוח ניכה במקור" — הניכוי מחושב לבד (3%) ומוצג לאימות.
        let toggle = app.switches["receipt-withholding-toggle"].firstMatch
        if !toggle.isHittable { app.swipeUp() }
        // ב-Form ההקשה חייבת ליפול על המתג הפנימי — הקשה על השורה לא מחליפה מצב.
        toggle.switches.firstMatch.tap()
        waitFor(element("receipt-net"), timeout: 5)
        XCTAssertTrue(element("receipt-withheld").label.contains("271.87"),
                      "הניכוי המחושב שגוי: \(element("receipt-withheld").label)")
        XCTAssertTrue(element("receipt-net").label.contains("8,790.53"),
                      "הסכום אחרי ניכוי שגוי: \(element("receipt-net").label)")

        waitFor(app.buttons["receipt-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    // MARK: - הזמנת רכש לספק

    func testSupplierPOComposerFullFlow() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-inventory"]).tap()
        waitForRows("inventory_purchase_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("supplier-composer"), timeout: 6)

        // בחירת ספק מאנשי הקשר.
        waitFor(app.buttons["supplier-picker"]).tap()
        waitFor(app.buttons["ע.ר יצחק מזרחי"].firstMatch).tap()
        let nameField = app.textFields["supplier-field-name"]
        XCTAssertTrue((nameField.value as? String)?.contains("מזרחי") == true,
                      "הספק לא מולא: \(String(describing: nameField.value))")

        let description = waitFor(app.textFields["supplier-item-description"])
        description.tap()
        description.typeText("בד אקוסטי TEST")
        let price = app.textFields["supplier-item-price"]
        price.tap()
        price.typeText("80")

        scrollAndTap(app.buttons["supplier-create"])
        waitFor(element("supplier-done"), timeout: 12)
        app.buttons["supplier-done-close"].tap()
        waitForRows("inventory_purchase_orders")
    }

    func testSupplierPOWhatsappFromDetail() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-inventory"]).tap()
        waitForRows("inventory_purchase_orders")
        app.buttons["row-inventory_purchase_orders"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(element("supplier-po-send-card"))
        waitFor(app.buttons["supplier-po-whatsapp"]).tap()
        let phone = waitFor(element("supplier-po-whatsapp-submit-phone"), timeout: 6)
        phone.tap()
        phone.typeText("0547720142")
        waitFor(app.buttons["supplier-po-whatsapp-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    // MARK: - מדבקות משלוח

    func testLabelsOnlyFlow() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-labels"]).tap()
        waitFor(element("labels-screen"), timeout: 6)
        let customer = waitFor(app.textFields["labels-customer"])
        customer.tap()
        customer.typeText("לקוח מדבקות TEST")
        scrollAndTap(app.buttons["labels-create"])
        waitFor(element("labels-done"), timeout: 10)
    }

    func testLabelsValidatesEmptyCustomer() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-labels"]).tap()
        waitFor(element("labels-screen"), timeout: 6)
        scrollAndTap(app.buttons["labels-create"])
        waitFor(element("labels-error"), timeout: 5)
    }

    // MARK: - וואטסאפ מסמכי מנהלה

    func testAdminDocWhatsapp() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-documents"]).tap()
        waitFor(element("documents-screen"), timeout: 6)
        scrollAndTap(app.buttons["admin-doc-whatsapp"].firstMatch)
        let phone = waitFor(element("admin-whatsapp-submit-phone"), timeout: 6)
        phone.tap()
        phone.typeText("0547720142")
        waitFor(app.buttons["admin-whatsapp-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    // MARK: - טפסים חדשים

    func testWorkManagerCreateForm() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-marketing"]).tap()
        waitForRows("marketing_pipeline")
        tapChip("marketing_work_managers")
        waitForRows("marketing_work_managers")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let name = waitFor(app.textFields["form-full_name"])
        name.tap()
        name.typeText("מנהל עבודה TEST")
        scrollAndTap(app.buttons["form-save"])
        waitFor(element("toast"), timeout: 8)
    }

    func testConstructionCompanyCreateFormValidation() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-marketing"]).tap()
        waitForRows("marketing_pipeline")
        tapChip("marketing_construction_companies")
        waitForRows("marketing_construction_companies")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        // שמירה בלי שם חברה — ולידציה מקומית עוצרת.
        scrollAndTap(app.buttons["form-save"])
        waitFor(element("form-error"), timeout: 5)
    }

    func testWithholdingCreateForm() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapChip("finance_customer_withholdings")
        waitForRows("finance_customer_withholdings")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        for (id, value) in [("form-customer_name", "לקוח ניכוי TEST"),
                            ("form-invoice_number", "20233"),
                            ("form-receipt_number", "777")] {
            let field = app.textFields[id]
            field.tap()
            field.typeText(value)
        }
        scrollAndTap(app.buttons["form-save"])
        waitFor(element("toast"), timeout: 8)
    }

    // MARK: - סינון תשלומים והעברות (גבייה/תשלום + סטטוס)

    func testPaymentsDirectionAndStatusFilters() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")

        // ברירת מחדל: גבייה, עם כפתורי הסטטוס של גבייה.
        waitFor(element("payments-direction"))
        waitFor(app.buttons["payments-status-overdue"])
        XCTAssertEqual(app.buttons["payments-status-overdue"].label, "מועד הגבייה חלף")

        // סינון "מועד הגבייה חלף" — נשארת רק שורת הפיגור מה-fixtures (1,111 ₪).
        app.buttons["payments-status-overdue"].tap()
        waitForRows("payments_transfer")
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "לקוח בפיגור")).firstMatch
                .waitForExistence(timeout: 6),
            "שורת הפיגור לא מוצגת בסינון מועד חלף"
        )
        XCTAssertEqual(element("record-count").label, "1 רשומות")
        XCTAssertTrue(element("payments-filter-total").label.contains("1,111"),
                      "סכום הסינון שגוי: \(element("payments-filter-total").label)")

        // לחיצה נוספת מבטלת את הסינון — כמו בדסקטופ.
        app.buttons["payments-status-overdue"].tap()
        waitForRows("payments_transfer")
        XCTAssertNotEqual(element("record-count").label, "1 רשומות", "הטוגל לא ביטל את הסינון")

        // מעבר לכיוון תשלום — הכפתורים מחליפים נוסח והשורות מתחלפות.
        app.buttons["תשלום"].firstMatch.tap()
        waitFor(app.buttons["payments-status-overdue"])
        XCTAssertEqual(app.buttons["payments-status-overdue"].label, "מועד התשלום חלף")
        XCTAssertEqual(app.buttons["payments-status-paid"].label, "שולם")
        waitForRows("payments_transfer")
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "ארוטקס")).firstMatch
                .waitForExistence(timeout: 6),
            "שורת התשלום של ארוטקס לא מוצגת בכיוון תשלום"
        )
    }

    // MARK: - חשבונית "טרם שולמה" מצטרפת ל"לתשלום"

    func testUnpaidInvoiceJoinsPayablesTable() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("invoice-upload"), timeout: 6)
        waitFor(app.buttons["invoice-sample-file"]).tap()
        waitFor(element("invoice-unpaid-toggle"), timeout: 10)

        // מדליקים "טרם שולמה" ושומרים.
        app.switches["invoice-unpaid-toggle"].firstMatch.switches.firstMatch.tap()
        scrollAndTap(app.buttons["invoice-save-draft"])
        waitFor(element("invoice-saved-badge"), timeout: 8)
        app.buttons["invoice-upload-close"].tap()

        // השורה החדשה בטבלת לתשלום (כיוון תשלום), עם החשבונית.
        tapChip("payments_transfer")
        waitForRows("payments_transfer")
        app.buttons["תשלום"].firstMatch.tap()
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("INV-777")
        XCTAssertTrue(app.buttons["row-payments_transfer"].firstMatch.waitForExistence(timeout: 8),
                      "החשבונית שסומנה טרם שולמה לא הצטרפה ללתשלום")
    }

    // MARK: - סוגי לקוחות ומיון

    func testCustomerTypeFilterAndAlphabeticalSort() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        let allCount = element("record-count").label

        // סינון טקסטיל — נשארות רק שורות הטקסטיל.
        waitFor(app.buttons["customer-type-textile"]).tap()
        waitForRows("customers")
        XCTAssertNotEqual(element("record-count").label, allCount, "הסינון לא צמצם")

        // ללא שיוך — ב-fixtures לכולם יש תחום ⇒ רשימה ריקה.
        app.buttons["customer-type-none"].tap()
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "אין נתונים")).firstMatch
                .waitForExistence(timeout: 5)
        )

        // ביטול (טוגל) — חוזרים לכולם, ממוינים אלפביתית.
        app.buttons["customer-type-none"].tap()
        waitForRows("customers")
        XCTAssertEqual(element("record-count").label, allCount)
        let firstTitle = app.buttons["row-customers"].firstMatch.label
        XCTAssertTrue(firstTitle.hasPrefix("א"), "המיון אלפביתי — הראשון: \(firstTitle)")
    }

    // MARK: - חמשת הפערים מהפיצוץ

    func testComposerDadAndInstallationToggles() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("order-composer"), timeout: 6)
        waitFor(app.buttons["composer-sample-file"]).tap()
        waitFor(app.textFields["composer-field-customer_name"], timeout: 10)

        // "שלח גם לאבא" מופיע רק כשוואטסאפ דלוק.
        XCTAssertFalse(element("composer-dad-toggle").exists)
        app.switches["composer-whatsapp-toggle"].firstMatch.switches.firstMatch.tap()
        waitFor(element("composer-dad-toggle"), timeout: 4)

        // טוגל "דורשת התקנה" קיים ליד החנייה.
        var attempts = 0
        while !element("composer-installation-toggle").isHittable && attempts < 8 {
            app.swipeUp(); attempts += 1
        }
        waitFor(element("composer-installation-toggle"))
    }

    func testInstallationsStatusFilter() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapChip("installation_cases")
        waitForRows("installation_cases")
        let before = element("record-count").label

        // צ'יפ "בוטל" — לחיצה מסננת (firstMatch מבין ששת הצ'יפים).
        let cancelChip = app.buttons.matching(NSPredicate(format: "label == %@", "בוטל")).firstMatch
        waitFor(cancelChip).tap()
        // ה-fixtures לא כוללים תיק שבוטל — הרשימה מתרוקנת, וזה מוכיח שהסינון עובד.
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "אין נתונים")).firstMatch
                .waitForExistence(timeout: 5) || element("record-count").label != before,
            "הסינון לא השפיע על הרשימה"
        )
        // לחיצה נוספת מבטלת (טוגל).
        cancelChip.tap()
        waitForRows("installation_cases")
    }

    func testReminderChannelPicker() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-marketing"]).tap()
        waitForRows("marketing_pipeline")
        tapChip("marketing_reminders")
        waitForRows("marketing_reminders")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        // בורר הערוץ קיים עם ברירת מחדל טלפון.
        let channel = waitFor(element("form-channel"))
        XCTAssertTrue(channel.label.contains("טלפון"), "ברירת המחדל: \(channel.label)")
        channel.tap()
        waitFor(app.buttons["ווטסאפ"].firstMatch).tap()
        let name = app.textFields["form-customer_name"]
        name.tap()
        name.typeText("לקוח ערוץ TEST")
        let date = app.textFields["form-due_date"]
        date.tap()
        date.typeText("2030-01-01")
        scrollAndTap(app.buttons["form-save"])
        waitFor(element("toast"), timeout: 8)
    }

    func testAccountantSummarySheet() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")
        waitFor(app.buttons["accountant-send-open"]).tap()
        waitFor(element("accountant-send-sheet"), timeout: 6)

        // בחירת מועד דיווח מה-fixtures + טוגל המע"מ.
        waitFor(app.buttons["accountant-due-15-01-2026"]).tap()
        let vat = app.switches["accountant-vat-toggle"].firstMatch
        if !vat.isHittable { app.swipeUp() }
        vat.switches.firstMatch.tap()
        // מצב בדיקה דלוק כברירת מחדל — שולחים.
        XCTAssertEqual(app.switches["accountant-test-toggle"].firstMatch.value as? String, "1")
        waitFor(app.buttons["accountant-send-submit"]).tap()
        waitFor(element("toast"), timeout: 8)
    }

    // MARK: - נעילה אופטימית: קונפליקט עריכה מקבילה

    func testPaymentsConflictShowsErrorRefreshesAndRetrySucceeds() {
        launchApp(extraEnvironment: ["BY_UITEST_PAYMENTS_CONFLICT": "1"])
        tapTab("כספים")
        waitForRows("payments_transfer")
        app.buttons["row-payments_transfer"].firstMatch.tap()
        waitFor(element("record-detail"))

        // ניסיון ראשון — "מישהו אחר" עדכן במקביל: 409, הודעה ורענון.
        waitFor(app.buttons["action-toggle-paid"]).tap()
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "מישהו אחר עדכן")).firstMatch
                .waitForExistence(timeout: 8),
            "חסרה הודעת קונפליקט"
        )

        // ניסיון שני עם הנתונים המרועננים — מצליח.
        waitFor(app.buttons["action-toggle-paid"], timeout: 6).tap()
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "סומן")).firstMatch
                .waitForExistence(timeout: 8),
            "הניסיון החוזר אחרי הקונפליקט לא הצליח"
        )
    }

    // MARK: - עדכון חי של טבלת החשבוניות

    func testFinanceInvoicesLiveUpdateWithoutManualRefresh() {
        // תרחיש: בזמן שהמסך פתוח, "מישהו" שומר חשבונית מהנייד/מהדסקטופ —
        // ה-watch מזהה את שינוי ה-epoch והטבלה מתעדכנת בלי משיכה לרענון.
        launchApp(extraEnvironment: ["BY_UITEST_EPOCH_DEMO": "1"])
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")

        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("עדכון חי")

        // השורה עוד לא קיימת — היא "תישמר מרחוק" אחרי כמה שניות.
        let newRow = app.buttons["row-finance_invoices"].firstMatch
        XCTAssertTrue(newRow.waitForExistence(timeout: 20),
                      "החשבונית שנשמרה מרחוק לא הופיעה אוטומטית בטבלה")
    }

    // MARK: - צפיינים

    func testSupplierNoteSourceViewer() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-inventory"]).tap()
        waitForRows("inventory_purchase_orders")
        tapChip("supplier_delivery_notes")
        waitForRows("supplier_delivery_notes")
        app.buttons["row-supplier_delivery_notes"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(app.buttons["supplier-note-view"]).tap()
        waitFor(element("document-pdf"), timeout: 10)
        waitFor(app.buttons["document-close"]).tap()
    }

    func testWorkingOrderNoteFileViewer() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(app.buttons["working-order-note-file"]).tap()
        waitFor(element("document-pdf"), timeout: 10)
        waitFor(app.buttons["document-close"]).tap()
    }

    // MARK: - יצירת הזמנה מתוך הזמנות בעבודה

    func testWorkingOrderCreateOrderFullFlow() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)

        // כפתור "יצירת הזמנה" בפירוט — פותח את הקומפוזר ישר בשלב העריכה.
        waitFor(app.buttons["working-order-create"]).tap()
        waitFor(element("order-composer"), timeout: 6)
        let nameField = waitFor(app.textFields["composer-field-customer_name"])
        XCTAssertTrue((nameField.value as? String)?.contains("דמרי") == true,
                      "פרטי ההזמנה לא נטענו מה-payload: \(String(describing: nameField.value))")
        XCTAssertTrue(element("composer-total").exists, "סכום ההזמנה לא מוצג")
        // אין כפתור "שמירה להזמנות בעבודה" — ההזמנה כבר שם.
        XCTAssertFalse(app.buttons["composer-park"].exists, "כפתור השמירה לעבודה לא אמור להופיע כאן")

        // יצירה בפרודקשן — כמו בדסקטופ, השורה יורדת אוטומטית מ"בעבודה".
        waitFor(app.buttons["פרודקשן"].firstMatch).tap()
        scrollAndTap(app.buttons["composer-finalize"])
        waitFor(element("composer-done"), timeout: 12)
        app.buttons["composer-done-close"].tap()

        // הרענון מסיר את הרשומה ומסך הפירוט נסגר מעצמו — מחכים שהשורה תיעלם.
        let row = app.buttons["row-working_orders"].firstMatch
        let deadline = Date().addingTimeInterval(10)
        while row.exists && Date() < deadline { usleep(300_000) }
        XCTAssertFalse(row.exists, "ההזמנה בעבודה לא הוסרה אחרי finalize בפרודקשן")
    }

    // MARK: - הלוואות ומשכנתאות + צי רכבים

    func testLoansScreenShowsCardsTotalsAndDocViewer() {
        launchApp()
        tapTab("עוד")
        scrollAndTap(app.buttons["more-loans"])
        waitFor(element("loans-screen"), timeout: 8)

        // סיכומי היתרות והכרטיסים מה-mock.
        waitFor(element("loans-totals"))
        let cards = app.descendants(matching: .any).matching(identifier: "loan-card")
        XCTAssertTrue(cards.firstMatch.waitForExistence(timeout: 6), "לא הופיעו כרטיסי הלוואות")
        XCTAssertTrue(app.staticTexts["₪ 382,559.42"].waitForExistence(timeout: 4),
                      "היתרה המחושבת לא מוצגת")
        XCTAssertTrue(app.staticTexts["הלוואה 400,000"].exists, "כותרת ההלוואה חסרה")
        XCTAssertTrue(app.staticTexts["משכנתא - הגורן 34, עתלית"].exists, "כרטיס המשכנתא חסר")

        // קרא עוד — פירוט ההלוואה נפתח.
        waitFor(app.buttons["loan-read-more"].firstMatch).tap()
        let accountDetail = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "253594555")).firstMatch
        XCTAssertTrue(accountDetail.waitForExistence(timeout: 4),
                      "פרטי החשבון לא נחשפו אחרי קרא עוד")

        // פתיחת מסמך — הצפיין הנייטיבי עולה עם ה-PDF.
        waitFor(app.buttons["lending-doc-open"].firstMatch).tap()
        waitFor(element("document-pdf"), timeout: 10)
        waitFor(app.buttons["document-close"]).tap()
    }

    func testVehiclesScreenShowsFleetAndDocViewer() {
        launchApp()
        tapTab("עוד")
        scrollAndTap(app.buttons["more-vehicles"])
        waitFor(element("vehicles-screen"), timeout: 8)

        let cards = app.descendants(matching: .any).matching(identifier: "vehicle-card")
        XCTAssertTrue(cards.firstMatch.waitForExistence(timeout: 6), "לא הופיעו כרטיסי רכבים")
        XCTAssertTrue(app.staticTexts["קיה נירו אפורה"].waitForExistence(timeout: 4),
                      "כרטיס הרכב הראשון שגוי")
        XCTAssertTrue(app.staticTexts["הפניקס"].exists, "פרטי הביטוח חסרים")
        let plate = app.staticTexts.matching(NSPredicate(format: "label == %@", "13578301")).firstMatch
        XCTAssertTrue(plate.exists, "מספר הרכב חסר")

        waitFor(app.buttons["lending-doc-open"].firstMatch).tap()
        waitFor(element("document-pdf"), timeout: 10)
        waitFor(app.buttons["document-close"]).tap()
    }

    // MARK: - חשבוניות ספקים: מיון + סינון לפי מועד דיווח

    func testFinanceInvoicesDefaultSortAndSortMenu() {
        launchApp()
        tapTab("כספים")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")

        let rows = app.buttons.matching(identifier: "row-finance_invoices")
        // ברירת מחדל: תאריך מהחדש לישן — פלאקסי (31/05/2026) ראשונה.
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("פלאקסי"),
                      "השורה הראשונה אינה החשבונית האחרונה: \(rows.element(boundBy: 0).label)")

        // סכום — מהגבוה לנמוך: פז 3,579.28 (31/07/2025) עוברת לראש.
        waitFor(element("finance-sort-menu")).tap()
        waitFor(app.buttons["סכום — מהגבוה לנמוך"]).tap()
        waitForRows("finance_invoices")
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("פז"),
                      "מיון סכום יורד לא העלה את החשבונית הגבוהה: \(rows.element(boundBy: 0).label)")

        // סכום — מהנמוך לגבוה: שורת Google Ads בלי סכום ראשונה.
        element("finance-sort-menu").tap()
        waitFor(app.buttons["סכום — מהנמוך לגבוה"]).tap()
        waitForRows("finance_invoices")
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("Google Ads"),
                      "מיון סכום עולה לא העלה את הסכום הנמוך: \(rows.element(boundBy: 0).label)")

        // ספק — אלפביתי: פז לפני פלאקסי (ז לפני ל), ולטינית אחרי העברית.
        element("finance-sort-menu").tap()
        waitFor(app.buttons["ספק — לפי א׳-ב׳ / ABC"]).tap()
        waitForRows("finance_invoices")
        XCTAssertTrue(rows.element(boundBy: 0).label.contains("פז"),
                      "מיון ספקים לא סידר אלפביתית: \(rows.element(boundBy: 0).label)")
    }

    func testFinanceInvoicesReportDateFilterChips() {
        launchApp()
        tapTab("כספים")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")
        XCTAssertTrue(waitFor(element("record-count")).label.contains("6"),
                      "ציפינו ל-6 חשבוניות בפיקסטורה: \(element("record-count").label)")

        // סינון למועד דיווח 15/01/2026 — שתי חשבוניות מסומנות אליו.
        // ה-label כולל תווי bidi isolate מהאינטרפולציה של SwiftUI, לכן CONTAINS.
        let januaryChip = app.buttons.matching(identifier: "finance-report-filter")
            .matching(NSPredicate(format: "label CONTAINS %@", "15.1.26")).firstMatch
        waitFor(januaryChip).tap()
        waitForRows("finance_invoices")
        XCTAssertTrue(waitFor(element("record-count")).label.contains("2"),
                      "סינון הדיווח לא צמצם לשתי חשבוניות: \(element("record-count").label)")

        // הקשה חוזרת מבטלת את הסינון — כמו בדסקטופ.
        januaryChip.tap()
        waitForRows("finance_invoices")
        XCTAssertTrue(waitFor(element("record-count")).label.contains("6"),
                      "ביטול הסינון לא החזיר את כל החשבוניות: \(element("record-count").label)")
    }
}
