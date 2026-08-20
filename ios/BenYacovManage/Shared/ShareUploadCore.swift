import Foundation

/// ליבת ההעלאה מגיליון השיתוף — משותפת לאפליקציה הראשית ול-Share Extension.
/// עצמאית לחלוטין (בלי תלות ב-APIClient) כדי שה-Extension יישאר רזה.
enum ShareUploadCore {

    /// קבוצת ה-Keychain המשותפת בין האפליקציה ל-Extension.
    /// עובדת עם פרופיל ה-provisioning הקיים (PRY2S55YGY.* כולל keychain-access-groups)
    /// בלי צורך ברישום App Group בחשבון המפתחים.
    static let keychainAccessGroup = "PRY2S55YGY.com.benyacov.shared"
    static let keychainService = "com.benyacov.shared-session"
    static let cookieKey = "shared-session-cookie-header"
    static let baseURLKey = "shared-base-url"

    enum Kind: String {
        case invoice
        case order
    }

    struct UploadError: LocalizedError, Equatable {
        let message: String
        var errorDescription: String? { message }
    }

    /// חתימת שליחה ניתנת להזרקה — בטסטים מחליפים אותה ב-fake.
    typealias Sender = @Sendable (URLRequest) async throws -> (Data, HTTPURLResponse)

    // MARK: - צד האפליקציה: שיתוף ה-session עם ה-Extension

    /// נקרא מהאפליקציה אחרי כל התחברות מוצלחת — משקף את עוגיות השרת ל-Keychain המשותף.
    static func syncSessionToAppGroup(baseURL: URL) {
        let cookies = HTTPCookieStorage.shared.cookies(for: baseURL) ?? []
        let header = HTTPCookie.requestHeaderFields(with: cookies)["Cookie"] ?? ""
        keychainSet(header, key: cookieKey)
        keychainSet(baseURL.absoluteString, key: baseURLKey)
    }

    /// נקרא מהאפליקציה בהתנתקות — מוחק את ה-session המשותף.
    static func clearSharedSession() {
        keychainSet("", key: cookieKey)
    }

    /// צד ה-Extension: העוגייה ששותפה (ריק = המשתמש לא מחובר).
    static func sharedCookieHeader() -> String {
        keychainGet(cookieKey) ?? ""
    }

    static func sharedBaseURL() -> URL {
        if let text = keychainGet(baseURLKey), let url = URL(string: text) {
            return url
        }
        return URL(string: "https://poautomationapp.vercel.app")!
    }

    // MARK: - Keychain משותף

