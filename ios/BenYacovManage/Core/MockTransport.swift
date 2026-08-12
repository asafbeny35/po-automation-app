import Foundation

/// שרת מדומה בזיכרון לטסטי UI ויחידה — מגיב לאותם נתיבים כמו השרת האמיתי,
/// כולל מוטציות אמיתיות על הדאטה כדי שהמסכים יתעדכנו כמו בפרודקשן.
final class MockTransport: Transport, @unchecked Sendable {
    private let lock = NSLock()
    private var authenticated: Bool
    private var pendingEmailCode: String?
    private var epochCallCount = 0
    private var consumedForcedConflict = false

    /// hash דטרמיניסטי לשורת תשלומים — מדמה את _payments_row_snapshot_hash בשרת.
    func paymentsSnapshotHash(_ row: [String: Any]) -> String {
        let fields = ["customer_name", "amount", "paid", "due_date", "notes", "po_number", "tax_invoice_number"]
        let payload = fields.map { "\($0)=\(str(row[$0]))" }.joined(separator: "|")
            + "|\(str(row["_sheet_title"]))|\(int(row["_sheet_row"]))"
        return "mockhash-\(payload.hashValue)"
    }

    /// כמו בשרת: expected_snapshot_hash חובה באפליקציה, ואם לא תואם — 409.
    private func paymentsConflictCheck(_ body: [String: Any]) -> (Int, [String: Any])? {
        let expected = str(body["expected_snapshot_hash"])
        guard !expected.isEmpty else {
            return (400, ["error": "האפליקציה חייבת לשלוח expected_snapshot_hash — הגנת הנעילה האופטימית."])
        }
        let rowNumber = int(body["row_number"])
        guard let current = (domains["payments_transfer"] ?? []).first(where: { self.int($0["_sheet_row"]) == rowNumber }) else {
            return nil
        }
        var conflictForced = false
        if ProcessInfo.processInfo.environment["BY_UITEST_PAYMENTS_CONFLICT"] == "1", !consumedForcedConflict {
            consumedForcedConflict = true
            conflictForced = true
        }
        if conflictForced || expected != paymentsSnapshotHash(current) {
            return (409, [
                "error": "מישהו אחר עדכן את השורה הזו הרגע — הנתונים רועננו, נסה שוב.",
                "conflict": true,
            ])
        }
        return nil
    }

    private var domains: [String: [[String: Any]]] = [:]
    /// דומיינים שייכשלו פעם אחת (לבדיקת מסכי שגיאה ו"נסה שוב").
    private var failOnceDomains: Set<String>
    /// דומיין שמחזיר 401 — סימולציה של פקיעת session.
    private let expireSessionOnDomain: String?
    /// נתיב פעולה שייכשל פעם אחת ב-500 — סימולציה של כשל שרת באמצע פעולה.
    private var failActionOncePath: String?
    /// דומיין איטי + זמן ההשהיה — סימולציה של רשת איטית.
    private let slowDomain: String?
    private let slowDomainDelayMs: UInt64

    static let validTOTPCode = "123456"
    static let validEmailCode = "654321"

    init(startAuthenticated: Bool = AppConfig.uiTestStartsAuthenticated) {
        authenticated = startAuthenticated
        failOnceDomains = Set(
            (ProcessInfo.processInfo.environment["BY_UITEST_FAIL_ONCE"] ?? "")
                .split(separator: ",").map(String.init)
        )
        expireSessionOnDomain = ProcessInfo.processInfo.environment["BY_UITEST_EXPIRE_ON"]
        failActionOncePath = ProcessInfo.processInfo.environment["BY_UITEST_FAIL_ACTION_ONCE"]
        slowDomain = ProcessInfo.processInfo.environment["BY_UITEST_SLOW_DOMAIN"]
        slowDomainDelayMs = UInt64(ProcessInfo.processInfo.environment["BY_UITEST_SLOW_MS"] ?? "") ?? 2500
        for domain in Domain.allCases {
            domains[domain.rawValue] = Self.loadFixtureRows(named: domain.rawValue)
        }
    }

    private static func loadFixtureRows(named name: String) -> [[String: Any]] {
        // Bundle.main בטסטי יחידה הוא ה-runner — מחפשים גם ב-bundle של האפליקציה.
        let bundles = [Bundle.main, Bundle(for: MockTransport.self)]
        for bundle in bundles {
            guard let url = bundle.url(forResource: name, withExtension: "json", subdirectory: "Fixtures")
                    ?? bundle.url(forResource: name, withExtension: "json"),
                  let data = try? Data(contentsOf: url),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let rows = object["rows"] as? [[String: Any]] else {
                continue
            }
            return rows
        }
        return []
    }

    // MARK: - Transport

    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        // השהיה קלה כדי לדמות רשת ולתת ל-UI להציג מצבי טעינה.
        try? await Task.sleep(nanoseconds: 30_000_000)
        let path = request.url?.path ?? ""

        // רשת איטית מדומה לדומיין נבחר.
        if let slowDomain, path == "/mobile/domains/\(slowDomain)" {
            try? await Task.sleep(nanoseconds: slowDomainDelayMs * 1_000_000)
        }

        // קבצים בינאריים (תצוגות מקדימות וקובצי חשבוניות).
        if let binary = binaryResponse(for: path) {
            let response = HTTPURLResponse(
                url: request.url!, statusCode: 200, httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": binary.mime]
            )!
            return (binary.data, response)
        }

