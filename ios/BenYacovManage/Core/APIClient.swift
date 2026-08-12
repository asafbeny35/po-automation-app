import Foundation

/// שגיאת שרת ידידותית — השרת מחזיר הודעות עברית בשדה `error`.
struct APIError: LocalizedError, Equatable {
    let message: String
    let statusCode: Int

    var errorDescription: String? { message }

    static func from(data: Data, statusCode: Int) -> APIError {
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["error"] as? String, !message.isEmpty {
            return APIError(message: message, statusCode: statusCode)
        }
        return APIError(message: "השרת החזיר שגיאה (\(statusCode)).", statusCode: statusCode)
    }
}

/// שכבת תעבורה — מוחלפת ב-mock בזמן טסטים.
protocol Transport: Sendable {
    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse)
}

struct LiveTransport: Transport {
    let session: URLSession

    init() {
        let configuration = URLSessionConfiguration.default
        // פעולות כבדות (finalize עם מסמכים ווואטסאפ) יכולות לקחת כמה דקות.
        configuration.timeoutIntervalForRequest = 300
        configuration.timeoutIntervalForResource = 600
        configuration.httpCookieAcceptPolicy = .always
        configuration.httpShouldSetCookies = true
        session = URLSession(configuration: configuration)
    }

    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError(message: "תגובת שרת לא תקינה.", statusCode: -1)
        }
        return (data, http)
    }
}

/// לקוח ה-API של האפליקציה. כל הקריאות עוברות דרכו.
final class APIClient: Sendable {
    let baseURL: URL
    private let transport: Transport

    init(baseURL: URL = AppConfig.baseURL, transport: Transport? = nil) {
        self.baseURL = baseURL
        if let transport {
            self.transport = transport
        } else if AppConfig.isUITest {
            self.transport = MockTransport()
        } else {
            self.transport = LiveTransport()
        }
    }

    // MARK: - בקשות בסיס

    func getJSON(_ path: String, query: [String: String] = [:]) async throws -> Data {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        return try await perform(request)
    }

    @discardableResult
    func postJSON(_ path: String, body: [String: Any] = [:]) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request)
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        try await performRaw(request)
    }

    /// ביצוע בקשה גולמית — משמש גם להעלאות multipart ולהורדת קבצים.
    func performRaw(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await transport.send(request)
        guard (200..<300).contains(response.statusCode) else {
            throw APIError.from(data: data, statusCode: response.statusCode)
        }
        return data
    }

    // MARK: - התחברות

    func authBootstrap() async throws -> AuthBootstrap {
        let data = try await getJSON("mobile/auth/bootstrap")
        return try JSONDecoder().decode(AuthBootstrap.self, from: data)
    }

    func verifyTOTP(userID: String, code: String, rememberMe: Bool) async throws {
        try await postJSON("auth/totp/verify", body: [
            "user_id": userID, "code": code, "remember_me": rememberMe,
        ])
    }

    func sendEmailCode(userID: String, rememberMe: Bool) async throws -> String {
        let data = try await postJSON("auth/email/send-code", body: [
            "user_id": userID, "remember_me": rememberMe,
        ])
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = object["message"] as? String {
            return message
        }
        return "נשלח קוד למייל."
    }

    func verifyEmailCode(code: String) async throws {
        try await postJSON("auth/email/verify", body: ["code": code])
    }

    func logout() async throws {
        try await postJSON("auth/logout")
    }

    // MARK: - נתונים

    func bootstrap() async throws -> BootstrapSnapshot {
        let data = try await getJSON("mobile/bootstrap")
        return try JSONDecoder().decode(BootstrapSnapshot.self, from: data)
    }

    func domainRows(_ domain: Domain, forceRefresh: Bool = false) async throws -> [DomainRecord] {
        // התקנות מוגשות מ-endpoint ייעודי שמחזיר תיקים וביקורים יחד.
        if !domain.isMobileDomain {
            let data = try await getJSON("installations-state")
            let decoded = try JSONDecoder().decode([String: JSONValue].self, from: data)
            let key = domain == .installationVisits ? "visits" : "rows"
            guard case .array(let rows)? = decoded[key] else { return [] }
            return rows.compactMap {
                if case .object(let fields) = $0 { return DomainRecord(fields: fields) }
                return nil
            }
        }
        var query: [String: String] = [:]
        if forceRefresh { query["force_refresh"] = "true" }
        let data = try await getJSON("mobile/domains/\(domain.rawValue)", query: query)
        return try DomainRecord.records(fromRowsJSON: data)
    }
}

// MARK: - מודלים של התחברות ותקציר

struct AuthBootstrap: Decodable, Sendable {
    struct User: Decodable, Identifiable, Sendable {
        let id: String
        let displayName: String
        let emailAddress: String
        let methods: Methods
        let setupRequired: Bool

        enum CodingKeys: String, CodingKey {
            case id
            case displayName = "display_name"
            case emailAddress = "email_address"
            case methods
            case setupRequired = "setup_required"
        }
    }

    struct Methods: Decodable, Sendable {
        let totp: Bool
        let email: Bool
        let passkey: Bool

        init(totp: Bool, email: Bool, passkey: Bool) {
            self.totp = totp
            self.email = email
            self.passkey = passkey
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: DynamicKey.self)
            totp = (try? container.decodeIfPresent(Bool.self, forKey: DynamicKey("totp"))) ?? false
            email = (try? container.decodeIfPresent(Bool.self, forKey: DynamicKey("email"))) ?? false
            passkey = (try? container.decodeIfPresent(Bool.self, forKey: DynamicKey("passkey"))) ?? false
        }
    }

    let authenticated: Bool
    let selectedUserID: String
    let selectedUserName: String
    let authUsers: [User]

    enum CodingKeys: String, CodingKey {
        case authenticated
        case selectedUserID = "selected_user_id"
        case selectedUserName = "selected_user_name"
        case authUsers = "auth_users"
    }
}

struct DynamicKey: CodingKey {
    var stringValue: String
    var intValue: Int? { nil }
    init(_ string: String) { stringValue = string }
    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { nil }
}

struct BootstrapSnapshot: Decodable, Equatable, Sendable {
    struct Section: Decodable, Equatable, Identifiable, Sendable {
        let id: String
        let title: String
        let count: Int
    }

    let generatedAt: String
    let sections: [Section]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case sections
    }
}
