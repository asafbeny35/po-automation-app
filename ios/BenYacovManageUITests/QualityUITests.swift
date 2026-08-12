import XCTest

/// איכות רוחבית: זמן עלייה, עומס, הגשה כפולה, עמידות לשרת שבור ונגישות.
final class QualityUITests: BYUITestCase {

    // MARK: - מהירות: זמן עליית האפליקציה

    func testLaunchPerformance() {
        let metrics: [XCTMetric] = [XCTApplicationLaunchMetric()]
        measure(metrics: metrics) {
            let app = XCUIApplication()
            app.launchEnvironment["BY_UITEST"] = "1"
            app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
            app.launch()
            app.terminate()
        }
    }

    // MARK: - עומס: 3,000 שורות ברשימה אחת

    func testHugeListRendersSearchesAndScrolls() {
        launchApp(extraEnvironment: ["BY_UITEST_BIG_DOMAIN": "payments_transfer"])
        tapTab("כספים")
        // הרשימה חייבת לעלות גם עם אלפי שורות — בתקציב זמן סביר.
        let firstRow = app.buttons["row-payments_transfer"].firstMatch
        XCTAssertTrue(firstRow.waitForExistence(timeout: 20), "הרשימה לא עלתה עם 3,000 שורות")

        // גלילה נשארת חלקה מספיק כדי להגיב (בלי קפיאה).
        for _ in 0..<5 { app.swipeUp() }
        for _ in 0..<2 { app.swipeDown() }

        // חיפוש מצמצם לשורה ספציפית מתוך האלפים.
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("LOAD-2999")
        XCTAssertTrue(firstRow.waitForExistence(timeout: 10), "החיפוש לא מצא את שורת העומס")
        XCTAssertEqual(element("record-count").label, "1 רשומות")
    }

    // MARK: - שפיות: דאבל-טאפ לא יוצר הזמנה כפולה

    func testDoubleTapFinalizeCreatesSingleOrder() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        waitFor(app.buttons["flow-button"]).tap()
        waitFor(element("order-composer"), timeout: 6)
        waitFor(app.buttons["composer-sample-file"]).tap()
        waitFor(app.textFields["composer-field-customer_name"], timeout: 10)

        // מספר הזמנה ייחודי כדי לספור בדיוק כמה רשומות נוצרו.
        let uniquePO = "DBL-\(Int(Date().timeIntervalSince1970))"
        let poField = app.textFields["composer-field-po_number"]
        poField.tap()
        poField.press(forDuration: 1.0)
        if app.menuItems["Select All"].waitForExistence(timeout: 2) {
            app.menuItems["Select All"].tap()
        }
        poField.typeText(uniquePO)

        // שתי הקשות מהירות על יצירת המסמכים. אחרי הראשונה הכפתור אמור
        // להיעלם/להינעל — אם הוא עדיין שם, מקישים שוב כדי לוודא שאין כפילות.
        let finalize = waitFor(app.buttons["composer-finalize"])
        finalize.tap()
        if finalize.waitForExistence(timeout: 0.3), finalize.isHittable {
            finalize.tap()
        }
        waitFor(element("composer-done"), timeout: 12)
        app.buttons["composer-done-close"].tap()

