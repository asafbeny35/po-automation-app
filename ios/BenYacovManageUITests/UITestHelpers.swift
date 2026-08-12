import XCTest

/// בסיס לכל טסטי ה-UI — הפעלה במצב mock, וכלי עזר לניווט RTL.
class BYUITestCase: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
    }

    /// מפעיל את האפליקציה מול השרת המדומה.
    func launchApp(authenticated: Bool = true, extraEnvironment: [String: String] = [:]) {
        app = XCUIApplication()
        app.launchEnvironment["BY_UITEST"] = "1"
        if authenticated {
            app.launchEnvironment["BY_UITEST_AUTHENTICATED"] = "1"
        }
        for (key, value) in extraEnvironment {
            app.launchEnvironment[key] = value
        }
        app.launch()
    }

    @discardableResult
    func waitFor(_ element: XCUIElement, timeout: TimeInterval = 8,
                 file: StaticString = #filePath, line: UInt = #line) -> XCUIElement {
        XCTAssertTrue(element.waitForExistence(timeout: timeout),
                      "האלמנט לא הופיע בזמן: \(element)", file: file, line: line)
        return element
    }

    /// כל אלמנט עם מזהה — בלי תלות בסוג.
    func element(_ identifier: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    func tapTab(_ title: String, file: StaticString = #filePath, line: UInt = #line) {
        // אייפון: סרגל טאבים תחתון. אייפד (iOS 26): סרגל עליון שלא נחשף כ-tabBars.
        let tabBarButton = app.tabBars.buttons[title]
        if tabBarButton.waitForExistence(timeout: 3) {
            tabBarButton.tap()
            return
        }
        let anyButton = app.buttons[title].firstMatch
        XCTAssertTrue(anyButton.waitForExistence(timeout: 8),
                      "טאב \(title) לא נמצא — לא בסרגל תחתון ולא עליון", file: file, line: line)
        anyButton.tap()
    }

    /// לוחץ על צ'יפ דומיין — כל הצ'יפים גלויים תמיד (פריסת flow עוטפת).
    func tapChip(_ domainRawValue: String, file: StaticString = #filePath, line: UInt = #line) {
        let chip = app.buttons["chip-\(domainRawValue)"].firstMatch
        XCTAssertTrue(chip.waitForExistence(timeout: 8),
                      "הצ'יפ chip-\(domainRawValue) לא קיים", file: file, line: line)
        chip.tap()
    }

    /// ממתין להופעת שורות של דומיין ברשימה.
    func waitForRows(_ domainRawValue: String, file: StaticString = #filePath, line: UInt = #line) {
        let row = app.buttons["row-\(domainRawValue)"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10),
                      "לא הופיעו שורות לדומיין \(domainRawValue)", file: file, line: line)
    }

    /// פותח את הפירוט של השורה הראשונה, מוודא שנפתח, וסוגר.
    func openAndCloseFirstRecord(_ domainRawValue: String) {
        app.buttons["row-\(domainRawValue)"].firstMatch.tap()
        waitFor(element("record-detail"), timeout: 6)
        waitFor(app.buttons["close-detail"]).tap()
        // ממתינים שה-sheet ייעלם לגמרי — אחרת ההקשה הבאה נבלעת באנימציית הסגירה.
        let detail = element("record-detail")
        let deadline = Date().addingTimeInterval(6)
        while detail.exists && Date() < deadline {
            usleep(200_000)
        }
        XCTAssertFalse(detail.exists, "מסך הפירוט לא נסגר")
        XCTAssertTrue(
            app.buttons["row-\(domainRawValue)"].firstMatch.waitForExistence(timeout: 5),
            "הרשימה לא חזרה אחרי סגירת פירוט"
        )
    }

    /// כפתור "נסה שוב" — לפי מזהה או תווית (המזהה לא תמיד נחשף על כפתורי SwiftUI).
    func retryButton() -> XCUIElement {
        app.buttons.matching(
            NSPredicate(format: "identifier == %@ OR label CONTAINS %@", "retry-button", "נסה שוב")
        ).firstMatch
    }

    /// התחברות מלאה דרך מסך ההתחברות עם קוד TOTP תקין.
    func loginWithTOTP() {
        waitFor(element("login-screen"), timeout: 10)
        let field = waitFor(app.textFields["code-field"])
        field.tap()
        field.typeText("123456")
        app.buttons["login-button"].tap()
        waitFor(element("home-screen"), timeout: 10)
    }
}
