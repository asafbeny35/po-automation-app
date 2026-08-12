import SwiftUI

@main
struct BenYacovManageApp: App {
    @State private var session = SessionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                // האפליקציה עברית בלבד — יישור מלא לימין בכל מסך.
                .environment(\.layoutDirection, .rightToLeft)
                .environment(\.locale, Formatters.hebrewLocale)
                .tint(BYTheme.Palette.brand)
                .preferredColorScheme(nil)
        }
    }
}

struct RootView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.scenePhase) private var scenePhase
    @State private var biometricLock = BiometricLock()

    var body: some View {
        Group {
            switch session.phase {
            case .launching:
                LaunchView()
            case .loggedOut:
                LoginView()
            case .loggedIn:
                MainTabView()
            }
        }
        // כשנעול: התוכן מוסתר גם מעץ הנגישות — פרטיות אמיתית, לא רק כיסוי ויזואלי.
        .accessibilityHidden(biometricLock.isLocked && session.phase != .loggedOut)
        .modifier(ToastPresenter())
        .task { await session.start() }
        // נעילה ביומטרית (אייפון בלבד): מעל התוכן, לא במקום ההתחברות לשרת.
        .overlay {
            if biometricLock.isLocked, session.phase != .loggedOut {
                BiometricLockScreen(lock: biometricLock)
                    .transition(.opacity)
            }
        }
        .environment(biometricLock)
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .background {
                biometricLock.lockOnBackground()
            } else if newPhase == .active, biometricLock.isLocked {
                Task { await biometricLock.unlock() }
            }
        }
        .task {
            if biometricLock.isLocked {
                await biometricLock.unlock()
            }
        }
    }
}

/// מסך פתיחה קצר בזמן בדיקת מצב ההתחברות.
struct LaunchView: View {
    var body: some View {
        ZStack {
            BYTheme.heroGradient.ignoresSafeArea()
            VStack(spacing: 14) {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: 52, weight: .light))
                    .foregroundStyle(.white)
                Text("בן יעקב")
                    .font(.byLargeTitle)
                    .foregroundStyle(.white)
                Text("ניהול העסק")
                    .font(.byBody)
                    .foregroundStyle(.white.opacity(0.7))
                ProgressView()
                    .tint(.white)
                    .padding(.top, 18)
            }
        }
        .accessibilityIdentifier("launch-screen")
    }
}
