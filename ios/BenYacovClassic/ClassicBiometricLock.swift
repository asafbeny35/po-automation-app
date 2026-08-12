import SwiftUI
import Combine

/// נעילה ביומטרית לקלאסי — Touch ID של האייפד, ObservableObject (iOS 16).
/// אותה מכונת מצבים כמו ה-BiometricLock של האפליקציה הראשית.
@MainActor
final class ClassicBiometricLock: ObservableObject {
    static let enabledDefaultsKey = "classic-biometric-lock-enabled"

    private let authenticator: BiometricAuthenticating

    @Published var isLocked = false
    @Published var isAuthenticating = false
    @Published var lastAttemptFailed = false

    init(authenticator: BiometricAuthenticating? = nil) {
        if let authenticator {
            self.authenticator = authenticator
        } else if AppConfig.isUITest {
            self.authenticator = UITestBiometricAuthenticator()
        } else {
            self.authenticator = LiveBiometricAuthenticator()
        }
        if AppConfig.isUITest {
            UserDefaults.standard.set(
                ProcessInfo.processInfo.environment["BY_UITEST_FACE_ID_ENABLED"] == "1",
                forKey: Self.enabledDefaultsKey
            )
        }
        isLocked = isEnabled
    }

    var isSupported: Bool { authenticator.isAvailable }
    var biometryLabel: String { authenticator.biometryLabel }

    var isEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: Self.enabledDefaultsKey) }
        set {
            UserDefaults.standard.set(newValue, forKey: Self.enabledDefaultsKey)
            if !newValue { isLocked = false }
        }
    }

    func lockOnBackground() {
        guard isEnabled else { return }
        isLocked = true
        lastAttemptFailed = false
    }

    func unlock() async {
        guard isLocked, !isAuthenticating else { return }
        isAuthenticating = true
        defer { isAuthenticating = false }
        let success = await authenticator.authenticate(reason: "כניסה לבן יעקב קלאסי")
        if success {
            isLocked = false
            lastAttemptFailed = false
        } else {
            lastAttemptFailed = true
        }
    }

    func enableAfterVerification() async -> Bool {
        let success = await authenticator.authenticate(reason: "אימות להפעלת הכניסה עם \(biometryLabel)")
        if success { isEnabled = true }
        return success
    }
}

/// מסך הנעילה של קלאסי.
struct ClassicLockScreen: View {
    @ObservedObject var lock: ClassicBiometricLock

    var body: some View {
        ZStack {
            ClassicTheme.hero.ignoresSafeArea()
            VStack(spacing: 16) {
                Image(systemName: "touchid")
                    .font(.system(size: 52, weight: .light))
                    .foregroundColor(.white)
                    .accessibilityIdentifier("classic-lock-screen")
                Text("בן יעקב — קלאסי")
                    .font(.largeTitle.bold())
                    .foregroundColor(.white)
                Text("האפליקציה נעולה. הזדהה עם \(lock.biometryLabel) כדי להמשיך.")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.75))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
                if lock.lastAttemptFailed {
                    Label("האימות נכשל — נסה שוב", systemImage: "exclamationmark.triangle.fill")
                        .font(.subheadline.weight(.semibold))
                        .foregroundColor(.yellow)
                        .accessibilityIdentifier("classic-lock-failed")
                }
                Button {
                    Task { await lock.unlock() }
                } label: {
                    HStack(spacing: 8) {
                        if lock.isAuthenticating {
                            ProgressView().tint(ClassicTheme.brand)
                        } else {
                            Image(systemName: "touchid")
                        }
                        Text("פתיחה עם \(lock.biometryLabel)")
                    }
                    .font(.headline)
                    .padding(.horizontal, 26)
                    .padding(.vertical, 14)
                    .background(Color.white, in: Capsule())
                    .foregroundColor(ClassicTheme.brand)
                }
                .disabled(lock.isAuthenticating)
                .accessibilityIdentifier("classic-unlock")
                .padding(.top, 8)
            }
        }
        .accessibilityAddTraits(.isModal)
    }
}
