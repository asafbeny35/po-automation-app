import SwiftUI
import Observation

/// מצב טעינה גנרי למסכים.
enum LoadState<Value>: Equatable where Value: Equatable {
    case idle
    case loading
    case loaded(Value)
    case failed(String)

    var value: Value? {
        if case .loaded(let value) = self { return value }
        return nil
    }

    var errorMessage: String? {
        if case .failed(let message) = self { return message }
        return nil
    }

    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }
}

/// המצב הגלובלי של האפליקציה: התחברות, תקציר, ומטמון דומיינים.
@Observable
@MainActor
final class SessionStore {
    enum Phase: Equatable {
        case launching
        case loggedOut
        case loggedIn
    }

    let api: APIClient
    var phase: Phase = .launching
    var authBootstrap: AuthBootstrap?
    var currentUserName: String = ""
    var bootstrap: LoadState<BootstrapSnapshot> = .idle
    var domainStates: [Domain: LoadState<[DomainRecord]>] = [:]
    /// הודעת טוסט גלובלית (הצלחות ושגיאות של פעולות).
    var toast: ToastMessage?

    init(api: APIClient = APIClient()) {
        self.api = api
    }

    struct ToastMessage: Equatable, Identifiable {
        enum Style { case success, error }
        let id = UUID()
        let text: String
        let style: Style
    }

    func showSuccess(_ text: String) {
        toast = ToastMessage(text: text, style: .success)
        Haptics.success()
    }

    func showError(_ text: String) {
        toast = ToastMessage(text: text, style: .error)
        Haptics.error()
    }

    // MARK: - התחברות

    func start() async {
        do {
            let bootstrap = try await api.authBootstrap()
            authBootstrap = bootstrap
            currentUserName = bootstrap.selectedUserName
            phase = bootstrap.authenticated ? .loggedIn : .loggedOut
            if bootstrap.authenticated {
                // משתף את עוגיית ה-session עם ה-Share Extension דרך ה-App Group.
                ShareUploadCore.syncSessionToAppGroup(baseURL: api.baseURL)
            }
        } catch {
            // אין רשת או שרת לא זמין — מציגים מסך התחברות עם שגיאה.
            phase = .loggedOut
        }
    }

    func didAuthenticate(userName: String) {
        currentUserName = userName
        phase = .loggedIn
        ShareUploadCore.syncSessionToAppGroup(baseURL: api.baseURL)
        Haptics.success()
    }

    func logout() async {
        try? await api.logout()
        ShareUploadCore.clearSharedSession()
        phase = .loggedOut
        bootstrap = .idle
        domainStates = [:]
    }

    // MARK: - נתונים

    /// פקיעת התחברות (401) — חזרה מסודרת למסך ההתחברות מכל מקום באפליקציה.
    @discardableResult
    private func handleAuthExpiry(_ error: Error) -> Bool {
        guard let apiError = error as? APIError, apiError.statusCode == 401 else { return false }
        phase = .loggedOut
        bootstrap = .idle
        domainStates = [:]
        showError("פג תוקף ההתחברות — יש להתחבר מחדש.")
        return true
    }

    func loadBootstrap(force: Bool = false) async {
        if !force, case .loaded = bootstrap { return }
        if !force { bootstrap = .loading }
        do {
            bootstrap = .loaded(try await api.bootstrap())
        } catch {
            if handleAuthExpiry(error) { return }
            bootstrap = .failed(friendlyMessage(error))
        }
    }

    func state(for domain: Domain) -> LoadState<[DomainRecord]> {
        domainStates[domain] ?? .idle
    }

    func records(for domain: Domain) -> [DomainRecord] {
        state(for: domain).value ?? []
    }

    /// טוען דומיין. `force` מרענן גם אם כבר טעון (משיכה לרענון).
    func loadDomain(_ domain: Domain, force: Bool = false) async {
        if !force, case .loaded = state(for: domain) { return }
        if state(for: domain).value == nil { domainStates[domain] = .loading }
        do {
            // force = רענון יזום (משיכה/אחרי מוטציה) — מדלג גם על קאש השרת.
            let rows = try await api.domainRows(domain, forceRefresh: force)
            domainStates[domain] = .loaded(rows)
        } catch {
            if handleAuthExpiry(error) { return }
            if let existing = state(for: domain).value {
                // יש דאטה קיים — משאירים אותו ומציגים שגיאה עדינה.
                domainStates[domain] = .loaded(existing)
                showError(friendlyMessage(error))
            } else {
                domainStates[domain] = .failed(friendlyMessage(error))
            }
        }
    }

    /// מריץ פעולת שרת, מרענן דומיינים רלוונטיים ומציג טוסט.
    @discardableResult
    func perform(_ successMessage: String,
                 refreshing: [Domain] = [],
                 action: @escaping () async throws -> Void) async -> Bool {
        do {
            try await action()
            for domain in refreshing {
                await loadDomain(domain, force: true)
            }
            showSuccess(successMessage)
            return true
        } catch {
            if handleAuthExpiry(error) { return false }
            if let apiError = error as? APIError, apiError.statusCode == 409 {
                // נעילה אופטימית: מישהו שינה את השורה במקביל — מרעננים כדי להציג את המצב העדכני.
                for domain in refreshing {
                    await loadDomain(domain, force: true)
                }
            }
            showError(friendlyMessage(error))
            return false
        }
    }

    nonisolated private func friendlyMessage(_ error: Error) -> String {
        if let apiError = error as? APIError { return apiError.message }
        if (error as NSError).domain == NSURLErrorDomain {
            return "אין חיבור לשרת. בדוק את הרשת ונסה שוב."
        }
        return "משהו השתבש: \(error.localizedDescription)"
    }
}