        // ולידציה אמיתית של העלאות multipart — כמו שהשרת היה דוחה בקשה בלי קובץ.
        if ["/process", "/finance-invoices-upload", "/delivery-confirmations-upload", "/working-orders-upload"].contains(path) {
            let files = Self.multipartFiles(request: request)
            if files.isEmpty {
                let error = try JSONSerialization.data(withJSONObject: ["error": "לא נבחרו קבצים להעלאה."])
                return (error, HTTPURLResponse(url: request.url!, statusCode: 400, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!)
            }
        }

        var body = request.httpBody
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
        // פרמטרי query זמינים לניתוב (כמו בהעלאת תעודה חתומה).
        if let url = request.url,
           let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems {
            for item in items where body[item.name] == nil {
                body[item.name] = item.value ?? ""
            }
        }
        let formFields = Self.multipartFields(request: request)

        // עמידות: דומיין שמוגדר ב-BY_UITEST_GARBAGE_DOMAIN מחזיר בתים שבורים —
        // האפליקציה חייבת להציג שגיאה מסודרת, לא לקרוס.
        if let garbageDomain = ProcessInfo.processInfo.environment["BY_UITEST_GARBAGE_DOMAIN"],
           path == "/mobile/domains/\(garbageDomain)" {
            let garbage = Data("not-json{{{broken".utf8)
            return (garbage, HTTPURLResponse(url: request.url!, statusCode: 200,
                                             httpVersion: "HTTP/1.1",
                                             headerFields: ["Content-Type": "application/json"])!)
        }

        let (status, payload) = handle(path: path, method: request.httpMethod ?? "GET", body: body, formFields: formFields)
        let data = try JSONSerialization.data(withJSONObject: payload)
        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"]
        )!
        return (data, response)
    }

    /// מפרסר שדות טקסט מגוף multipart (חלקים בלי filename). מחזיר nil אם הבקשה אינה multipart.
    static func multipartFields(request: URLRequest) -> [String: Any]? {
        guard let contentType = request.value(forHTTPHeaderField: "Content-Type"),
              contentType.contains("multipart/form-data"),
              let boundaryRange = contentType.range(of: "boundary="),
              let body = request.httpBody else {
            return nil
        }
        let boundary = "--" + contentType[boundaryRange.upperBound...].trimmingCharacters(in: .whitespaces)
        guard let boundaryData = boundary.data(using: .utf8),
              let separator = "\r\n\r\n".data(using: .utf8) else {
            return nil
        }
        var fields: [String: Any] = [:]
        var searchStart = body.startIndex
        while let partStart = body.range(of: boundaryData, in: searchStart..<body.endIndex) {
            let afterBoundary = partStart.upperBound
            guard let nextBoundary = body.range(of: boundaryData, in: afterBoundary..<body.endIndex) else { break }
            let part = body[afterBoundary..<nextBoundary.lowerBound]
            searchStart = nextBoundary.lowerBound
            guard let headerEnd = part.range(of: separator),
                  let headerText = String(data: part[part.startIndex..<headerEnd.lowerBound], encoding: .utf8),
                  !headerText.contains("filename=\""),
                  let nameRange = headerText.range(of: #"name="([^"]+)""#, options: .regularExpression) else {
                continue
            }
            let name = String(headerText[nameRange])
                .replacingOccurrences(of: "name=\"", with: "")
                .replacingOccurrences(of: "\"", with: "")
            var valueData = Data(part[headerEnd.upperBound...])
            if valueData.suffix(2) == Data("\r\n".utf8) {
                valueData = valueData.dropLast(2)
            }
            fields[name] = String(data: valueData, encoding: .utf8) ?? ""
        }
        return fields
    }

    /// מפרסר גוף multipart ומחזיר את חלקי הקבצים (שם + תוכן) — מוודא שהקידוד
    /// של האפליקציה באמת תקין, לא רק שהנתיב נקרא.
    static func multipartFiles(request: URLRequest) -> [(filename: String, data: Data)] {
        guard let contentType = request.value(forHTTPHeaderField: "Content-Type"),
              let boundaryRange = contentType.range(of: "boundary="),
              let body = request.httpBody else {
            return []
        }
        let boundary = "--" + contentType[boundaryRange.upperBound...].trimmingCharacters(in: .whitespaces)
        guard let boundaryData = boundary.data(using: .utf8),
              let separator = "\r\n\r\n".data(using: .utf8) else {
            return []
        }

        var files: [(String, Data)] = []
        var searchStart = body.startIndex
        while let partStart = body.range(of: boundaryData, in: searchStart..<body.endIndex) {
            let afterBoundary = partStart.upperBound
            guard let nextBoundary = body.range(of: boundaryData, in: afterBoundary..<body.endIndex) else { break }
            let part = body[afterBoundary..<nextBoundary.lowerBound]
            searchStart = nextBoundary.lowerBound

            guard let headerEnd = part.range(of: separator),
                  let headerText = String(data: part[part.startIndex..<headerEnd.lowerBound], encoding: .utf8),
                  let filenameRange = headerText.range(of: #"filename="([^"]+)""#, options: .regularExpression) else {
                continue
            }
            let filename = String(headerText[filenameRange])
                .replacingOccurrences(of: "filename=\"", with: "")
                .replacingOccurrences(of: "\"", with: "")
            // תוכן הקובץ עד ה-\r\n שלפני הגבול הבא.
            var fileData = Data(part[headerEnd.upperBound...])
            if fileData.suffix(2) == Data("\r\n".utf8) {
                fileData = fileData.dropLast(2)
            }
            if !filename.isEmpty && !fileData.isEmpty {
                files.append((filename, fileData))
            }
        }
        return files
    }

    private func binaryResponse(for path: String) -> (data: Data, mime: String)? {
        func fixtureData(_ name: String, _ ext: String) -> Data? {
            for bundle in [Bundle.main, Bundle(for: MockTransport.self)] {
                if let url = bundle.url(forResource: name, withExtension: ext, subdirectory: "Fixtures")
                    ?? bundle.url(forResource: name, withExtension: ext) {
                    return try? Data(contentsOf: url)
                }
            }
            return nil
        }
        if path.hasPrefix("/marketing-doc-preview/") {
            return fixtureData("sample_preview", "png").map { ($0, "image/png") }
        }
        if path.hasPrefix("/finance-invoices-file/")
            || path.hasPrefix("/supplier-delivery-note-source/")
            || path.hasPrefix("/working-order-note-file/")
            || path.hasPrefix("/admin-drive-file/") {
            return fixtureData("sample_invoice", "pdf").map { ($0, "application/pdf") }
        }
        if path.hasPrefix("/static/admin/vehicles/") {
            return fixtureData("sample_preview", "png").map { ($0, "image/png") }
        }
        return nil
    }

    /// שדות טופס מה-multipart של הבקשה הנוכחית (בתוקף רק בזמן ניתוב).
    private var pendingFormFields: [String: Any]?

    /// טיפול סינכרוני תחת נעילה — בטוח לקריאה מהקשר אסינכרוני.
    private func handle(path: String, method: String, body: [String: Any], formFields: [String: Any]?) -> (Int, [String: Any]) {
        lock.lock()
        defer { lock.unlock(); pendingFormFields = nil }
        pendingFormFields = formFields
        return route(path: path, method: method, body: body)
    }

    // MARK: - ניתוב

    private func route(path: String, method: String, body: [String: Any]) -> (Int, [String: Any]) {
        switch (method, path) {
        case ("GET", "/mobile/auth/bootstrap"):
            return (200, authBootstrapPayload())
        case ("GET", "/mobile/bootstrap"):
            return (200, bootstrapPayload())
        case ("POST", "/auth/totp/verify"):
            let code = str(body["code"])
            guard code == Self.validTOTPCode else {
                return (400, ["error": "קוד האימות לא תקין."])
            }
            authenticated = true
            return (200, ["status": "ok"])
        case ("POST", "/auth/email/send-code"):
            pendingEmailCode = Self.validEmailCode
            return (200, ["status": "ok", "message": "נשלח קוד ל-asafbeny@gmail.com"])
        case ("POST", "/auth/email/verify"):
            guard let pending = pendingEmailCode, str(body["code"]) == pending else {
                return (400, ["error": "קוד המייל לא תקין או שפג תוקפו."])
            }
            pendingEmailCode = nil
            authenticated = true
            return (200, ["status": "ok"])
        case ("POST", "/auth/logout"):
            authenticated = false
            return (200, ["status": "ok"])
        default:
            break
        }

        if method == "GET", path == "/installations-state" {
            return (200, [
                "status": "ok",
                "rows": domains["installation_cases"] ?? [],
                "visits": domains["installation_visits"] ?? [],
                "status_options": ["ממתין לתיאום", "תואם", "הותקן חלקית", "הושלם", "מושהה", "בוטל"],
            ])
        }

        if method == "GET", path == "/quote-history-quote-resolve" {
            return (200, ["status": "ok", "url": "https://drive.google.com/file/d/mock-quote-view"])
        }

        if method == "GET", path == "/finance-invoices-epoch" {
            epochCallCount += 1
            // תרחיש הדגמה ל-E2E: אחרי שתי בדיקות, "מישהו" שומר חשבונית מרחוק.
            if ProcessInfo.processInfo.environment["BY_UITEST_EPOCH_DEMO"] == "1",
               epochCallCount == 3 {
                upsert("finance_invoices", idKey: "row_id", row: [
                    "row_id": "live-update-demo",
                    "supplier_name": "ספק עדכון חי",
                    "invoice_number": "77777",
                    "amount": "1,234.00",
                    "updated_at": "2030-01-01T00:00:00",
                ])
            }
            let rows = domains["finance_invoices"] ?? []
            let latest = rows.compactMap { self.str($0["updated_at"]) }.max() ?? ""
            return (200, ["status": "ok", "count": rows.count, "latest_updated_at": latest])
        }

        if method == "GET", path == "/mobile/admin-lending" {
            return (200, [
                "status": "ok",
                "totals": ["loans": "₪ 410,059.43", "mortgages": "₪ 629,029.10"],
                "loans": [
                    ["title": "הלוואה 400,000", "kicker": "דיסקונט · הלוואה עסקית", "group": "loan",
                     "blurb": "שפיצר לא צמוד בריבית פריים, עם חיוב חודשי משוער.",
                     "facts": [["label": "סה״כ יתרה", "value": "₪ 382,559.42"],
                               ["label": "התשלום הבא", "value": "20/07/2026 · ₪ 7,640.46"],
                               ["label": "תאריך סיום", "value": "20/03/2031"]],
                     "details": ["חשבון: 253594555 · סניף 44 עסקים הרצליה", "מספר הלוואה: 0-044-0155-00-468286"],
                     "docs": [["key": "loan-discount-400-summary", "label": "פירוט הלוואה"],
                              ["key": "loan-discount-400-amortization", "label": "לוח סילוקין"]]],
                    ["title": "הלוואה 30,000", "kicker": "דיסקונט · הלוואה עסקית", "group": "loan",
                     "blurb": "הלוואה לא צמודה ללא ריבית, במסלול קרן קבועה.",
                     "facts": [["label": "סה״כ יתרה", "value": "₪ 27,500.01"],
                               ["label": "התשלום הבא", "value": "20/07/2026 · ₪ 833.33"]],
                     "details": ["שיטת פרעון: קרן קבועה · 36 תשלומים"],
                     "docs": [["key": "loan-discount-30-summary", "label": "פירוט הלוואה"]]],
                    ["title": "משכנתא - הגורן 34, עתלית", "kicker": "דיסקונט · משכנתא", "group": "mortgage",
                     "blurb": "חשבון משכנתא משולב עם 5 מסלולים פעילים.",
                     "facts": [["label": "סה״כ יתרה", "value": "₪ 629,029.10"],
                               ["label": "התשלום הבא", "value": "10/07/2026 · ₪ 5,787.67"]],
                     "details": ["נכס: הגורן 34, עתלית", "חשבון משכנתא: 0153-0193646902"],
                     "docs": [["key": "mortgage-discount-summary", "label": "פירוט משכנתא"]]],
                ],
                "vehicles": [
                    ["name": "קיה נירו אפורה", "plate": "13578301", "title": "קיה נירו אפורה",
                     "subtitle": "דגם 2017 עם רישיון רכב עדכני וביטוח מלא.",
                     "image_path": "static/admin/vehicles/grey-niro-cutout.png",
                     "facts": [["label": "טסט הבא", "value": "26/11/2026"],
                               ["label": "חברת ביטוח", "value": "הפניקס"],
                               ["label": "מספר פוליסה", "value": "261480401172479"],
                               ["label": "פקיעת ביטוח", "value": "31/03/2027"]],
                     "docs": [["key": "vehicle-grey-niro-license", "label": "רישיון"],
                              ["key": "vehicle-grey-niro-policy", "label": "פוליסה"]]],
                    ["name": "מלגזה", "plate": "78662", "title": "מלגזה",
                     "subtitle": "רישיון צמ״ה, פוליסת צד ג' ותעודת חובה.",
                     "image_path": "static/admin/vehicles/forklift-cutout.png",
                     "facts": [["label": "טסט הבא", "value": "01/05/2026"],
                               ["label": "חברת ביטוח", "value": "ש. שלמה חברה לביטוח"]],
                     "docs": [["key": "vehicle-forklift-license", "label": "רישיון צמ״ה"]]],
                ],
            ])
        }

        if method == "GET", path == "/manual-order-recent-customers" {
            return (200, ["status": "ok", "rows": [
                ["customer_name": "י.ח. דמרי בניה ופיתוח בעמ", "customer_id": "511399388", "customer_phone": "08-9939000"],
                ["customer_name": "עזריאלי יונתן בינוי ופיתוח בעמ", "customer_id": "517073284", "customer_phone": "055-6818973"],
            ]])
        }

        if method == "GET", path == "/marketing-docs-state" {
            return (200, [
                "status": "ok",
                "docs": [
                    ["asset_key": "brochure-hebrew", "label": "ברושור מלא בעברית", "category": "מסמכי ליבה",
                     "share_link_url": "https://drive.google.com/file/d/mock-brochure", "available": true],
                    ["asset_key": "price-list", "label": "מחירון ללקוחות", "category": "מסמכי ליבה",
                     "share_link_url": "https://drive.google.com/file/d/mock-prices", "available": true],
                ],
            ])
        }

        if path.hasPrefix("/mobile/domains/") {
            let name = path.replacingOccurrences(of: "/mobile/domains/", with: "")
            if name == expireSessionOnDomain {
                // כמו auth_gate בשרת האמיתי.
                return (401, ["error": "נדרשת הזדהות לפני שימוש באפליקציה."])
            }
            if failOnceDomains.contains(name) {
                failOnceDomains.remove(name)
                return (500, ["error": "לא הצלחתי לטעון כרגע את הדומיין \(name): תקלת בדיקה."])
            }
            if let rows = domains[name] {
                // תשלומים מוגשים עם _snapshot_hash — כמו העשרת המובייל בשרת.
                if name == "payments_transfer" {
                    var served = rows
                    // עומס: BY_UITEST_BIG_DOMAIN מוסיף אלפי שורות סינתטיות לבדיק,
                    // כדי לוודא שהרשימה, החיפוש והגלילה שורדים דאטה אמיתי-בגודלו.
                    if ProcessInfo.processInfo.environment["BY_UITEST_BIG_DOMAIN"] == name {
                        for index in 0..<3000 {
                            served.append([
                                "customer_name": "לקוח עומס \(index)",
                                "payment_direction": index % 3 == 0 ? "תשלום" : "גביה",
                                "amount": "₪\(100 + index).00",
                                "due_date": "01/0\(1 + index % 9)/2026",
                                "invoice_date": "01/01/2026",
                                "paid": index % 5 == 0 ? "TRUE" : "FALSE",
                                "po_number": "LOAD-\(index)",
                                "_sheet_title": "תשלומים והעברות 2026",
                                "_sheet_row": 5000 + index,
                            ])
                        }
                    }
                    let enriched = served.map { row -> [String: Any] in
                        var copy = row
                        copy["_snapshot_hash"] = paymentsSnapshotHash(row)
                        return copy
                    }
                    return (200, ["status": "ok", "domain": name, "count": enriched.count, "rows": enriched])
                }
                return (200, ["status": "ok", "domain": name, "count": rows.count, "rows": rows])
            }
            return (404, ["error": "דומיין mobile לא נתמך: \(name)"])
        }

        if method == "POST" {
            // כשל שרת חד-פעמי בפעולה — לבדיקת התאוששות וניסיון חוזר.
            if path == failActionOncePath {
                failActionOncePath = nil
                return (500, ["error": "תקלת שרת זמנית בפעולה. נסה שוב."])
            }
            return routeAction(path: path, body: body)
        }
        return (404, ["error": "נתיב לא קיים: \(path)"])
    }

    /// פעולות מוטציה — מעדכנות את הדאטה בזיכרון כדי שהמסך ישקף שינוי אמיתי.
    private func routeAction(path: String, body: [String: Any]) -> (Int, [String: Any]) {
        switch path {
        case "/payments-transfer-paid":
            // נעילה אופטימית — כמו בשרת: hash לא תואם ⇒ 409 conflict.
            if let conflict = paymentsConflictCheck(body) { return conflict }

            let rowNumber = int(body["row_number"])
            let paid = (body["paid"] as? Bool) ?? false
            mutate("payments_transfer") { row in
                if self.int(row["_sheet_row"]) == rowNumber {
                    row["paid"] = paid ? "TRUE" : "FALSE"
                }
            }
            return (200, ["status": "ok"])

        case "/marketing-complete-reminder":
            let reminderID = str(body["reminder_id"])
            mutate("marketing_reminders") { row in
                if self.str(row["reminder_id"]) == reminderID {
                    row["status"] = "completed"
                    row["completed_at"] = "2026-07-04T12:00:00"
                }
            }
            return (200, ["status": "ok"])

        case "/marketing-save-reminder":
            var row = body
            row["reminder_id"] = str(body["reminder_id"]).isEmpty ? UUID().uuidString : str(body["reminder_id"])
            upsert("marketing_reminders", idKey: "reminder_id", row: row)
            return (200, ["status": "ok"])

        case "/marketing-save-note":
            return (200, ["status": "ok"])

        case "/customers-create":
            var row = (body["customer"] as? [String: Any]) ?? [:]
            row["customer_guid"] = UUID().uuidString
            row["active"] = "TRUE"
            domains["customers", default: []].insert(row, at: 0)
            return (200, ["status": "ok", "message": "הלקוח נוצר."])

        case "/customers-update":
            let row = (body["customer"] as? [String: Any]) ?? [:]
            upsert("customers", idKey: "customer_guid", row: row)
            return (200, ["status": "ok", "message": "הלקוח עודכן."])

        case "/customers-delete":
            let customer = (body["customer"] as? [String: Any]) ?? [:]
            let guid = str(customer["customer_guid"])
            remove("customers") { self.str($0["customer_guid"]) == guid }
            remove("inactive_customers") { self.str($0["customer_guid"]) == guid }
            return (200, ["status": "ok", "message": "הלקוח נמחק."])

        case "/customers-set-active":
            let active = self.str(body["active"]).lowercased() == "true" || (body["active"] as? Bool) == true
            let rows = (body["rows"] as? [[String: Any]]) ?? []
            let guids = Set(rows.map { self.str($0["customer_guid"]) })
            let sourceKey = active ? "inactive_customers" : "customers"
            let targetKey = active ? "customers" : "inactive_customers"
            var moved: [[String: Any]] = []
            remove(sourceKey) { row in
                if guids.contains(self.str(row["customer_guid"])) {
                    var updated = row
                    updated["active"] = active ? "TRUE" : "FALSE"
                    moved.append(updated)
                    return true
                }
                return false
            }
            domains[targetKey, default: []].insert(contentsOf: moved, at: 0)
            return (200, ["status": "ok"])

        case "/order-history-delete":
            let id = str(body["history_id"])
            let historyRow = (domains["order_history"] ?? []).first { self.str($0["history_id"]) == id }
            let po = str(historyRow?["po_number"] ?? body["po_number"])
            let invoice = str(historyRow?["tax_invoice_number"] ?? body["tax_invoice_number"])
            remove("order_history") { self.str($0["history_id"]) == id }
            // מחיקה מדורגת — כמו בשרת: תשלומים ואישורי מסירה משויכים נמחקים יחד.
            if !po.isEmpty || !invoice.isEmpty {
                remove("payments_transfer") { row in
                    (!po.isEmpty && self.str(row["po_number"]) == po)
                        || (!invoice.isEmpty && self.str(row["tax_invoice_number"]) == invoice)
                }
                remove("delivery_confirmations") { row in
                    (!po.isEmpty && self.str(row["po_number"]) == po)
                        || (!invoice.isEmpty && self.str(row["tax_invoice_number"]) == invoice)
                }
            }
            return (200, ["status": "ok"])

        case "/quote-history-delete":
            let id = str(body["history_id"])
            remove("quote_history") { self.str($0["history_id"]) == id }
            return (200, ["status": "ok"])

        case "/working-orders-delete":
            let id = str(body["row_id"])
            remove("working_orders") { self.str($0["row_id"]) == id }
            return (200, ["status": "ok"])

        case "/working-orders-note-save":
            // השרת האמיתי מקבל רק multipart form — JSON נדחה, בדיוק כמו שם.
            guard let fields = pendingFormFields, !str(fields["row_id"]).isEmpty else {
                return (400, ["error": "לא הצלחתי לקרוא את נתוני ההערה."])
            }
            let id = str(fields["row_id"])
            mutate("working_orders") { row in
                if self.str(row["row_id"]) == id {
                    row["order_note_text"] = self.str(fields["note_text"])
                }
            }
            return (200, ["status": "ok"])

        case "/finance-invoices-delete":
            let id = str(body["row_id"])
            remove("finance_invoices") { self.str($0["row_id"]) == id }
            return (200, ["status": "ok"])

        case "/hr-employee-save":
            var row = (body["row"] as? [String: Any]) ?? [:]
            if str(row["employee_id"]).isEmpty { row["employee_id"] = UUID().uuidString }
            upsert("hr_employees", idKey: "employee_id", row: row)
            return (200, ["status": "ok"])

        case "/hr-hours-save":
            var row = (body["row"] as? [String: Any]) ?? [:]
            // חוק אמיתי מהשרת: שורת שעות חייבת עובד וחודש.
            guard !str(row["employee_id"]).isEmpty else {
                return (400, ["error": "חסר עובד לשורת השעות."])
            }
            guard !str(row["month_key"]).isEmpty else {
                return (400, ["error": "חסר חודש לשורת השעות."])
            }
            if str(row["row_id"]).isEmpty { row["row_id"] = UUID().uuidString }
            upsert("hr_hours", idKey: "row_id", row: row)
            return (200, ["status": "ok"])

        case "/delivery-confirmations-mark-sent":
            return (200, ["status": "ok", "message": "סומן כנשלח."])

        case "/marketing-send-whatsapp", "/marketing-send-email",
             "/quote-send-whatsapp", "/quote-send-email",
             "/customers-send-email":
            return (200, ["status": "ok", "message": "נשלח בהצלחה."])

        case "/hr-payroll-send-whatsapp":
            // כמו בשרת: row_id וגם phone חובה (24529-24534 ב-app.py).
            guard !str(body["row_id"]).isEmpty else {
                return (400, ["error": "חסר מזהה שורת שכר."])
            }
            guard !str(body["phone"]).isEmpty else {
                return (400, ["error": "חסר מספר טלפון לשליחה."])
            }
            return (200, ["status": "ok", "message": "התלוש נשלח בוואטסאפ."])

        case "/payments-transfer-row":
            var row = (body["row"] as? [String: Any]) ?? [:]
            row["_sheet_row"] = 1000 + (domains["payments_transfer"]?.count ?? 0)
            domains["payments_transfer", default: []].insert(row, at: 0)
            return (200, ["status": "ok"])

        case "/payments-transfer-update-row":
            if let conflict = paymentsConflictCheck(body) { return conflict }

            let rowNumber = int(body["row_number"])
            let updated = (body["row"] as? [String: Any]) ?? [:]
            mutate("payments_transfer") { row in
                if self.int(row["_sheet_row"]) == rowNumber {
                    for (key, value) in updated { row[key] = value }
                }
            }
            return (200, ["status": "ok"])

        case "/payments-transfer-delete-row":
            if let conflict = paymentsConflictCheck(body) { return conflict }

            let rowNumber = int(body["row_number"])
            let paymentRow = (domains["payments_transfer"] ?? []).first { self.int($0["_sheet_row"]) == rowNumber }
            let paymentPO = str(paymentRow?["po_number"])
            let paymentInvoice = str(paymentRow?["tax_invoice_number"])
            remove("payments_transfer") { self.int($0["_sheet_row"]) == rowNumber }
            // מחיקה מדורגת — כמו בשרת.
            if !paymentPO.isEmpty || !paymentInvoice.isEmpty {
                remove("order_history") { row in
                    (!paymentPO.isEmpty && self.str(row["po_number"]) == paymentPO)
                        || (!paymentInvoice.isEmpty && self.str(row["tax_invoice_number"]) == paymentInvoice)
                }
                remove("delivery_confirmations") { row in
                    (!paymentPO.isEmpty && self.str(row["po_number"]) == paymentPO)
                        || (!paymentInvoice.isEmpty && self.str(row["tax_invoice_number"]) == paymentInvoice)
                }
            }
            return (200, ["status": "ok"])

        case "/process":
            // multipart לא מפורסר במדומה — מחזירים הזמנה מפורסרת לדוגמה.
            return (200, [
                "status": "ok",
                "mode": "sandbox",
                "source_file": "sample_po.pdf",
                "source_file_path": "/tmp/mock/sample_po.pdf",
                "po_number": "112999",
                "po_date": "01/07/2026",
                "customer_name": "י.ח. דמרי בניה ופיתוח בעמ",
                "customer_id": "511399388",
                "customer_phone": "08-9939000",
                "delivery_address": "אמנון ליפקין שחק 7",
                "project": "B15 גבעת שמואל",
                "contact_name": "משה",
                "contact_phone": "050-1234567",
                "payment_terms_days": "60",
                "payment_terms_label": "שוטף + 60",
                "subtotal": 4200.0,
                "vat": 714.0,
                "total": 4914.0,
                "items": [
                    ["description": "מגן דלת פרו דור", "sku": "PROD5050", "unit": "יחידה",
                     "quantity": 20, "unit_price": 210, "line_total": 4200, "generate_label": true],
                ],
            ])

        case "/finalize":
            let orderData = (body["data"] as? [String: Any]) ?? [:]
            var historyRow: [String: Any] = [:]
            for (key, value) in orderData { historyRow[key] = value }
            historyRow["history_id"] = UUID().uuidString
            historyRow["created_at"] = "2026-07-04T21:30:00"
            historyRow["mode"] = str(body["mode"]).hasPrefix("prod") ? "PROD" : "SANDBOX"
            historyRow["input_source"] = "מובייל"
            domains["order_history", default: []].insert(historyRow, at: 0)
            // כמו השרת: finalize בפרודקשן מסיר את ההזמנה מ"הזמנות בעבודה".
            let workingOrderRowID = str(orderData["working_order_row_id"])
            if str(body["mode"]).hasPrefix("prod"), !workingOrderRowID.isEmpty {
                remove("working_orders") { self.str($0["row_id"]) == workingOrderRowID }
            }
            let skipWhatsapp = (body["skip_whatsapp"] as? Bool) ?? false
            let message = skipWhatsapp
                ? "המסמכים נוצרו בהצלחה (בלי שליחת וואטסאפ)."
                : "המסמכים נוצרו ונשלחו בוואטסאפ."
            return (200, ["status": "ok", "message": message])

        case "/finalize-quote":
            let quoteData = (body["data"] as? [String: Any]) ?? [:]
            let quoteNumber = "5\(Int.random(in: 1000...9999))"
            var quoteRow: [String: Any] = [:]
            for (key, value) in quoteData { quoteRow[key] = value }
            quoteRow["history_id"] = UUID().uuidString
            quoteRow["quote_number"] = quoteNumber
            quoteRow["quote_date"] = "05/07/2026"
            quoteRow["created_at"] = "2026-07-05T12:00:00"
            quoteRow["mode"] = str(body["mode"]).hasPrefix("prod") ? "PROD" : "SB"
            quoteRow["input_source"] = "מובייל"
            domains["quote_history", default: []].insert(quoteRow, at: 0)
            return (200, [
                "status": "ok", "is_quote": true,
                "quote_document_number": quoteNumber,
                "quote_number": quoteNumber,
                "quote_drive_url": "https://drive.google.com/file/d/mock-quote-\(quoteNumber)",
                "message": "הצעת מחיר \(quoteNumber) נוצרה.",
            ])

        case "/quote-send-whatsapp":
            guard !str(body["phone"]).isEmpty else { return (400, ["error": "חסר טלפון לשליחה."]) }
            return (200, ["status": "ok", "message": "ההצעה נשלחה בוואטסאפ."])

        case "/quote-history-order-data":
            let historyID = str(body["history_id"])
            guard let quote = (domains["quote_history"] ?? []).first(where: { self.str($0["history_id"]) == historyID }) else {
                return (404, ["error": "לא נמצאה הצעה."])
            }
            // כמו בשרת: השורה תחת row ומערך items בצד.
            var orderData = quote
            orderData["po_number"] = ""
            return (200, ["status": "ok", "row": orderData,
                          "items": [["description": "פריט מההצעה", "quantity": 1, "unit_price": 100]]])

        case "/greeninvoice-create-receipt":
            // כמו GreenInvoice: בצ'ק כל ארבעת הפרטים חובה.
            if let payment = body["payment"] as? [String: Any],
               str(payment["payment_method"]) == "check" {
                for key in ["check_number", "bank_number", "branch_number", "account_number"] {
                    if str(payment[key]).isEmpty {
                        return (400, ["error": "בתשלום בצ׳ק צריך למלא מספר צ׳ק, בנק, סניף ומספר חשבון."])
                    }
                }
            }
            if let payment = body["payment"] as? [String: Any],
               str(payment["payment_method"]) == "payment_app",
               !["bit", "paybox"].contains(str(payment["payment_app_provider"]).lowercased()) {
                return (400, ["error": "אפליקציית תשלום לא נתמכת."])
            }
            // אכיפת עקביות הניכוי: withheld = gross*percent, paid = gross-withheld,
            // וסכום התשלום חייב להיות הסכום ששולם בפועל — כמו שהדסקטופ שולח.
            if let withholding = body["withholding"] as? [String: Any],
               (withholding["applied"] as? Bool) == true {
                let gross = (withholding["gross_amount"] as? Double) ?? -1
                let percent = (withholding["percent"] as? Double) ?? 0
                let withheld = (withholding["withheld_amount"] as? Double) ?? -1
                let paid = (withholding["paid_amount"] as? Double) ?? -1
                let paymentAmount = ((body["payment"] as? [String: Any])?["amount"] as? Double) ?? -1
                guard percent > 0,
                      abs(withheld - (gross * percent / 100 * 100).rounded() / 100) < 0.01,
                      abs(paid - (gross - withheld)) < 0.01,
                      abs(paymentAmount - paid) < 0.01 else {
                    return (400, ["error": "פירוק ניכוי המס לא עקבי — הקבלה חייבת להיות על הסכום ששולם בפועל."])
                }
            }
            let receiptInvoice = (body["invoice"] as? [String: Any]) ?? [:]
            guard !str(receiptInvoice["number"]).isEmpty else {
                return (400, ["error": "חסר מספר חשבונית לקבלה."])
            }
            let receiptPayment = (body["payment"] as? [String: Any]) ?? [:]
            guard ((receiptPayment["amount"] as? NSNumber)?.doubleValue ?? 0) > 0 else {
                return (400, ["error": "חסר סכום תשלום."])
            }
            return (200, ["status": "ok", "receipt_number": "R-\(Int.random(in: 100...999))",
                          "message": "הקבלה הופקה."])

        case "/inventory-purchase-orders-create":
            var poRow: [String: Any] = [:]
            for key in ["supplier_name", "supplier_email", "supplier_phone", "remarks"] {
                poRow[key] = str(body[key])
            }
            guard !str(poRow["supplier_name"]).isEmpty else {
                return (400, ["error": "חסר שם ספק."])
            }
            poRow["history_id"] = UUID().uuidString
            poRow["po_number"] = "15\(Int.random(in: 1000...9999))"
            poRow["po_date"] = "2026-07-05"
            poRow["mode"] = str(body["mode"]) == "prod" ? "production" : "sandbox"
            if let firstItem = (body["items"] as? [[String: Any]])?.first {
                poRow["item_description"] = str(firstItem["description"])
                poRow["item_quantity"] = firstItem["quantity"] ?? ""
            }
            poRow["total"] = body["total"] ?? 0
            domains["inventory_purchase_orders", default: []].insert(poRow, at: 0)
            return (200, ["status": "ok", "message": "הזמנת הרכש נוצרה."])

        case "/inventory-purchase-orders-send-whatsapp":
            guard !str(body["phone"]).isEmpty else { return (400, ["error": "חסר טלפון."]) }
            return (200, ["status": "ok", "message": "הזמנת הרכש נשלחה בוואטסאפ."])

        case "/marketing-work-managers-save":
            var wmRow = (body["row"] as? [String: Any]) ?? [:]
            // כמו בשרת: שם מלא הוא חובה.
            guard !str(wmRow["full_name"]).trimmingCharacters(in: .whitespaces).isEmpty else {
                return (400, ["error": "חסר שם מלא."])
            }
            if str(wmRow["row_id"]).isEmpty { wmRow["row_id"] = UUID().uuidString }
            upsert("marketing_work_managers", idKey: "row_id", row: wmRow)
            return (200, ["status": "ok"])

        case "/marketing-construction-companies-save":
            var ccRow = (body["row"] as? [String: Any]) ?? [:]
            guard !str(ccRow["company_name"]).trimmingCharacters(in: .whitespaces).isEmpty else {
                return (400, ["error": "חסר שם חברה."])
            }
            if str(ccRow["row_id"]).isEmpty { ccRow["row_id"] = UUID().uuidString }
            upsert("marketing_construction_companies", idKey: "row_id", row: ccRow)
            return (200, ["status": "ok"])

        case "/finance-customer-withholdings-save":
            var whRow = (body["row"] as? [String: Any]) ?? [:]
            // כמו בשרת: לקוח, מספר קבלה ומספר חשבונית — חובה.
            for (key, message) in [("customer_name", "חסר שם לקוח לשמירת ניכוי המס."),
                                   ("receipt_number", "חסר מספר קבלה לשמירת ניכוי המס."),
                                   ("invoice_number", "חסר מספר חשבונית לשמירת ניכוי המס.")] {
                if str(whRow[key]).trimmingCharacters(in: .whitespaces).isEmpty {
                    return (400, ["error": message])
                }
            }
            if str(whRow["row_id"]).isEmpty { whRow["row_id"] = UUID().uuidString }
            upsert("finance_customer_withholdings", idKey: "row_id", row: whRow)
            return (200, ["status": "ok"])

        case "/labels-only":
            let labels = (body["labels"] as? [[String: Any]]) ?? []
            guard !labels.isEmpty else { return (400, ["error": "חסר מידע מדבקות."]) }
            return (200, ["status": "ok", "message": "\(labels.count) מדבקות נוצרו ונשלחו."])

        case "/admin-business-doc-send-whatsapp":
            return (200, ["status": "ok", "message": "המסמך נשלח בוואטסאפ."])

        case "/supplier-delivery-notes-delete-row":
            let noteRecordID = str(body["record_id"])
            guard (domains["supplier_delivery_notes"] ?? []).contains(where: { self.str($0["record_id"]) == noteRecordID }) else {
                return (404, ["error": "לא נמצאה שורת תעודת משלוח מתאימה."])
            }
            remove("supplier_delivery_notes") { self.str($0["record_id"]) == noteRecordID }
            return (200, ["status": "ok"])

        case "/finance-invoices-upload":
            return (200, [
                "status": "ok",
                "message": "הקבצים נשמרו ופורסרו.",
                "drafts": [
                    ["row_id": "draft-\(UUID().uuidString)", "supplier_name": "ספק בדיקה בעמ",
                     "invoice_date": "01/07/2026", "reference_number": "INV-777",
                     "service_or_product": "חומרי גלם", "subtotal": "1000.00", "vat": "170.00", "total": "1170.00",
                     "source_file_name": "sample_invoice.pdf"],
                ],
            ])

        case "/finance-invoices-send-email":
            // כמו בשרת: מועדי דיווח חובה; בלי מצב בדיקה — נמענים חובה.
            let dueDates = (body["report_due_dates"] as? [Any]) ?? []
            guard !dueDates.isEmpty else {
                return (400, ["error": "יש לבחור לפחות מועד דיווח אחד."])
            }
            let isTest = (body["test_send"] as? Bool) ?? false
            if !isTest, str(body["recipients"]).isEmpty {
                return (400, ["error": "חסרים נמענים לשליחת הריכוז."])
            }
            return (200, ["status": "ok",
                          "message": isTest ? "ריכוז נשלח אליך (בדיקה)." : "ריכוז החשבוניות נשלח."])

        case "/finance-invoices-save":
            var row = (body["row"] as? [String: Any]) ?? [:]
            if str(row["row_id"]).isEmpty { row["row_id"] = UUID().uuidString }
            upsert("finance_invoices", idKey: "row_id", row: row)
            // כמו בשרת: "טרם שולמה" + מספר חשבונית ⇒ שורת "לתשלום" בתשלומים והעברות.
            // ה-endpoint האמיתי קורא supplier_invoice_number מהשורה הנכנסת (לא reference_number).
            let payableFlag = ["1", "true", "yes", "on", "כן"].contains(str(row["create_payable_row"]).lowercased())
            let payableInvoice = str(row["supplier_invoice_number"]).isEmpty
                ? str(row["invoice_number"]) : str(row["supplier_invoice_number"])
            var paymentsSync: [String: Any]? = nil
            if payableFlag, !payableInvoice.isEmpty {
                // כמו בשרת: מספר החשבונית נשמר ב-po_number של שורת התשלום.
                let payableRow: [String: Any] = [
                    "customer_name": str(row["supplier_name"]),
                    "payment_direction": "תשלום",
                    "amount": str(row["total"]),
                    "po_number": payableInvoice,
                    "paid": "FALSE",
                    "notes": "נוצר אוטומטית מחשבונית ספק",
                    "_sheet_title": "תשלומים והעברות 2026",
                    "_sheet_row": 1000 + (domains["payments_transfer"]?.count ?? 0),
                ]
                domains["payments_transfer", default: []].insert(payableRow, at: 0)
                paymentsSync = ["created": true]
            }
            if let paymentsSync {
                return (200, ["status": "ok", "message": "החשבונית נשמרה.", "payments_sync": paymentsSync])
            }
            return (200, ["status": "ok", "message": "החשבונית נשמרה."])

        case "/delivery-confirmations-upload":
            // כמו בשרת: חייבים מזהה מימוש או מספר הזמנה, והקובץ כבר אומת למעלה.
            let uploadFulfillment = str(body["fulfillment_id"])
            let uploadPO = str(body["po_number"])
            guard !uploadFulfillment.isEmpty || !uploadPO.isEmpty else {
                return (400, ["error": "חסר מזהה מימוש או מספר הזמנה לשיוך אישור המסירה."])
            }
            var matched = false
            mutate("delivery_confirmations") { row in
                let hit = (!uploadFulfillment.isEmpty && self.str(row["fulfillment_id"]) == uploadFulfillment)
                    || (uploadFulfillment.isEmpty && self.str(row["po_number"]) == uploadPO)
                if hit {
                    matched = true
                    row["signed_delivery_name"] = "signed-delivery.pdf"
                    row["signed_delivery_drive_file_id"] = "sim-signed-\(UUID().uuidString.prefix(6))"
                }
            }
            guard matched else {
                return (404, ["error": "אישור המסירה לא נמצא."])
            }
            return (200, ["status": "ok", "message": "התעודה החתומה הועלתה."])

        case "/delivery-confirmations-delete-upload":
            let delFulfillment = str(body["fulfillment_id"])
            let delPO = str(body["po_number"])
            mutate("delivery_confirmations") { row in
                let hit = (!delFulfillment.isEmpty && self.str(row["fulfillment_id"]) == delFulfillment)
                    || (delFulfillment.isEmpty && self.str(row["po_number"]) == delPO)
                if hit {
                    row["signed_delivery_name"] = ""
                    row["signed_delivery_drive_file_id"] = ""
                    row["signed_delivery_local_path"] = ""
                }
            }
            return (200, ["status": "ok", "message": "התעודה החתומה נמחקה."])

        case "/delivery-confirmations-send":
            // חוק אמיתי מהשרת: חייבים חשבונית מס + תעודה חתומה.
            let fulfillmentID = str(body["fulfillment_id"])
            let poNumber = str(body["po_number"])
            let row = (domains["delivery_confirmations"] ?? []).first {
                (!fulfillmentID.isEmpty && self.str($0["fulfillment_id"]) == fulfillmentID)
                    || (!poNumber.isEmpty && self.str($0["po_number"]) == poNumber)
            }
            let hasInvoice = !str(row?["tax_invoice_number"]).isEmpty
            let hasSigned = !str(row?["signed_delivery_drive_file_id"]).isEmpty || !str(row?["signed_delivery_name"]).isEmpty
            guard hasInvoice && hasSigned else {
                return (400, ["error": "צריך גם חשבונית מס וגם ת. משלוח חתומה לפני שליחת המייל."])
            }
            let testSend = (body["test_send"] as? Bool) ?? false
            return (200, ["status": "ok", "message": testSend ? "נשלח אליך במצב בדיקה." : "אישור המסירה נשלח ללקוח."])

        case "/installations-case-update":
            let id = str(body["installation_id"])
            // חוק אמיתי: תיק "ממתין" לא קיים בשרת ואי אפשר לעדכן אותו.
            let caseExists = (domains["installation_cases"] ?? []).contains {
                self.str($0["installation_id"]) == id && !id.hasPrefix("pending")
            }
            guard caseExists else {
                return (404, ["error": "תיק ההתקנה לא נמצא."])
            }
            let row = (body["row"] as? [String: Any]) ?? [:]
            mutate("installation_cases") { current in
                if self.str(current["installation_id"]) == id {
                    for key in ["status", "delay_reason", "next_visit_date", "notes"] {
                        current[key] = self.str(row[key])
                    }
                }
            }
            return (200, ["status": "ok"])

        case "/installations-visit-save":
            let visit = (body["visit"] as? [String: Any]) ?? [:]
            var row = visit
            row["visit_id"] = str(visit["visit_id"]).isEmpty ? UUID().uuidString : str(visit["visit_id"])
            row["status"] = "בוצע"
            row["created_at"] = "2026-07-04T21:30:00"
            let quantities = (visit["installed_items"] as? [[String: Any]] ?? [])
                .compactMap { $0["quantity"] as? NSNumber }
                .reduce(0) { $0 + $1.doubleValue }
            row["installed_total_quantity"] = quantities
            row["installed_items"] = nil
            domains["installation_visits", default: []].insert(row.compactMapValues { $0 }, at: 0)
            let installationID = str(visit["installation_id"])
            mutate("installation_cases") { current in
                if self.str(current["installation_id"]) == installationID {
                    current["visit_count"] = self.int(current["visit_count"]) + 1
                    current["last_visit_date"] = self.str(visit["visit_date"])
                }
            }
            return (200, ["status": "ok"])

        case "/installations-visit-delete":
            let id = str(body["visit_id"])
            remove("installation_visits") { self.str($0["visit_id"]) == id }
            return (200, ["status": "ok"])

        case "/customers-assign-domain":
            let rows = (body["rows"] as? [[String: Any]]) ?? []
            let guids = Set(rows.map { self.str($0["customer_guid"]) })
            let domainValue = str(body["customer_domain"])
            for key in ["customers", "inactive_customers"] {
                mutate(key) { current in
                    if guids.contains(self.str(current["customer_guid"])) {
                        current["customer_domain"] = domainValue
                    }
                }
            }
            return (200, ["status": "ok", "customer_domain": domainValue, "updated_count": guids.count])

        case "/admin-business-doc-send-email":
            return (200, ["status": "ok", "message": "המסמך נשלח במייל."])

        case "/quote-send-email":
            guard !str(pendingFormFields?["history_id"]).isEmpty else {
                return (400, ["error": "חסרה הצעה לשליחה."])
            }
            return (200, ["status": "ok", "message": "ההצעה נשלחה במייל."])

        case "/inventory-purchase-orders-send-email":
            guard !str(pendingFormFields?["history_id"]).isEmpty else {
                return (400, ["error": "חסרה הזמנת רכש לשליחה."])
            }
            return (200, ["status": "ok", "message": "הזמנת הרכש נשלחה במייל."])

        case "/quote-history-upload-signed":
            let signedHistoryID = str(pendingFormFields?["history_id"])
            guard !signedHistoryID.isEmpty else {
                return (400, ["error": "חסרה הצעה להעלאה."])
            }
            mutate("quote_history") { row in
                if self.str(row["history_id"]) == signedHistoryID {
                    row["signed_quote_name"] = "signed-quote.pdf"
                }
            }
            return (200, ["status": "ok", "message": "ההצעה החתומה הועלתה."])

        case "/working-orders-upload":
            domains["working_orders", default: []].insert([
                "row_id": UUID().uuidString,
                "customer_name": "הזמנה שהועלתה מהמובייל",
                "source_file_name": "uploaded.pdf",
                "created_at": "2026-07-05T02:30:00",
                "po_date": "05/07/2026",
            ], at: 0)
            return (200, ["status": "ok", "message": "ההזמנה נשמרה בהזמנות בעבודה."])

        case "/hr-employee-delete":
            let employeeID = str(body["employee_id"])
            guard !employeeID.isEmpty else { return (400, ["error": "חסר מזהה עובד."]) }
            remove("hr_employees") { self.str($0["employee_id"]) == employeeID }
            return (200, ["status": "ok"])

        case "/hr-payroll-delete":
            remove("hr_payroll") { self.str($0["row_id"]) == self.str(body["row_id"]) }
            return (200, ["status": "ok"])

        case "/hr-payroll-send-whatsapp":
            guard !str(body["row_id"]).isEmpty else { return (400, ["error": "חסר מזהה תלוש."]) }
            return (200, ["status": "ok", "message": "התלוש נשלח בוואטסאפ."])

        case "/hr-contribution-save":
            var row = (body["row"] as? [String: Any]) ?? [:]
            if str(row["row_id"]).isEmpty { row["row_id"] = UUID().uuidString }
            upsert("hr_contributions", idKey: "row_id", row: row)
            return (200, ["status": "ok"])

        case "/hr-document-delete":
            remove("hr_documents") { self.str($0["row_id"]) == self.str(body["row_id"]) }
            return (200, ["status": "ok"])

        case "/inventory-purchase-orders-delete":
            remove("inventory_purchase_orders") { self.str($0["history_id"]) == self.str(body["history_id"]) }
            return (200, ["status": "ok"])

        case "/marketing-work-managers-delete":
            remove("marketing_work_managers") { self.str($0["row_id"]) == self.str(body["row_id"]) }
            return (200, ["status": "ok"])

        case "/marketing-construction-companies-delete":
            remove("marketing_construction_companies") { self.str($0["row_id"]) == self.str(body["row_id"]) }
            return (200, ["status": "ok"])

        case "/marketing-pipeline-delete":
            remove("marketing_pipeline") { self.str($0["customer_key"]) == self.str(body["customer_key"]) }
            return (200, ["status": "ok"])

        case "/delivery-confirmations-send-coc":
            let cocRow = (domains["delivery_confirmations"] ?? []).first {
                self.str($0["fulfillment_id"]) == self.str(body["fulfillment_id"])
                    || self.str($0["po_number"]) == self.str(body["po_number"])
            }
            guard !str(cocRow?["coc_drive_file_id"]).isEmpty else {
                return (400, ["error": "אין תעודת COC משויכת להזמנה."])
            }
            return (200, ["status": "ok", "message": "תעודת ה-COC נשלחה."])

        default:
            // כל פעולה אחרת נחשבת מוצלחת — מאפשר לחווט כפתורים עתידיים בלי לשבור טסטים.
            return (200, ["status": "ok"])
        }
    }

    // MARK: - עזרי דאטה

    private func mutate(_ domain: String, _ transform: (inout [String: Any]) -> Void) {
        guard var rows = domains[domain] else { return }
        for index in rows.indices {
            transform(&rows[index])
        }
        domains[domain] = rows
    }

    private func remove(_ domain: String, where predicate: ([String: Any]) -> Bool) {
        domains[domain] = (domains[domain] ?? []).filter { !predicate($0) }
    }

    private func upsert(_ domain: String, idKey: String, row: [String: Any]) {
        var rows = domains[domain] ?? []
        let id = str(row[idKey])
        if let index = rows.firstIndex(where: { str($0[idKey]) == id && !id.isEmpty }) {
            for (key, value) in row { rows[index][key] = value }
        } else {
            rows.insert(row, at: 0)
        }
        domains[domain] = rows
    }

    private func str(_ value: Any?) -> String {
        if let text = value as? String { return text }
        if let number = value as? NSNumber { return number.stringValue }
        return ""
    }

    private func int(_ value: Any?) -> Int {
        if let number = value as? Int { return number }
        if let number = value as? NSNumber { return number.intValue }
        if let text = value as? String { return Int(text) ?? -1 }
        return -1
    }

    // MARK: - תשובות מורכבות

    private func authBootstrapPayload() -> [String: Any] {
        [
            "status": "ok",
            "authenticated": authenticated,
            "selected_user_id": "asaf",
            "selected_user_name": "אסף",
            "methods": ["totp": true, "email": true, "passkey": false],
            "auth_users": [
                [
                    "id": "asaf",
                    "display_name": "אסף",
                    "email_address": "asafbeny@gmail.com",
                    "methods": ["totp": true, "email": true, "passkey": false],
                    "setup_required": false,
                ],
                [
                    "id": "reut",
                    "display_name": "רעות",
                    "email_address": "reut@example.com",
                    "methods": ["totp": false, "email": true, "passkey": false],
                    "setup_required": false,
                ],
            ],
        ]
    }

    private func bootstrapPayload() -> [String: Any] {
        let sections: [[String: Any]] = Domain.allCases.map { domain in
            [
                "id": domain.bootstrapSectionID,
                "title": domain.spec.title,
                "count": domains[domain.rawValue]?.count ?? 0,
            ]
        }
        return [
            "status": "ok",
            "generated_at": "2026-07-04T12:00:00",
            "source_label": "backend:mock",
            "sections": sections,
        ]
    }
}
