import SwiftUI

@main
struct BenYacovClassicApp: App {
    @StateObject private var session = ClassicSession()

    var body: some Scene {
        WindowGroup {
            ClassicRootView()
                .environmentObject(session)
                .environment(\.layoutDirection, .rightToLeft)
                .environment(\.locale, Locale(identifier: "he_IL"))
                .tint(ClassicTheme.brand)
        }
    }
}

struct ClassicRootView: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var biometricLock = ClassicBiometricLock()

    var body: some View {
        Group {
            switch session.phase {
            case .launching:
                ClassicLaunchView()
            case .loggedOut:
                ClassicLoginView()
            case .loggedIn:
                ClassicMainView()
            }
        }
        .overlay(alignment: .top) {
            if let toast = session.toast {
                ClassicToast(toast: toast)
                    .padding(.top, 8)
                    .task(id: toast.id) {
                        try? await Task.sleep(nanoseconds: 3_000_000_000)
                        if session.toast?.id == toast.id { session.toast = nil }
                    }
            }
        }
        .task { await session.start() }
        .overlay {
            if biometricLock.isLocked, session.phase != .loggedOut {
                ClassicLockScreen(lock: biometricLock)
                    .transition(.opacity)
            }
        }
        .environmentObject(biometricLock)
        .onChange(of: scenePhase) { newPhase in
            if newPhase == .background {
                biometricLock.lockOnBackground()
            } else if newPhase == .active, biometricLock.isLocked {
                Task { await biometricLock.unlock() }
            }
        }
        .task {
            if biometricLock.isLocked { await biometricLock.unlock() }
        }
    }
}

struct ClassicLaunchView: View {
    var body: some View {
        ZStack {
            ClassicTheme.hero.ignoresSafeArea()
            VStack(spacing: 12) {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: 52, weight: .light))
                    .foregroundColor(.white)
                Text("בן יעקב — קלאסי")
                    .font(.largeTitle.bold())
                    .foregroundColor(.white)
                ProgressView().tint(.white).padding(.top, 14)
            }
        }
        .accessibilityIdentifier("classic-launch")
    }
}

struct ClassicToast: View {
    let toast: ClassicSession.Toast

    var body: some View {
        Label(toast.text, systemImage: toast.style == .success ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background((toast.style == .success ? Color.green : Color.red).opacity(0.92),
                        in: Capsule())
            .foregroundColor(.white)
            .accessibilityIdentifier("classic-toast")
    }
}

/// ערכת צבעים מינימלית לקלאסיק — ללא תלות ב-BYTheme של האפליקציה הראשית.
enum ClassicTheme {
    static let brand = Color(red: 0.13, green: 0.32, blue: 0.65)
    static let hero = LinearGradient(
        colors: [Color(red: 0.10, green: 0.22, blue: 0.45), Color(red: 0.15, green: 0.38, blue: 0.72)],
        startPoint: .top, endPoint: .bottom
    )
    static let screen = Color(uiColor: .systemGroupedBackground)
    static let card = Color(uiColor: .secondarySystemGroupedBackground)
}
