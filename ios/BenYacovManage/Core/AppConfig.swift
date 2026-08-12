import Foundation

/// קונפיגורציית ריצה — כתובת שרת ומצב טסטים.
enum AppConfig {
    /// מזהה session יציב לריצת האפליקציה — לנוכחות עריכה ולנעילה האופטימית בתשלומים.
    static let sessionID = UUID().uuidString

    /// כתובת השרת. ניתנת לדריסה דרך משתני סביבה (לטסטים ולפיתוח מקומי).
    static var baseURL: URL {
        if let override = ProcessInfo.processInfo.environment["BY_BASE_URL"],
           let url = URL(string: override) {
            return url
        }
        if let configured = Bundle.main.object(forInfoDictionaryKey: "BACKEND_API_BASE_URL") as? String,
           let url = URL(string: configured) {
            return url
        }
        return URL(string: "https://poautomationapp.vercel.app")!
    }

    /// מצב טסטי UI — האפליקציה עובדת מול שרת מדומה בזיכרון.
    static var isUITest: Bool {
        ProcessInfo.processInfo.environment["BY_UITEST"] == "1"
    }

    /// בטסטי UI אפשר להתחיל ישר כמחוברים כדי לבדוק מסכים פנימיים.
    static var uiTestStartsAuthenticated: Bool {
        ProcessInfo.processInfo.environment["BY_UITEST_AUTHENTICATED"] == "1"
    }
}
