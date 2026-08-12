import XCTest

/// זרימות התחברות והתנתקות — TOTP, קוד מייל, שגיאות והחלפת משתמש.
final class AuthUITests: BYUITestCase {

    func testLoginScreenShowsUsersAndMethods() {
        launchApp(authenticated: false)
        waitFor(element("login-screen"), timeout: 10)
        waitFor(app.buttons["user-asaf"])
        waitFor(app.buttons["user-reut"])
        waitFor(app.buttons["method-totp"])
        waitFor(app.buttons["method-email"])
        waitFor(app.textFields["code-field"])
        XCTAssertTrue(app.switches["remember-toggle"].firstMatch.exists)
    }

    func testTOTPWrongCodeShowsError() {
        launchApp(authenticated: false)
        let field = waitFor(app.textFields["code-field"], timeout: 10)
        field.tap()
        field.typeText("000000")
        app.buttons["login-button"].tap()
        waitFor(element("login-error"), timeout: 6)
        XCTAssertFalse(element("home-screen").exists, "לא אמורים להיכנס עם קוד שגוי")
    }

    func testTOTPShortCodeValidation() {
        launchApp(authenticated: false)
        let field = waitFor(app.textFields["code-field"], timeout: 10)
        field.tap()
        field.typeText("123")
        app.buttons["login-button"].tap()
        waitFor(element("login-error"), timeout: 4)
    }

    func testTOTPHappyPathReachesHome() {
        launchApp(authenticated: false)
        loginWithTOTP()
        waitFor(element("greeting"))
    }

    func testEmailCodeHappyPath() {
        launchApp(authenticated: false)
        waitFor(app.buttons["method-email"], timeout: 10).tap()
        waitFor(app.buttons["send-code-button"]).tap()
        waitFor(element("login-status"), timeout: 6)
        let field = app.textFields["code-field"]
        field.tap()
        field.typeText("654321")
        waitFor(app.buttons["login-button"]).tap()
        waitFor(element("home-screen"), timeout: 10)
    }

    func testEmailWrongCodeShowsError() {
        launchApp(authenticated: false)
        waitFor(app.buttons["method-email"], timeout: 10).tap()
        waitFor(app.buttons["send-code-button"]).tap()
        waitFor(element("login-status"), timeout: 6)
        let field = app.textFields["code-field"]
        field.tap()
        field.typeText("999999")
        app.buttons["login-button"].tap()
        waitFor(element("login-error"), timeout: 6)
    }

    func testSwitchUserKeepsScreenUsable() {
        launchApp(authenticated: false)
        waitFor(app.buttons["user-reut"], timeout: 10).tap()
        // לרעות אין TOTP — שיטת המייל אמורה להיבחר אוטומטית.
        waitFor(app.buttons["send-code-button"], timeout: 4)
        app.buttons["user-asaf"].tap()
        waitFor(app.buttons["method-totp"], timeout: 4)
    }

    func testLogoutReturnsToLogin() {
        launchApp(authenticated: true)
        waitFor(element("home-screen"), timeout: 10)
        tapTab("עוד")
        waitFor(app.buttons["logout-button"], timeout: 6).tap()
        waitFor(element("login-screen"), timeout: 8)
    }

    func testAuthenticatedLaunchSkipsLogin() {
        launchApp(authenticated: true)
        waitFor(element("home-screen"), timeout: 10)
        XCTAssertFalse(element("login-screen").exists)
    }
}
