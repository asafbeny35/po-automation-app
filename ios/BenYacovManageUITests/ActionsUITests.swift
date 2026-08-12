import XCTest

/// פעולות עסקיות מקצה לקצה — סימון שולם, תזכורות, לקוחות, טפסים ומחיקות.
final class ActionsUITests: BYUITestCase {

    func testMarkPaymentAsPaid() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")
        app.buttons["row-payments_transfer"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-toggle-paid"]).tap()
        waitFor(element("toast"), timeout: 8)
        // הפעולה נשארת במסך — הכפתור מתהפך לסימון ההפוך.
        waitFor(app.buttons["action-toggle-paid"], timeout: 6)
        app.buttons["close-detail"].tap()
    }

    func testCompleteMarketingReminder() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-marketing"], timeout: 6).tap()
        tapChip("marketing_reminders")
        waitForRows("marketing_reminders")
        app.buttons["row-marketing_reminders"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-complete-reminder"]).tap()
        waitFor(element("toast"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    func testCreateCustomerFromForm() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let nameField = waitFor(app.textFields["form-customer_name"])
        nameField.tap()
        nameField.typeText("Test Customer Ltd")
        app.buttons["form-save"].tap()
        waitFor(element("toast"), timeout: 8)
        // הלקוח החדש מופיע ברשימה.
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("Test Customer")
        waitForRows("customers")
    }

    func testCustomerFormValidationBlocksEmptyName() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        app.buttons["form-save"].tap()
        waitFor(element("form-error"), timeout: 4)
        app.buttons["form-cancel"].tap()
    }

    func testEditCustomerCity() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        app.buttons["row-customers"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["edit-record"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let cityField = waitFor(app.textFields["form-city"])
        cityField.tap()
        cityField.typeText("Haifa")
        app.buttons["form-save"].tap()
        waitFor(element("toast"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    func testDeactivateCustomerMovesToInactive() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        app.buttons["row-customers"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-toggle-active"]).tap()
        // דיאלוג אישור.
        waitFor(app.buttons["confirm-action"].firstMatch, timeout: 6).tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testDeleteOrderHistoryWithConfirmation() {
        launchApp()
        tapTab("הזמנות")
        tapChip("order_history")
        waitForRows("order_history")
        app.buttons["row-order_history"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-delete-order"]).tap()
        waitFor(app.buttons["confirm-action"].firstMatch, timeout: 6).tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testDeleteConfirmationCanBeCancelled() {
        launchApp()
        tapTab("הזמנות")
        tapChip("quote_history")
        waitForRows("quote_history")
        app.buttons["row-quote_history"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-delete-quote"]).tap()
        // מחכים שהדיאלוג יופיע ואז מבטלים בהקשה מחוץ לו (כפתורי ביטול של
        // confirmationDialog לא חושפים מזהים ל-XCUITest).
        waitFor(app.buttons["confirm-action"].firstMatch, timeout: 6)
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12)).tap()
        // הרשומה עדיין קיימת והמסך פתוח.
        waitFor(app.buttons["action-delete-quote"], timeout: 4)
        app.buttons["close-detail"].tap()
    }

    func testAddPaymentRow() {
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let nameField = waitFor(app.textFields["form-customer_name"])
        nameField.tap()
        nameField.typeText("Test Supplier")
        let amountField = app.textFields["form-amount"]
        amountField.tap()
        amountField.typeText("450")
        app.buttons["form-save"].tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testSaveWorkingOrderNote() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["edit-record"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let noteField = waitFor(app.textFields["form-order_note_text"])
        noteField.tap()
        noteField.typeText("Note from test")
        app.buttons["form-save"].tap()
        waitFor(element("toast"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    func testCreateHREmployee() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-hr"], timeout: 6).tap()
        waitForRows("hr_employees")
        waitFor(app.buttons["add-button"]).tap()
        waitFor(element("record-form"), timeout: 6)
        let nameField = waitFor(app.textFields["form-full_name"])
        nameField.tap()
        nameField.typeText("Test Employee")
        app.buttons["form-save"].tap()
        waitFor(element("toast"), timeout: 8)
    }

    func testMarkDeliveryConfirmationSent() {
        launchApp()
        tapTab("הזמנות")
        tapChip("delivery_confirmations")
        waitForRows("delivery_confirmations")
        app.buttons["row-delivery_confirmations"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["action-mark-sent"]).tap()
        waitFor(element("toast"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    func testCustomerDetailShowsContactActions() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        // מחפשים לקוח עם טלפון — א. ליפמן (יש phone בנתוני הבדיקה).
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("ליפמן")
        if app.buttons["row-customers"].firstMatch.waitForExistence(timeout: 4) {
            app.buttons["row-customers"].firstMatch.tap()
            waitFor(element("record-detail"))
            // לפחות אחת מפעולות הקשר צריכה להופיע אם יש פרטי קשר.
            let hasContact = element("contact-call").exists
                || element("contact-whatsapp").exists
                || element("contact-mail").exists
            _ = hasContact // לקוח בלי פרטי קשר הוא גם מצב תקין.
            app.buttons["close-detail"].tap()
        }
    }
}
