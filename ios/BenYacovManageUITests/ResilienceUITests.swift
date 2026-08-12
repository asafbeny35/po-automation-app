import XCTest

/// עמידות בתנאי עולם אמיתי — כשל שרת באמצע פעולה, רשת איטית, יציאה לרקע,
/// מצב כהה וגופן נגישות מוגדל.
final class ResilienceUITests: BYUITestCase {

    /// פעולה נכשלת בשרת → הודעת שגיאה, המסך שלם, ניסיון שני מצליח.
    func testActionFailureShowsErrorAndRetrySucceeds() {
        launchApp(extraEnvironment: ["BY_UITEST_FAIL_ACTION_ONCE": "/payments-transfer-paid"])
        tapTab("כספים")
        waitForRows("payments_transfer")
        app.buttons["row-payments_transfer"].firstMatch.tap()
        waitFor(element("record-detail"))

        // ניסיון ראשון — השרת מחזיר 500.
        waitFor(app.buttons["action-toggle-paid"]).tap()
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "תקלת שרת")).firstMatch
                .waitForExistence(timeout: 8),
            "חסרה הודעת שגיאה על כשל הפעולה"
        )
        // המסך נשאר תקין והפעולה עדיין זמינה.
        waitFor(app.buttons["action-toggle-paid"], timeout: 6)

        // ניסיון שני — מצליח.
        app.buttons["action-toggle-paid"].tap()
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "סומן")).firstMatch
                .waitForExistence(timeout: 8),
            "הניסיון החוזר לא הצליח"
        )
        app.buttons["close-detail"].tap()
    }

    /// רשת איטית → שלד טעינה מוצג, ואז הדאטה מגיע.
    func testSlowNetworkShowsLoadingThenRows() {
        // ההשהיה ארוכה מספיק כדי ש-XCUITest יספיק לצלם את מצב הטעינה.
        launchApp(extraEnvironment: ["BY_UITEST_SLOW_DOMAIN": "customers", "BY_UITEST_SLOW_MS": "7000"])
        tapTab("לקוחות")
        waitFor(element("loading-shimmer"), timeout: 6)
        waitForRows("customers")
    }

    /// יציאה לרקע וחזרה — המצב נשמר.
    func testBackgroundAndForegroundPreservesState() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        XCUIDevice.shared.press(.home)
        sleep(2)
        app.activate()
        // חוזרים לאותו מקום עם אותו דאטה.
        waitForRows("working_orders")
        waitFor(app.buttons["chip-order_history"], timeout: 6)
    }

    /// מצב כהה — כל המסכים המרכזיים חיים ותקינים.
    func testDarkModeRendersAllMainScreens() {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
        app.launchArguments += ["-AppleInterfaceStyle", "Dark"]
        app.launch()

        waitFor(element("home-screen"), timeout: 10)
        waitFor(element("kpi-collect"))
        tapTab("הזמנות")
        waitForRows("working_orders")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"))
        app.buttons["close-detail"].tap()
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapTab("עוד")
        waitFor(element("more-screen"))
    }

    /// גופן נגישות מוגדל — המסכים נשארים שמישים.
    func testLargeAccessibilityFontKeepsScreensUsable() {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
        app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityL"]
        app.launch()

        waitFor(element("home-screen"), timeout: 10)
        tapTab("הזמנות")
        waitForRows("working_orders")
        app.buttons["row-working_orders"].firstMatch.tap()
        waitFor(element("record-detail"))
        app.buttons["close-detail"].tap()
        tapTab("לקוחות")
        waitForRows("customers")
    }

    /// מסך ההתחברות במצב כהה.
    func testDarkModeLoginScreen() {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        app.launchArguments += ["-AppleInterfaceStyle", "Dark"]
        app.launch()
        waitFor(element("login-screen"), timeout: 10)
        waitFor(app.buttons["method-totp"])
        waitFor(app.textFields["code-field"])
    }
}
