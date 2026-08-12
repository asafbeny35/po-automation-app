import XCTest
@testable import BenYacovManage

/// טסטי חוזה מול שרת אמיתי שרץ מקומית (uvicorn על 127.0.0.1:8017) עם הדאטה האמיתי.
/// קריאה בלבד + dev-login — אפס מוטציות על דאטה עסקי.
/// הרצה: `TEST_RUNNER_BY_CONTRACT=1 xcodebuild test -only-testing:BenYacovManageTests/LocalContractTests`
final class LocalContractTests: XCTestCase {
    private static var didLogin = false
    private var client: APIClient!
    private var baseURL: URL!

    override func setUp() async throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["BY_CONTRACT"] == "1"
                || FileManager.default.fileExists(atPath: "/tmp/by_contract_tests"),
            "טסטי חוזה מקומיים רצים רק עם BY_CONTRACT=1 ושרת על 8017"
        )
        baseURL = URL(string: ProcessInfo.processInfo.environment["BY_CONTRACT_URL"] ?? "http://127.0.0.1:8017")!
        client = APIClient(baseURL: baseURL, transport: LiveTransport())
        if !Self.didLogin {
            try await devLogin()
            Self.didLogin = true
        }
    }

    /// כניסת פיתוח — זמינה רק ב-localhost עם כותרת debug, בדיוק כמו בשרת.
    private func devLogin() async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("auth/dev-login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("1", forHTTPHeaderField: "x-po-debug-auth")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["user_id": "asaf", "remember_me": true])
        let (data, response) = try await URLSession.shared.data(for: request)
        let http = try XCTUnwrap(response as? HTTPURLResponse)
        XCTAssertEqual(http.statusCode, 200, "dev-login נכשל: \(String(data: data, encoding: .utf8) ?? "")")
    }

    private func getJSONObject(_ path: String) async throws -> [String: Any] {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.timeoutInterval = 120
        let (data, response) = try await URLSession.shared.data(for: request)
        let http = try XCTUnwrap(response as? HTTPURLResponse)
        XCTAssertEqual(http.statusCode, 200, "\(path) החזיר \(http.statusCode)")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    // MARK: - התחברות ובוטסטראפ

    func testAuthBootstrapContract() async throws {
        let bootstrap = try await client.authBootstrap()
        XCTAssertFalse(bootstrap.authUsers.isEmpty)
        XCTAssertNotNil(bootstrap.authUsers.first { $0.id == "asaf" })
    }

    func testDevLoginProducesAuthenticatedSession() async throws {
        let payload = try await getJSONObject("mobile/auth/bootstrap")
        XCTAssertEqual(payload["authenticated"] as? Bool, true,
                       "אחרי dev-login השרת חייב לזהות session מחובר")
    }

    /// מזהי המקטעים בשרת חייבים להתאים למיפוי של האפליקציה — אחד לאחד.
    func testBootstrapSectionIDsMatchApp() async throws {
        let snapshot = try await client.bootstrap()
        let serverIDs = Set(snapshot.sections.map(\.id))
        let appIDs = Set(Domain.allCases.filter(\.isMobileDomain).map(\.bootstrapSectionID))
        XCTAssertEqual(appIDs.subtracting(serverIDs), [],
                       "מזהי מקטעים שהאפליקציה מצפה להם ולא קיימים בשרת")
        XCTAssertEqual(serverIDs.subtracting(appIDs), [],
                       "מקטעים בשרת שהאפליקציה לא מכירה")
    }

    // MARK: - כל הדומיינים עם דאטה אמיתי

    func testEveryMobileDomainDecodesRealData() async throws {
        var emptyDomains: [String] = []
        for domain in Domain.allCases where domain.isMobileDomain {
            let records = try await client.domainRows(domain)
            guard !records.isEmpty else {
                emptyDomains.append(domain.rawValue)
                continue
            }
            // לרוב מוחלט של השורות יש כותרת לתצוגה לפי ה-spec.
            let titled = records.filter { !$0.first(of: domain.spec.titleKeys).isEmpty }
            XCTAssertGreaterThanOrEqual(
                Double(titled.count), Double(records.count) * 0.9,
                "\(domain.rawValue): ל-\(records.count - titled.count) מתוך \(records.count) שורות אין כותרת (מפתחות: \(domain.spec.titleKeys))"
            )
            // סכומים אמיתיים מתפרסרים למספר.
            if let amountKey = domain.spec.amountKey {
                let withAmount = records.filter { !$0[amountKey].isEmpty }
                let parsed = withAmount.filter { $0.number(amountKey) != nil }
                XCTAssertGreaterThanOrEqual(
                    Double(parsed.count), Double(withAmount.count) * 0.9,
                    "\(domain.rawValue): סכומים אמיתיים לא מתפרסרים במפתח \(amountKey)"
                )
            }
            // תאריכים אמיתיים מקבלים פורמט תצוגה.
            for record in records.prefix(20) {
                let raw = record.first(of: domain.spec.dateKeys)
                if !raw.isEmpty {
                    XCTAssertFalse(Formatters.dateText(raw).isEmpty,
                                   "\(domain.rawValue): תאריך אמיתי '\(raw)' נעלם בפורמט")
                }
            }
        }
        // דומיינים ריקים מותרים (למשל תמחור לפני אכלוס) — אבל שידווחו.
        print("CONTRACT: דומיינים ריקים בדאטה האמיתי: \(emptyDomains)")
    }

    func testInstallationsContract() async throws {
        let cases = try await client.domainRows(.installationCases)
        let payload = try await getJSONObject("installations-state")
        XCTAssertNotNil(payload["rows"] as? [[String: Any]])
        XCTAssertNotNil(payload["visits"] as? [[String: Any]])
        let serverOptions = try XCTUnwrap(payload["status_options"] as? [String])
        XCTAssertEqual(serverOptions, APIClient.installationStatusOptions,
                       "אפשרויות הסטטוס באפליקציה לא תואמות לשרת")
        for record in cases {
            XCTAssertFalse(record["installation_id"].isEmpty, "תיק התקנה בלי מזהה")
        }
    }

    /// הטסט המרכזי: הסיווג של האפליקציה לגבייה/תשלום חייב להתאים לקטגוריזציה של השרת,
    /// שורה-בשורה. מצב "שולם" נלקח מ-all_rows העדכני — רשימות הקטגוריות בקאש השרת
    /// עלולות להחזיק עותק ישן של הדגל (באג שרת מתועד בנפרד).
    func testHomeTilesMatchServerCategorization() async throws {
        let payload = try await getJSONObject("payments-transfer-state")
        let serverCollection = (payload["payments_2026_collection"] as? [[String: Any]]) ?? []
        let serverPayment = (payload["payments_2026_payment"] as? [[String: Any]]) ?? []

        func rowKey(_ sheet: String, _ row: String) -> String { "\(sheet)#\(row)" }
        func serverKeys(_ rows: [[String: Any]]) -> Set<String> {
            Set(rows.map { rowKey(String(describing: $0["_sheet_title"] ?? ""), String(describing: $0["_sheet_row"] ?? "")) })
        }

        let appRows = try await client.domainRows(.paymentsTransfer)
        let categories = PaymentsMath.categorize(appRows)
        func appKeys(_ rows: [DomainRecord]) -> Set<String> {
            Set(rows.map { rowKey($0["_sheet_title"], $0["_sheet_row"]) })
        }

        let currentByKey = Dictionary(uniqueKeysWithValues: appRows.map {
            (rowKey($0["_sheet_title"], $0["_sheet_row"]), $0)
        })

        // חברות בקטגוריה זהה לשרת — שורה-בשורה. רשימות הקטגוריות בשרת הן snapshot,
        // ולכן מותר הפרש רק על שורות ששולמו (סחף קאש מתועד); הפרש על שורה פתוחה = באג סיווג.
        func assertMembership(_ app: Set<String>, _ server: Set<String>, label: String) {
            let drift = app.symmetricDifference(server)
            let openDrift = drift.filter { key in
                guard let row = currentByKey[key] else { return false }
                return !row.bool("paid")
            }
            XCTAssertEqual(openDrift, [],
                           "\(label): שורות פתוחות שמסווגות שונה מהשרת: \(openDrift)")
        }
        assertMembership(appKeys(categories.collection), serverKeys(serverCollection), label: "גבייה")
        assertMembership(appKeys(categories.payment), serverKeys(serverPayment), label: "תשלום")
        func openSum(_ keys: Set<String>) -> Double {
            keys.compactMap { currentByKey[$0] }
                .filter { !$0.bool("paid") }
                .compactMap { $0.number("amount") }
                .reduce(0, +)
        }
        XCTAssertEqual(PaymentsMath.openTotal(categories.collection),
                       openSum(serverKeys(serverCollection)), accuracy: 1.0,
                       "סכום לגבייה שונה מחישוב על קבוצת השרת")
        XCTAssertEqual(PaymentsMath.openTotal(categories.payment),
                       openSum(serverKeys(serverPayment)), accuracy: 1.0,
                       "סכום לתשלום שונה מחישוב על קבוצת השרת")
    }

    /// עוגיית ההתחברות שורדת בין מופעי לקוח שונים — שקול להפעלה מחדש של האפליקציה.
    func testAuthCookiePersistsAcrossClientInstances() async throws {
        let freshClient = APIClient(baseURL: baseURL, transport: LiveTransport())
        let bootstrap = try await freshClient.authBootstrap()
        XCTAssertTrue(bootstrap.authenticated,
                      "עוגיית ההתחברות לא נשמרה בין מופעים — התחברות תידרש בכל פתיחת אפליקציה")
    }

    func testStateEndpointsRespond() async throws {
        for path in ["finance-state", "customers-state", "order-history-state",
                     "quote-history-state", "delivery-confirmations-state", "marketing-docs-state"] {
            let payload = try await getJSONObject(path)
            XCTAssertNil(payload["error"], "\(path) החזיר שגיאה: \(payload["error"] ?? "")")
        }
    }
}
