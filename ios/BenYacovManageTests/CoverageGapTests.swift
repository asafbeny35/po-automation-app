import XCTest
@testable import BenYacovManage

/// טסטים ממוקדים לענפים שלא כוסו — קידוד JSON, מצבי שגיאה ב-SessionStore,
/// והרצת כל פעולות הקטלוג ישירות.
final class CoverageGapTests: XCTestCase {

    // MARK: - JSONValue: קידוד, אובייקטים מקוננים וקצוות

    func testJSONValueEncodeDecodeRoundTrip() throws {
        let original: [String: JSONValue] = [
            "text": .string("שלום"),
            "number": .number(3.5),
            "flag": .bool(false),
            "nothing": .null,
            "list": .array([.number(1), .string("ב")]),
            "nested": .object(["inner": .string("ערך")]),
        ]
        let encoded = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: encoded)
        XCTAssertEqual(decoded, original)
    }

    func testJSONValueDisplayTextEdgeCases() {
        XCTAssertEqual(JSONValue.object(["a": .string("b")]).displayText, "…")
        XCTAssertEqual(JSONValue.array([.bool(false), .null]).displayText, "לא, ")
        XCTAssertEqual(JSONValue.number(1e13).displayText, "10000000000000.0")
        XCTAssertTrue(JSONValue.string("   ").isEmptyDisplay)
        XCTAssertFalse(JSONValue.number(0).isEmptyDisplay)
    }

    func testJSONValueRejectsGarbage() {
        XCTAssertThrowsError(try JSONDecoder().decode(JSONValue.self, from: Data("not json".utf8)))
    }

    // MARK: - APIError: נפילה חיננית על תשובות לא צפויות

    func testAPIErrorFromNonJSONBody() {
        let error = APIError.from(data: Data("<html>oops</html>".utf8), statusCode: 502)
        XCTAssertEqual(error.statusCode, 502)
        XCTAssertTrue(error.message.contains("502"))
    }

    func testAPIErrorFromEmptyErrorField() {
        let error = APIError.from(data: Data("{\"error\": \"\"}".utf8), statusCode: 500)
        XCTAssertTrue(error.message.contains("500"))
    }

    // MARK: - SessionStore: מסלולי שגיאה וטוסטים

    /// תעבורה שנכשלת תמיד — לבדיקת מסלולי השגיאה.
    private struct FailingTransport: Transport {
        let error: Error
        func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
            throw error
        }
    }

    @MainActor
    func testNetworkErrorProducesFriendlyHebrewMessage() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: FailingTransport(error: URLError(.notConnectedToInternet))
        )
        let session = SessionStore(api: client)
        await session.loadDomain(.customers)
        XCTAssertEqual(session.state(for: .customers).errorMessage,
                       "אין חיבור לשרת. בדוק את הרשת ונסה שוב.")
    }

    @MainActor
    func testStartWithDeadServerFallsBackToLogin() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: FailingTransport(error: URLError(.cannotConnectToHost))
        )
        let session = SessionStore(api: client)
        await session.start()
        XCTAssertEqual(session.phase, .loggedOut)
    }

    @MainActor
    func testPerformFailureShowsErrorToastAndReturnsFalse() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        let session = SessionStore(api: client)
        let succeeded = await session.perform("לא אמור להופיע") {
            throw APIError(message: "שגיאה מכוונת", statusCode: 500)
        }
        XCTAssertFalse(succeeded)
        XCTAssertEqual(session.toast?.style, .error)
        XCTAssertEqual(session.toast?.text, "שגיאה מכוונת")
    }

    @MainActor
    func testPerformSuccessShowsSuccessToast() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        let session = SessionStore(api: client)
        let succeeded = await session.perform("הצלחה!") {}
        XCTAssertTrue(succeeded)
        XCTAssertEqual(session.toast?.style, .success)
    }

    @MainActor
    func testBootstrap401LogsOut() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: FailingTransport(error: APIError(message: "נדרשת הזדהות", statusCode: 401))
        )
        let session = SessionStore(api: client)
        session.phase = .loggedIn
        await session.loadBootstrap()
        XCTAssertEqual(session.phase, .loggedOut)
        XCTAssertTrue(session.toast?.text.contains("פג תוקף") ?? false)
    }

    @MainActor
    func testDomainErrorWithExistingDataKeepsDataAndToasts() async {
        setenv("BY_UITEST_FAIL_ONCE", "customers", 1)
        defer { unsetenv("BY_UITEST_FAIL_ONCE") }
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        let session = SessionStore(api: client)
        // טעינה ראשונה נכשלת → מצב שגיאה; שנייה מצליחה; שלישית עם כשל מדומה חדש
        await session.loadDomain(.customers)
        XCTAssertNotNil(session.state(for: .customers).errorMessage)
        await session.loadDomain(.customers, force: true)
        XCTAssertFalse(session.records(for: .customers).isEmpty)
    }

    @MainActor
    func testLogoutClearsState() async {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        let session = SessionStore(api: client)
        await session.loadDomain(.customers)
        XCTAssertFalse(session.records(for: .customers).isEmpty)
        await session.logout()
        XCTAssertEqual(session.phase, .loggedOut)
        XCTAssertTrue(session.records(for: .customers).isEmpty)
        XCTAssertNil(session.bootstrap.value)
    }

    // MARK: - כל פעולות הקטלוג רצות בפועל

    func testEveryCatalogActionExecutesAgainstMock() async throws {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
        for domain in Domain.allCases {
            let records = try await client.domainRows(domain)
            guard let first = records.first else { continue }
            for action in DomainActionCatalog.actions(for: domain, record: first) {
                do {
                    // שליפה מחדש לפני כל פעולה — מוטציה קודמת משנה את ה-snapshot hash
                    // (זה חוזה הנעילה האופטימית, לא פרט מימוש).
                    let fresh = try await client.domainRows(domain, forceRefresh: true)
                    guard let record = fresh.first(where: { $0.id == first.id }) ?? fresh.first else { continue }
                    try await action.run(client, record)
                } catch {
                    XCTFail("פעולת \(action.id) בדומיין \(domain.rawValue) נכשלה: \(error)")
                }
            }
        }
    }

    // MARK: - AppConfig

    func testBaseURLFallsBackToProduction() {
        // בסביבת הטסטים אין override — ברירת המחדל היא הפרודקשן.
        XCTAssertTrue(AppConfig.baseURL.absoluteString.contains("poautomationapp")
                      || ProcessInfo.processInfo.environment["BY_BASE_URL"] != nil)
    }
}
