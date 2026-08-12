import XCTest

/// פקיעת התחברות באמצע עבודה — האפליקציה חוזרת מסודר למסך ההתחברות.
final class SessionExpiryUITests: BYUITestCase {

    func testExpiredSessionReturnsToLogin() {
        // דומיין ההזמנות בעבודה מחזיר 401 — כמו קוקי שפג באמצע שימוש.
        launchApp(extraEnvironment: ["BY_UITEST_EXPIRE_ON": "working_orders"])
        waitFor(element("home-screen"), timeout: 10)
        tapTab("הזמנות")
        // ההודעה נבדקת מיד — הטוסט נעלם אחרי כמה שניות.
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "פג תוקף")).firstMatch
                .waitForExistence(timeout: 8),
            "חסרה הודעת פקיעת התחברות"
        )
        // ובמקום הרשימה — חזרה למסך ההתחברות.
        waitFor(element("login-screen"), timeout: 10)
    }

    func testReloginAfterExpiryWorks() {
        launchApp(extraEnvironment: ["BY_UITEST_EXPIRE_ON": "customers"])
        waitFor(element("home-screen"), timeout: 10)
        tapTab("לקוחות")
        waitFor(element("login-screen"), timeout: 10)
        // התחברות מחדש עובדת ומחזירה הביתה.
        loginWithTOTP()
    }
}
