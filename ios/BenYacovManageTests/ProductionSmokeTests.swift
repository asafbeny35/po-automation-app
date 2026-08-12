import XCTest
@testable import BenYacovManage

/// טסטי עשן מול שרת הפרודקשן האמיתי — קריאה בלבד, בלי לגעת בדאטה.
/// רצים רק כשמוגדר משתנה סביבה BY_SMOKE=1 (כדי שהריצה הרגילה תישאר מנותקת מהרשת):
/// `xcodebuild test ... TEST_RUNNER_BY_SMOKE=1 -only-testing:BenYacovManageTests/ProductionSmokeTests`
final class ProductionSmokeTests: XCTestCase {
    private var client: APIClient!

    override func setUpWithError() throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["BY_SMOKE"] == "1"
                || FileManager.default.fileExists(atPath: "/tmp/by_smoke_tests"),
            "טסטי עשן מול פרודקשן רצים רק עם BY_SMOKE=1"
        )
        client = APIClient(
            baseURL: URL(string: "https://poautomationapp.vercel.app")!,
            transport: LiveTransport()
        )
    }

    func testAuthBootstrapIsHealthy() async throws {
        let bootstrap = try await client.authBootstrap()
        XCTAssertFalse(bootstrap.authUsers.isEmpty, "צפוי לפחות משתמש התחברות אחד")
        let asaf = bootstrap.authUsers.first { $0.id == "asaf" }
        XCTAssertNotNil(asaf, "המשתמש asaf חסר בשרת")
        XCTAssertTrue(
            asaf.map { $0.methods.email || $0.methods.totp } ?? false,
            "לאסף אין אף שיטת התחברות פעילה"
        )
    }

    /// הטסט שהיה תופס את תקלת ההתחברות: טוקן Gmail פג = אי אפשר לשלוח קוד למייל.
    func testGmailOAuthCanSendLoginCodes() async throws {
        let data = try await client.getJSON("gmail-oauth/status")
        let status = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        XCTAssertEqual(status["send_status"] as? String, "ok",
                       "טוקן Gmail לא תקין — התחברות בקוד מייל תיכשל. סטטוס: \(status)")
        XCTAssertEqual(status["can_send"] as? Bool, true)
    }

    func testMobileBootstrapResponds() async throws {
        let snapshot = try await client.bootstrap()
        XCTAssertFalse(snapshot.sections.isEmpty, "תקציר המובייל ריק")
    }
}
