import XCTest

/// מצבי שגיאה והתאוששות — תקלת שרת, נסה שוב, וקלט לא תקין.
final class ErrorStateUITests: BYUITestCase {

    func testDomainFailureShowsErrorAndRetryRecovers() {
        launchApp(extraEnvironment: ["BY_UITEST_FAIL_ONCE": "customers"])
        tapTab("לקוחות")
        waitFor(element("error-state"), timeout: 10)
        waitFor(retryButton()).tap()
        waitForRows("customers")
    }

    func testFailedDomainDoesNotBreakOtherDomains() {
        launchApp(extraEnvironment: ["BY_UITEST_FAIL_ONCE": "working_orders"])
        tapTab("הזמנות")
        waitFor(element("error-state"), timeout: 10)
        // מעבר לדומיין תקין באותו מסך.
        tapChip("order_history")
        waitForRows("order_history")
        // חזרה לדומיין שנכשל — נטען מחדש אוטומטית ומתאושש.
        tapChip("working_orders")
        waitForRows("working_orders")
    }

    func testHebrewErrorMessageIsShown() {
        launchApp(extraEnvironment: ["BY_UITEST_FAIL_ONCE": "customers"])
        tapTab("לקוחות")
        waitFor(element("error-state"), timeout: 10)
        // הודעת השגיאה מהשרת מוצגת בעברית.
        XCTAssertTrue(
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "לא הצלחתי")).firstMatch.exists
        )
    }
}