        // בדיוק רשומה אחת בהיסטוריה עם המספר הייחודי.
        tapChip("order_history")
        waitForRows("order_history")
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText(uniquePO)
        XCTAssertTrue(app.buttons["row-order_history"].firstMatch.waitForExistence(timeout: 8))
        XCTAssertEqual(element("record-count").label, "1 רשומות",
                       "דאבל-טאפ יצר יותר מהזמנה אחת!")
    }

    // MARK: - עמידות: שרת מחזיר JSON שבור

    func testGarbageServerResponseShowsErrorStateNotCrash() {
        launchApp(extraEnvironment: ["BY_UITEST_GARBAGE_DOMAIN": "customers"])
        tapTab("לקוחות")
        // מסך שגיאה מסודר עם "נסה שוב" — והאפליקציה עצמה חיה.
        XCTAssertTrue(retryButton().waitForExistence(timeout: 10),
                      "JSON שבור חייב להוביל למסך שגיאה עם ניסיון חוזר")
        // ניווט לטאב אחר עדיין עובד — האפליקציה לא קרסה.
        tapTab("כספים")
        waitForRows("payments_transfer")
    }

    // MARK: - חיווי: לכל כפתור אינטראקטיבי יש תווית ל-VoiceOver

    func testInteractiveButtonsHaveAccessibilityLabels() {
        launchApp()
        var offenders: [String] = []

        func sweep(_ screen: String) {
            for button in app.buttons.allElementsBoundByIndex.prefix(60) {
                guard button.exists, button.frame.width > 1 else { continue }
                let identifier = button.identifier
                // בודקים את הכפתורים שלנו (עם מזהה) — הם חייבים גם תווית קולית.
                guard !identifier.isEmpty, button.label.isEmpty else { continue }
                offenders.append("\(screen): \(identifier)")
            }
        }

        sweep("בית")
        tapTab("הזמנות")
        waitForRows("working_orders")
        sweep("הזמנות")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"))
        sweep("פירוט")
        app.buttons["close-detail"].tap()
        tapTab("כספים")
        waitForRows("payments_transfer")
        sweep("כספים")

        XCTAssertTrue(offenders.isEmpty,
                      "כפתורים בלי תווית ל-VoiceOver:\n" + offenders.joined(separator: "\n"))
    }

    // MARK: - אייפד: רוטציה לרוחב ובחזרה

    func testIPadLandscapeRotationKeepsAppFunctional() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("רוטציה חופשית נתמכת רק באייפד — באייפון האפליקציה נעולה לאורך")
        }
        launchApp()
        tapTab("כספים")
        waitForRows("payments_transfer")

        XCUIDevice.shared.orientation = .landscapeLeft
        // הרשימה חיה גם לרוחב: פתיחת פירוט, סגירה וחיפוש.
        waitForRows("payments_transfer")
        openAndCloseFirstRecord("payments_transfer")
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("550583")
        waitForRows("payments_transfer")

        XCUIDevice.shared.orientation = .portrait
        waitForRows("payments_transfer")
    }

    // MARK: - Face ID (אייפון בלבד)

    func testFaceIDLockBlocksUntilUnlock() throws {
        guard UIDevice.current.userInterfaceIdiom == .phone else {
            throw XCTSkip("Face ID — פיצ'ר אייפון בלבד")
        }
        // אימות נכשל ⇒ המסך נשאר נעול והתוכן חסום.
        launchApp(extraEnvironment: [
            "BY_UITEST_FACE_ID_ENABLED": "1",
            "BY_UITEST_FACE_ID": "fail",
        ])
        waitFor(element("biometric-lock-screen"), timeout: 8)
        waitFor(app.buttons["biometric-unlock"]).tap()
        waitFor(element("biometric-failed"), timeout: 6)
        XCTAssertTrue(element("biometric-lock-screen").exists, "אחרי כשל — עדיין נעול")

        // הבדיקה שחשובה באמת: הקשה "מבעד" לנעילה לא מפעילה שום דבר מאחור.
        let tile = app.buttons["home-domain-order_history"].firstMatch
        if tile.exists { tile.tap() }
        XCTAssertFalse(element("domain-list-order_history").waitForExistence(timeout: 2),
                       "הקשה מבעד לנעילה ניווטה לתוכן — פרצת אבטחה!")
        XCTAssertTrue(element("biometric-lock-screen").exists, "המסך הנעול נשאר במקומו")
    }

    func testFaceIDUnlockSuccessOpensApp() throws {
        guard UIDevice.current.userInterfaceIdiom == .phone else {
            throw XCTSkip("Face ID — פיצ'ר אייפון בלבד")
        }
        launchApp(extraEnvironment: ["BY_UITEST_FACE_ID_ENABLED": "1"])
        // האימות האוטומטי בעלייה מצליח — התוכן נפתח.
        if element("biometric-lock-screen").waitForExistence(timeout: 2) {
            if app.buttons["biometric-unlock"].exists {
                app.buttons["biometric-unlock"].tap()
            }
        }
        waitFor(element("home-domain-order_history"), timeout: 8)
    }

    func testFaceIDToggleOnlyOnPhone() {
        launchApp()
        tapTab("עוד")
        waitFor(element("more-screen"), timeout: 6)
        var attempts = 0
        while !app.switches["faceid-toggle"].firstMatch.exists && attempts < 8 {
            app.swipeUp(); attempts += 1
        }
        if UIDevice.current.userInterfaceIdiom == .phone {
            XCTAssertTrue(app.switches["faceid-toggle"].firstMatch.exists,
                          "באייפון הטוגל חייב להופיע בהגדרות")
        } else {
            XCTAssertFalse(app.switches["faceid-toggle"].firstMatch.exists,
                           "באייפד אסור שהטוגל יופיע — פיצ'ר אייפון בלבד")
        }
    }

    func testFaceIDEnableFromSettings() throws {
        guard UIDevice.current.userInterfaceIdiom == .phone else {
            throw XCTSkip("Face ID — פיצ'ר אייפון בלבד")
        }
        launchApp()
        tapTab("עוד")
        waitFor(element("more-screen"), timeout: 6)
        var attempts = 0
        let toggle = app.switches["faceid-toggle"].firstMatch
        while !toggle.isHittable && attempts < 8 { app.swipeUp(); attempts += 1 }
        toggle.switches.firstMatch.tap()
        // האימות (המזויף) מצליח — טוסט הפעלה.
        waitFor(element("toast"), timeout: 6)
    }
}
