import SwiftUI
import LocalAuthentication
import Observation

/// מצב הנעילה הביומטרית — אייפון בלבד, מעל ה-session הקיים.
@Observable
@MainActor
final class BiometricLock {
    static let enabledDefaultsKey = "by-biometric-lock-enabled"

    private let authenticator: BiometricAuthenticating
    private let isPhone: Bool

    /// המסך נעול כרגע (מוצג מסך Face ID).
    var isLocked = false
    var isAuthenticating = false
    var lastAttemptFailed = false

    init(authenticator: BiometricAuthenticating? = nil,
         isPhone: Bool = UIDevice.current.userInterfaceIdiom == .phone) {
        if let authenticator {
            self.authenticator = authenticator
        } else if AppConfig.isUITest {
            self.authenticator = UITestBiometricAuthenticator()
        } else {
            self.authenticator = LiveBiometricAuthenticator()
        }
        self.isPhone = isPhone
        // בטסטי UI המצב נקבע מהסביבה — דטרמיניסטי בין ריצות.
        if AppConfig.isUITest {
            UserDefaults.standard.set(
                ProcessInfo.processInfo.environment["BY_UITEST_FACE_ID_ENABLED"] == "1",
                forKey: Self.enabledDefaultsKey
            )
        }
        // נעילה כבר בעלייה אם ההגנה פעילה — שלא יהבהב תוכן לפני האימות.
        isLocked = isEnabled
    }

    /// ההגנה זמינה רק באייפון עם ביומטריה/קוד מכשיר.
    var isSupported: Bool {
        isPhone && authenticator.isAvailable
    }

    var biometryLabel: String { authenticator.biometryLabel }

    var isEnabled: Bool {
        get {
            isPhone && UserDefaults.standard.bool(forKey: Self.enabledDefaultsKey)
        }
        set {
            UserDefaults.standard.set(newValue, forKey: Self.enabledDefaultsKey)
            if !newValue { isLocked = false }
        }
    }

    /// יציאה לרקע ⇒ נעילה מחדש (כשהתכונה פעילה).
    func lockOnBackground() {
        guard isEnabled else { return }
        isLocked = true
        lastAttemptFailed = false
    }

    func unlock() async {
        guard isLocked, !isAuthenticating else { return }
        isAuthenticating = true
        defer { isAuthenticating = false }
        let success = await authenticator.authenticate(reason: "כניסה לאפליקציית הניהול של בן יעקב")
        if success {
            isLocked = false
            lastAttemptFailed = false
        } else {
            lastAttemptFailed = true
        }
    }

    /// הפעלה מההגדרות — מאמתים פעם אחת לפני שמדליקים, כמו שמקובל.
    func enableAfterVerification() async -> Bool {
        let success = await authenticator.authenticate(reason: "אימות להפעלת הכניסה עם \(biometryLabel)")
        if success { isEnabled = true }
        return success
    }
}

/// מסך הנעילה — מוצג מעל התוכן עד לאימות מוצלח.
struct BiometricLockScreen: View {
    let lock: BiometricLock

    var body: some View {
        ZStack {
            BYTheme.heroGradient.ignoresSafeArea()
            VStack(spacing: 18) {
                Image(systemName: "faceid")
                    .font(.system(size: 56, weight: .light))
                    .foregroundStyle(.white)
                    .accessibilityIdentifier("biometric-lock-screen")
                Text("בן יעקב — ניהול")
                    .font(.byLargeTitle)
                    .foregroundStyle(.white)
                Text("האפליקציה נעולה. הזדהה עם \(lock.biometryLabel) כדי להמשיך.")
                    .font(.byBody)
                    .foregroundStyle(.white.opacity(0.75))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
                if lock.lastAttemptFailed {
                    Label("האימות נכשל — נסה שוב", systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.semibold))
                        .foregroundStyle(.yellow)
                        .accessibilityIdentifier("biometric-failed")
                }
                Button {
                    Haptics.tap()
                    Task { await lock.unlock() }
                } label: {
                    HStack(spacing: 8) {
                        if lock.isAuthenticating {
                            ProgressView().tint(BYTheme.Palette.brand)
                        } else {
                            Image(systemName: "faceid")
                        }
                        Text("פתיחה עם \(lock.biometryLabel)")
                    }
                    .font(.byRowTitle)
                    .padding(.horizontal, 26)
                    .padding(.vertical, 14)
                    .background(.white)
                    .foregroundStyle(BYTheme.Palette.brand)
                    .clipShape(Capsule())
                }
                .disabled(lock.isAuthenticating)
                .accessibilityIdentifier("biometric-unlock")
                .padding(.top, 8)
            }
        }
        // מודאל אמיתי לעץ הנגישות — VoiceOver וטסטים לא רואים את התוכן שמאחור.
        .accessibilityAddTraits(.isModal)
    }
}