    private static func baseQuery(key: String, withGroup: Bool) -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
        ]
        if withGroup {
            query[kSecAttrAccessGroup as String] = keychainAccessGroup
        }
        return query
    }

    private static func keychainSet(_ value: String, key: String) {
        // קודם עם קבוצת הגישה המשותפת; אם ה-entitlement חסר (טסטים/סביבות חריגות) — בלי.
        for withGroup in [true, false] {
            var query = baseQuery(key: key, withGroup: withGroup)
            SecItemDelete(query as CFDictionary)
            query[kSecValueData as String] = Data(value.utf8)
            query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            let status = SecItemAdd(query as CFDictionary, nil)
            if status == errSecSuccess { return }
        }
    }

    private static func keychainGet(_ key: String) -> String? {
        for withGroup in [true, false] {
            var query = baseQuery(key: key, withGroup: withGroup)
            query[kSecReturnData as String] = true
            query[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: AnyObject?
            if SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
               let data = result as? Data {
                return String(decoding: data, as: UTF8.self)
            }
        }
        return nil
    }

    // MARK: - העלאות

    /// מעלה קובץ ששותף, לפי הסוג שנבחר. מחזיר הודעת הצלחה בעברית.
    /// `markUnpaid` (חשבונית בלבד): כמו הטוגל "טרם שולמה" בדסקטופ — החשבונית
    /// מצטרפת גם לטבלת "לתשלום" בתשלומים והעברות.
    /// אחרי התקנה מחדש של האפליקציה ה-Keychain המשותף יכול לחזור ריק, וה-Extension
    /// נשאר בלי session עד שנפתחת האפליקציה הראשית פעם אחת. עדיף לומר את זה מיד
    /// מאשר להעלות קובץ שלם ואז ליפול על 401.
    private static func requireSession(_ cookieHeader: String) throws {
        guard !cookieHeader.isEmpty else {
            throw UploadError(message: "אין התחברות פעילה — פתח את אפליקציית בן יעקב, התחבר ונסה שוב.")
        }
    }

    static func upload(kind: Kind, fileData: Data, filename: String, mimeType: String,
                       markUnpaid: Bool = false,
                       requiresInstallation: Bool = false,
                       baseURL: URL, cookieHeader: String, send: Sender) async throws -> String {
        try requireSession(cookieHeader)
        switch kind {
        case .order:
            // עולה כהזמנה בעבודה — מחכה להשלמה בטאב הזמנות.
            _ = try await postMultipart(
                path: "working-orders-upload",
                fields: [("requires_installation", requiresInstallation ? "true" : "")],
                fileField: "file", fileData: fileData, filename: filename, mimeType: mimeType,
                baseURL: baseURL, cookieHeader: cookieHeader, send: send
            )
            return requiresInstallation
                ? "ההזמנה הועלתה להזמנות בעבודה וסומנה כדורשת התקנה."
                : "ההזמנה הועלתה להזמנות בעבודה. ההשלמה — בטאב הזמנות באפליקציה."

        case .invoice:
            // העלאה → טיוטות מפורסרות → שמירה אוטומטית לטאב כספים.
            let uploadData = try await postMultipart(
                path: "finance-invoices-upload",
                fields: [],
                fileField: "files", fileData: fileData, filename: filename, mimeType: mimeType,
                baseURL: baseURL, cookieHeader: cookieHeader, send: send
            )
            guard let object = try? JSONSerialization.jsonObject(with: uploadData) as? [String: Any],
                  let drafts = object["drafts"] as? [[String: Any]], !drafts.isEmpty else {
                throw UploadError(message: "החשבונית הועלתה אבל הפרסור לא החזיר טיוטה — נסה מתוך האפליקציה.")
            }
            var savedSuppliers: [String] = []
            for draft in drafts {
                var row = draft
                if markUnpaid {
                    row["create_payable_row"] = "TRUE"
                    // ה-endpoint קורא supplier_invoice_number מהשורה הנכנסת — משלימים
                    // מ-reference_number אם הפרסור שם אותו שם.
                    let invoiceNumber = (row["supplier_invoice_number"] as? String) ?? ""
                    if invoiceNumber.isEmpty {
                        row["supplier_invoice_number"] = (row["reference_number"] as? String) ?? ""
                    }
                }
                _ = try await postJSON(
                    path: "finance-invoices-save", body: ["row": row],
                    baseURL: baseURL, cookieHeader: cookieHeader, send: send
                )
                let supplier = (draft["supplier_name"] as? String) ?? ""
                if !supplier.isEmpty { savedSuppliers.append(supplier) }
            }
            let suffix = savedSuppliers.isEmpty ? "" : " (\(savedSuppliers.joined(separator: ", ")))"
            return markUnpaid
                ? "החשבונית נשמרה בטאב כספים\(suffix) ונוספה גם ל'לתשלום' בתשלומים והעברות."
                : "החשבונית נשמרה בטאב כספים\(suffix)."
        }
    }

    // MARK: - אישורי מסירה מהשיתוף

    /// רשומת אישור מסירה פתוחה (שטרם נשלחה ללקוח) — היעד להעלאת תעודה חתומה.
    struct DeliveryTarget: Identifiable, Equatable {
        let fulfillmentID: String
        let poNumber: String
        let taxInvoiceNumber: String
        let sourceMode: String
        let company: String
        let targetEmail: String

        var id: String { fulfillmentID.isEmpty ? poNumber : fulfillmentID }
        var displayTitle: String { company.isEmpty ? "הזמנה \(poNumber)" : company }
        var displaySubtitle: String {
            var parts: [String] = []
            if !poNumber.isEmpty { parts.append("הזמנה \(poNumber)") }
            if !taxInvoiceNumber.isEmpty { parts.append("חשבונית \(taxInvoiceNumber)") }
            return parts.joined(separator: " · ")
        }
    }

    /// שולף את אישורי המסירה הפתוחים (sent ≠ TRUE) — היעדים האפשריים להעלאה.
    static func fetchOpenDeliveryConfirmations(baseURL: URL, cookieHeader: String,
                                               send: Sender) async throws -> [DeliveryTarget] {
        guard !cookieHeader.isEmpty else {
            throw UploadError(message: "אין התחברות פעילה — פתח את אפליקציית בן יעקב, התחבר ונסה שוב.")
        }
        try requireSession(cookieHeader)
        var request = URLRequest(url: baseURL.appendingPathComponent("mobile/domains/delivery_confirmations"))
        request.httpMethod = "GET"
        request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
        let data = try await perform(request, send: send)
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let rows = object["rows"] as? [[String: Any]] else {
            throw UploadError(message: "לא הצלחתי לטעון את רשימת אישורי המסירה.")
        }
        func str(_ value: Any?) -> String { (value as? String) ?? "" }
        return rows
            .filter { str($0["sent"]).uppercased() != "TRUE" }
            .map { row in
                DeliveryTarget(
                    fulfillmentID: str(row["fulfillment_id"]),
                    poNumber: str(row["po_number"]),
                    taxInvoiceNumber: str(row["tax_invoice_number"]),
                    sourceMode: str(row["source_mode"]),
                    company: str(row["company"]),
                    targetEmail: str(row["target_email"])
                )
            }
    }

    /// מעלה את הקובץ ששותף כתעודת משלוח חתומה לרשומה שנבחרה.
    static func uploadSignedDelivery(to target: DeliveryTarget,
                                     fileData: Data, filename: String, mimeType: String,
                                     baseURL: URL, cookieHeader: String, send: Sender) async throws {
        try requireSession(cookieHeader)
        _ = try await postMultipart(
            path: "delivery-confirmations-upload",
            query: [
                ("fulfillment_id", target.fulfillmentID),
                ("po_number", target.poNumber),
                ("tax_invoice_number", target.taxInvoiceNumber),
                ("source_mode", target.sourceMode),
            ],
            fields: [],
            fileField: "file", fileData: fileData, filename: filename, mimeType: mimeType,
            baseURL: baseURL, cookieHeader: cookieHeader, send: send
        )
    }

    /// שליחה אמיתית ללקוח — אופציונלית, אחרי ההעלאה. נושא/גוף ריקים ⇒ הנוסח
    /// הקנוני של השרת; נמענים ריקים ⇒ השרת נופל חזרה ל-target_email של הרשומה.
    static func sendDeliveryConfirmation(for target: DeliveryTarget,
                                         baseURL: URL, cookieHeader: String,
                                         send: Sender) async throws -> String {
        try requireSession(cookieHeader)
        let data = try await postJSON(path: "delivery-confirmations-send", body: [
            "fulfillment_id": target.fulfillmentID,
            "po_number": target.poNumber,
            "tax_invoice_number": target.taxInvoiceNumber,
            "source_mode": target.sourceMode,
            "mode": "prod",
            "test_send": false,
            "subject": "",
            "message": "",
            "recipients": "",
        ], baseURL: baseURL, cookieHeader: cookieHeader, send: send)
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String, !message.isEmpty {
            return message
        }
        return "אישור המסירה נשלח ללקוח."
    }

    // MARK: - HTTP מינימלי

    private static func postJSON(path: String, body: [String: Any],
                                 baseURL: URL, cookieHeader: String, send: Sender) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request, send: send)
    }

    private static func postMultipart(path: String, query: [(String, String)] = [],
                                      fields: [(String, String)],
                                      fileField: String, fileData: Data, filename: String, mimeType: String,
                                      baseURL: URL, cookieHeader: String, send: Sender) async throws -> Data {
        let boundary = "by-share-\(UUID().uuidString)"
        var body = Data()
        for (name, value) in fields {
            body.append(Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n".utf8))
        }
        body.append(Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(fileField)\"; filename=\"\(filename)\"\r\nContent-Type: \(mimeType)\r\n\r\n".utf8))
        body.append(fileData)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))

        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.0, value: $0.1) }
        }
        var request = URLRequest(url: components.url!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
        request.httpBody = body
        return try await perform(request, send: send)
    }

    private static func perform(_ request: URLRequest, send: Sender) async throws -> Data {
        let (data, response): (Data, HTTPURLResponse)
        do {
            (data, response) = try await send(request)
        } catch let error as UploadError {
            throw error
        } catch {
            throw UploadError(message: "אין חיבור לשרת — בדוק רשת ונסה שוב.")
        }
        if response.statusCode == 401 {
            throw UploadError(message: "ההתחברות פגה — פתח את אפליקציית בן יעקב, התחבר ונסה שוב.")
        }
        guard (200..<300).contains(response.statusCode) else {
            if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let message = object["error"] as? String, !message.isEmpty {
                throw UploadError(message: message)
            }
            throw UploadError(message: "השרת החזיר שגיאה (\(response.statusCode)).")
        }
        return data
    }
}
