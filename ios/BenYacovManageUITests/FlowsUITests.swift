import XCTest

/// E2E לזרימות העסקיות המלאות — מהמסך ועד הדאטה.
final class FlowsUITests: BYUITestCase {

    // MARK: - הזמנת רכש

    func testOrderComposerFullFlow() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("order-composer"), timeout: 6)

        // טעינת קובץ לדוגמה ופרסור.
        waitFor(app.buttons["composer-sample-file"]).tap()
        waitFor(app.textFields["composer-field-customer_name"], timeout: 10)
        // ההזמנה פורסרה עם נתונים.
        let nameField = app.textFields["composer-field-customer_name"]
        XCTAssertTrue((nameField.value as? String)?.contains("דמרי") == true,
                      "שם הלקוח המפורסר לא הופיע: \(String(describing: nameField.value))")
        waitFor(element("composer-total"))

        // עריכת שדה לפני יצירה.
        let poField = app.textFields["composer-field-po_number"]
        poField.tap()
        poField.typeText("7")

        // יצירת מסמכים בסנדבוקס (בלי וואטסאפ — ברירת המחדל).
        waitFor(app.buttons["composer-finalize"]).tap()
        waitFor(element("composer-done"), timeout: 12)
        let doneText = element("composer-done-message").label
        XCTAssertTrue(doneText.contains("המסמכים נוצרו"), "הודעת הסיום: \(doneText)")
        app.buttons["composer-done-close"].tap()

        // ההזמנה החדשה מופיעה בהיסטוריית ההזמנות.
        tapChip("order_history")
        waitForRows("order_history")
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("1129997")
        waitForRows("order_history")
    }

    func testOrderComposerWhatsappToggle() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("order-composer"), timeout: 6)
        waitFor(app.buttons["composer-sample-file"]).tap()
        waitFor(app.textFields["composer-field-customer_name"], timeout: 10)

        // הפעלת שליחה בוואטסאפ ויצירה — הודעת הסיום משקפת שליחה.
        let toggle = app.switches["composer-whatsapp-toggle"].firstMatch
        var attempts = 0
        while !toggle.isHittable && attempts < 6 {
            app.swipeUp()
            attempts += 1
        }
        toggle.tap()
        waitFor(app.buttons["composer-finalize"]).tap()
        waitFor(element("composer-done"), timeout: 12)
        XCTAssertTrue(element("composer-done-message").label.contains("וואטסאפ"))
        app.buttons["composer-done-close"].tap()
    }

    /// בוחר הקבצים של המערכת באמת נפתח מכפתור ההעלאה.
    func testOrderComposerOpensRealFilePicker() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("order-composer"), timeout: 6)
        waitFor(app.buttons["composer-pick-file"]).tap()
        // בוחר המסמכים של iOS עולה (תהליך חיצוני שמוצג בתוך האפליקציה).
        let cancel = app.buttons["Cancel"].firstMatch.exists
            ? app.buttons["Cancel"].firstMatch
            : app.buttons["ביטול"].firstMatch
        XCTAssertTrue(cancel.waitForExistence(timeout: 10), "בוחר הקבצים לא נפתח")
        cancel.tap()
        // חזרה למסך הבחירה.
        waitFor(app.buttons["composer-pick-file"], timeout: 6)
        app.buttons["composer-close"].tap()
    }

    // MARK: - חשבוניות

    func testInvoiceUploadParseAndSaveToFinance() {
        launchApp()
        tapTab("כספים")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("invoice-upload"), timeout: 6)

        waitFor(app.buttons["invoice-sample-file"]).tap()
        // הטיוטה פורסרה עם ספק וסכומים.
        waitFor(app.textFields["invoice-field-supplier_name"], timeout: 10)
        let supplierField = app.textFields["invoice-field-supplier_name"]
        XCTAssertTrue((supplierField.value as? String)?.contains("ספק בדיקה") == true)

        // שמירה לטבלת הכספים.
        waitFor(app.buttons["invoice-save-draft"]).tap()
        waitFor(element("invoice-saved-badge"), timeout: 10)
        app.buttons["invoice-upload-close"].tap()

        // החשבונית מופיעה בטאב כספים.
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("INV-777")
        waitForRows("finance_invoices")
    }

    // MARK: - אישור מסירה

    func testDeliveryConfirmationSendInTestMode() {
        launchApp()
        tapTab("הזמנות")
        tapChip("delivery_confirmations")
        waitForRows("delivery_confirmations")
        app.buttons["row-delivery_confirmations"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["delivery-send-open"]).tap()
        waitFor(element("delivery-send-sheet"), timeout: 6)

        // מצב בדיקה דולק כברירת מחדל — השליחה אליי בלבד.
        let toggle = app.switches["delivery-send-test-toggle"].firstMatch
        XCTAssertEqual(toggle.value as? String, "1", "מצב בדיקה חייב להיות דלוק כברירת מחדל")

        // הנושא ממולא בנוסח הקנוני של הדסקטופ.
        let subjectValue = app.textFields["delivery-send-subject"].value as? String ?? ""
        XCTAssertTrue(subjectValue.contains("מצורפת חשבונית"),
                      "נושא המייל חייב להיות בנוסח הדסקטופ, התקבל: \(subjectValue)")
        XCTAssertTrue(subjectValue.contains("מבן יעקב פתרונות טקסטיל"),
                      "חסרה חתימת החברה בנושא: \(subjectValue)")

        waitFor(app.buttons["delivery-send-submit"]).tap()
        waitFor(element("toast"), timeout: 10)
        app.buttons["close-detail"].tap()
    }

    /// העלאת תעודה חתומה מהמסך: אזהרה → העלאה → הקובץ מוצג → מחיקה → האזהרה חוזרת.
    func testSignedDeliveryUploadAndDeleteFlow() {
        launchApp()
        tapTab("הזמנות")
        tapChip("delivery_confirmations")
        waitForRows("delivery_confirmations")

        // שורת בדיקה ייעודית בלי תעודה חתומה.
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("NOSIGN")
        waitForRows("delivery_confirmations")
        app.buttons["row-delivery_confirmations"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(element("signed-upload-card"))

        // אין תעודה → מוצגת אזהרת שליחה.
        waitFor(element("delivery-send-warning"), timeout: 4)

        // העלאה.
        waitFor(app.buttons["signed-sample-upload"]).tap()
        waitFor(element("toast"), timeout: 10)
        waitFor(element("signed-file-name"), timeout: 8)
        // האזהרה נעלמה — השורה כשירה לשליחה.
        XCTAssertFalse(element("delivery-send-warning").exists,
                       "האזהרה אמורה להיעלם אחרי העלאת תעודה")

        // מחיקה.
        waitFor(app.buttons["signed-delete"]).tap()
        waitFor(app.buttons["signed-delete-confirm"].firstMatch, timeout: 6).tap()
        waitFor(element("delivery-send-warning"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    // MARK: - התקנות

    func testInstallationsListAndStatusChange() {
        launchApp()
        tapTab("הזמנות")
        tapChip("installation_cases")
        waitForRows("installation_cases")
        app.buttons["row-installation_cases"].firstMatch.tap()
        waitFor(element("record-detail"))

        // שינוי סטטוס דרך התפריט.
        waitFor(element("installation-status-menu")).tap()
        waitFor(app.buttons["תואם"].firstMatch, timeout: 4).tap()
        waitFor(app.buttons["installation-save-status"]).tap()
        waitFor(element("toast"), timeout: 8)
        app.buttons["close-detail"].tap()
    }

    func testInstallationAddVisit() {
        launchApp()
        tapTab("הזמנות")
        tapChip("installation_cases")
        waitForRows("installation_cases")
        app.buttons["row-installation_cases"].firstMatch.tap()
        waitFor(element("record-detail"))

        var attempts = 0
        let addVisit = app.buttons["installation-add-visit"]
        while !addVisit.isHittable && attempts < 6 {
            app.swipeUp()
            attempts += 1
        }
        addVisit.tap()
        waitFor(element("visit-form"), timeout: 6)

        // הוספת כמות לפריט הראשון אם קיים.
        let plus = app.buttons["visit-item-plus"].firstMatch
        if plus.waitForExistence(timeout: 3) {
            plus.tap()
        }
        waitFor(app.buttons["visit-save"]).tap()
        waitFor(element("toast"), timeout: 10)
        app.buttons["close-detail"].tap()
    }

    // MARK: - שיוך תחום

    func testAssignCustomerToDomain() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        app.buttons["row-customers"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(element("customer-domain-menu")).tap()
        waitFor(app.buttons["תחום הבנייה"].firstMatch, timeout: 4).tap()
        waitFor(element("toast"), timeout: 10)
        // התחום המעודכן מוצג בכרטיס.
        XCTAssertTrue(
            app.staticTexts["תחום הבנייה"].firstMatch.waitForExistence(timeout: 6),
            "התחום החדש לא מוצג אחרי השיוך"
        )
        app.buttons["close-detail"].tap()
    }

    // MARK: - מסמכים

    func testMarketingDocPreviewOpensNatively() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-documents"], timeout: 6).tap()
        waitFor(element("documents-screen"), timeout: 8)
        waitFor(app.buttons["marketing-doc-preview"].firstMatch, timeout: 8).tap()
        waitFor(element("document-preview"), timeout: 8)
        // התמונה נטענה מקומית (PNG מהשרת).
        waitFor(element("document-image"), timeout: 8)
        app.buttons["document-close"].tap()
    }

    func testAdminDocSendInTestMode() {
        launchApp()
        tapTab("עוד")
        waitFor(app.buttons["more-documents"], timeout: 6).tap()
        waitFor(element("documents-screen"), timeout: 8)
        let sendButton = app.buttons["admin-doc-send"].firstMatch
        var attempts = 0
        while !sendButton.isHittable && attempts < 8 {
            app.swipeUp()
            attempts += 1
        }
        sendButton.tap()
        waitFor(element("admin-send-sheet"), timeout: 6)
        let toggle = app.switches["admin-send-test-toggle"].firstMatch
        XCTAssertEqual(toggle.value as? String, "1", "מצב בדיקה חייב להיות דלוק כברירת מחדל")
        waitFor(app.buttons["admin-send-submit"]).tap()
        waitFor(element("toast"), timeout: 10)
    }

    func testInvoiceFileOpensInNativeViewer() {
        launchApp()
        tapTab("כספים")
        tapChip("finance_invoices")
        waitForRows("finance_invoices")
        app.buttons["row-finance_invoices"].firstMatch.tap()
        waitFor(element("record-detail"))
        waitFor(app.buttons["invoice-view-file"]).tap()
        waitFor(element("document-preview"), timeout: 8)
        waitFor(element("document-pdf"), timeout: 8)
        app.buttons["document-close"].tap()
        app.buttons["close-detail"].tap()
    }
}
