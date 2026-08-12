import XCTest

/// ניווט כללי — טאבים, דשבורד, חיפוש ומצבי רשימה.
final class NavigationUITests: BYUITestCase {

    func testAllTabsOpen() {
        launchApp()
        waitFor(element("home-screen"), timeout: 10)
        tapTab("הזמנות")
        waitForRows("working_orders")
        tapTab("לקוחות")
        waitForRows("customers")
        tapTab("כספים")
        waitForRows("payments_transfer")
        tapTab("עוד")
        waitFor(element("more-screen"))
        tapTab("בית")
        waitFor(element("greeting"))
    }

    func testHomeShowsKPIsAndSections() {
        launchApp()
        waitFor(element("home-screen"), timeout: 10)
        waitFor(element("kpi-working"))
        waitFor(element("kpi-collect"))
        waitFor(element("kpi-pay"))
        waitFor(element("kpi-reminders"))
        // כרטיסי דומיין במסך הבית.
        waitFor(element("home-domain-working_orders"))
    }

    /// הסכומים בריבועי הבית חייבים להיות מדויקים — אותם סינונים כמו בדסקטופ.
    func testHomeTileValuesAreExact() {
        launchApp()
        waitFor(element("home-screen"), timeout: 10)

        // ממתינים שהדאטה ייטען לריבועים (לא ערכי אפס התחלתיים).
        let collectTile = element("kpi-collect")
        let deadline = Date().addingTimeInterval(10)
        while Date() < deadline && !collectTile.label.contains("25,452") {
            usleep(300_000)
        }

        // לגבייה: 5 שורות פתוחות עתידיות + שורת פיגור = ‎25,452 (כולל מועד גבייה שחלף).
        XCTAssertTrue(collectTile.label.contains("25,452"),
                      "ריבוע לגבייה שגוי: \(collectTile.label)")
        // שורת הפירוט של הפיגור מוצגת עם הסכום שחלף מועדו.
        XCTAssertTrue(collectTile.label.contains("מועד הגבייה חלף"),
                      "חסר פירוט מועד גבייה שחלף: \(collectTile.label)")
        XCTAssertTrue(collectTile.label.contains("1,111"),
                      "סכום הפיגור שגוי: \(collectTile.label)")
        // לתשלום: שורת התשלום הפתוחה היחידה = ‎7,009.
        XCTAssertTrue(element("kpi-pay").label.contains("7,009"),
                      "ריבוע לתשלום שגוי: \(element("kpi-pay").label)")
        // הזמנות בעבודה: רשומה אחת בנתוני הבדיקה.
        XCTAssertTrue(element("kpi-working").label.contains("1"),
                      "ריבוע הזמנות בעבודה שגוי: \(element("kpi-working").label)")
        // תזכורות פתוחות: שתיים בנתוני הבדיקה.
        XCTAssertTrue(element("kpi-reminders").label.contains("2"),
                      "ריבוע תזכורות שגוי: \(element("kpi-reminders").label)")

        // שורות המלכודת לא מחושבות: שולם 50,000 / גיליון ישן 99,999 / חשבונית ישנה 88,888.
        for excluded in ["50,000", "99,999", "88,888"] {
            XCTAssertFalse(collectTile.label.contains(excluded),
                           "הריבוע כולל סכום שאמור להיות מסונן: \(excluded)")
        }
    }

    func testHomeKPINavigatesToDomain() {
        launchApp()
        waitFor(element("kpi-working"), timeout: 10).tap()
        waitForRows("working_orders")
        app.navigationBars.buttons.firstMatch.tap()
        waitFor(element("greeting"))
    }

    func testHomeDomainCardNavigates() {
        launchApp()
        waitFor(element("home-screen"), timeout: 10)
        let card = element("home-domain-order_history")
        // הכרטיס נמצא בהמשך המסך — גוללים אליו.
        var attempts = 0
        while !card.isHittable && attempts < 6 {
            app.swipeUp()
            attempts += 1
        }
        card.tap()
        waitForRows("order_history")
    }

    func testSearchFiltersCustomers() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("night")
        // "night heron" קיים בנתוני הבדיקה.
        waitForRows("customers")
        let count = element("record-count")
        waitFor(count)
        XCTAssertTrue(count.label.contains("1"), "צפויה תוצאה אחת, התקבל: \(count.label)")
    }

    func testSearchNoResultsShowsEmptyState() {
        launchApp()
        tapTab("לקוחות")
        waitForRows("customers")
        let search = waitFor(app.searchFields.firstMatch)
        search.tap()
        search.typeText("zzzzqqqq")
        waitFor(element("empty-state"), timeout: 6)
    }

    func testPullToRefreshKeepsRows() {
        launchApp()
        tapTab("הזמנות")
        waitForRows("working_orders")
        let firstRow = app.buttons["row-working_orders"].firstMatch
        let start = firstRow.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.2))
        let end = firstRow.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 3.0))
        start.press(forDuration: 0.1, thenDragTo: end)
        waitForRows("working_orders")
    }
}
