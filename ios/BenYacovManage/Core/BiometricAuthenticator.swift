import Foundation
import LocalAuthentication

/// מאמת ביומטרי בר-החלפה — LAContext אמיתי בריצה רגילה, מזויף בטסטים
/// (סימולטור לא מאפשר אוטומציה של Face ID אמיתי).
protocol BiometricAuthenticating: Sendable {
    var isAvailable: Bool { get }
    var biometryLabel: String { get }
    func authenticate(reason: String) async -> Bool
}

struct LiveBiometricAuthenticator: BiometricAuthenticating {
    var isAvailable: Bool {
        LAContext().canEvaluatePolicy(.deviceOwnerAuthentication, error: nil)
    }

    var biometryLabel: String {
        let context = LAContext()
        _ = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
        switch context.biometryType {
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        default: return "קוד המכשיר"
        }
    }

    func authenticate(reason: String) async -> Bool {
        let context = LAContext()
        context.localizedCancelTitle = "ביטול"
        do {
            // deviceOwnerAuthentication — עם נפילה חיננית לקוד המכשיר.
            return try await context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason)
        } catch {
            return false
        }
    }
}

/// מזויף לטסטים: BY_UITEST_FACE_ID=success/fail שולט בתוצאה.
struct UITestBiometricAuthenticator: BiometricAuthenticating {
    var isAvailable: Bool { true }
    var biometryLabel: String { "Face ID" }

    func authenticate(reason: String) async -> Bool {
        ProcessInfo.processInfo.environment["BY_UITEST_FACE_ID"] != "fail"
    }
}
