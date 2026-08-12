import SwiftUI
import Combine

/// ה-store של גרסת הקלאסיק — ObservableObject (iOS 16), אותה ליבת API
/// והתנהגות כמו SessionStore של האפליקציה הראשית, בלי Observation של iOS 17.
@MainActor
final class ClassicSession: ObservableObject {
    enum Phase: Equatable {
        case launching
        case loggedOut
        case loggedIn
    }

    struct Toast: Equatable, Identifiable {
        enum Style { case success, error }
        let id = UUID()
        let text: String
        let style: Style
    }

    /// המשתמש האחרון שהשלים התחברות — הדיפולט במסך הכניסה הבא.
    static let lastUserDefaultsKey = "classic-last-user-id"

    let api: APIClient
    @Published var phase: Phase = .launching
    @Published var authBootstrap: AuthBootstrap?
    @Published var currentUserName = ""
    @Published var domainStates: [Domain: ClassicLoadState] = [:]
    @Published var toast: Toast?

    init(api: APIClient = APIClient()) {
        self.api = api
        // דטרמיניזם בטסטי UI: המשתמש האחרון נקבע מהסביבה (או מתאפס).
        if AppConfig.isUITest {
            if let seeded = ProcessInfo.processInfo.environment["BY_UITEST_LAST_USER"] {
                UserDefaults.standard.set(seeded, forKey: Self.lastUserDefaultsKey)
            } else {
                UserDefaults.standard.removeObject(forKey: Self.lastUserDefaultsKey)
            }
        }
    }

    var lastLoggedInUserID: String? {
        UserDefaults.standard.string(forKey: Self.lastUserDefaultsKey)
    }

    // MARK: - התחברות

    func start() async {
        do {
            let bootstrap = try await api.authBootstrap()
            authBootstrap = bootstrap
            currentUserName = bootstrap.selectedUserName
            phase = bootstrap.authenticated ? .loggedIn : .loggedOut
        } catch {
            phase = .loggedOut
        }
    }

    func didAuthenticate(userName: String, userID: String = "") {
        currentUserName = userName
        if !userID.isEmpty {
            UserDefaults.standard.set(userID, forKey: Self.lastUserDefaultsKey)
        }
        phase = .loggedIn
    }

    func logout() async {
        try? await api.logout()
        phase = .loggedOut
        domainStates = [:]
    }

    // MARK: - נתונים

    func state(for domain: Domain) -> ClassicLoadState {
        domainStates[domain] ?? .idle
    }

    func records(for domain: Domain) -> [DomainRecord] {
        if case .loaded(let rows) = state(for: domain) { return rows }
        return []
    }

    func loadDomain(_ domain: Domain, force: Bool = false) async {
        if !force, case .loaded = state(for: domain) { return }
        if case .loading = state(for: domain) { return }
        if !force { domainStates[domain] = .loading }
        do {
            let rows = try await api.domainRows(domain, forceRefresh: force)
            domainStates[domain] = .loaded(rows)
        } catch {
            if handleAuthExpiry(error) { return }
            domainStates[domain] = .failed(friendlyMessage(error))
        }
    }

    // MARK: - פעולות

    @discardableResult
    func perform(_ successMessage: String, refreshing: [Domain] = [],
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
                // נעילה אופטימית — מרעננים כדי להציג את המצב העדכני, כמו באפליקציה הראשית.
                for domain in refreshing {
                    await loadDomain(domain, force: true)
                }
            }
            showError(friendlyMessage(error))
            return false
        }
    }

    func showSuccess(_ text: String) { toast = Toast(text: text, style: .success) }
    func showError(_ text: String) { toast = Toast(text: text, style: .error) }

    private func handleAuthExpiry(_ error: Error) -> Bool {
        guard let apiError = error as? APIError, apiError.statusCode == 401 else { return false }
        phase = .loggedOut
        domainStates = [:]
        toast = Toast(text: "ההתחברות פגה — יש להתחבר מחדש.", style: .error)
        return true
    }

    private nonisolated func friendlyMessage(_ error: Error) -> String {
        if let apiError = error as? APIError { return apiError.message }
        if (error as NSError).domain == NSURLErrorDomain {
            return "אין חיבור לשרת. בדוק את הרשת ונסה שוב."
        }
        return "משהו השתבש: \(error.localizedDescription)"
    }
}

/// מצב טעינה — עותק 16-תואם (בלי גנריות של ה-LoadState הראשי, לפשטות).
enum ClassicLoadState: Equatable {
    case idle
    case loading
    case loaded([DomainRecord])
    case failed(String)
}
