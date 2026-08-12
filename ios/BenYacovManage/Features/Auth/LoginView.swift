import SwiftUI

/// מסך התחברות — בחירת משתמש ואימות בקוד (אפליקציית אימות או מייל).
struct LoginView: View {
    @Environment(SessionStore.self) private var session

    enum Method: String, CaseIterable, Identifiable {
        case totp, email
        var id: String { rawValue }

        var title: String {
            switch self {
            case .totp: return "אפליקציית אימות"
            case .email: return "קוד למייל"
            }
        }

        var icon: String {
            switch self {
            case .totp: return "lock.shield.fill"
            case .email: return "envelope.fill"
            }
        }
    }

    @State private var selectedUserID: String = ""
    @State private var method: Method = .totp
    @State private var code: String = ""
    @State private var rememberMe = true
    @State private var isWorking = false
    @State private var emailCodeSent = false
    @State private var statusMessage: String?
    @State private var errorMessage: String?
    @FocusState private var codeFocused: Bool

    private var users: [AuthBootstrap.User] { session.authBootstrap?.authUsers ?? [] }
    private var selectedUser: AuthBootstrap.User? {
        users.first { $0.id == selectedUserID } ?? users.first
    }

    var body: some View {
        ZStack {
            BYTheme.heroGradient.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 24) {
                    header
                    card
                }
                .padding(20)
                .padding(.top, 40)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
        .onAppear {
            if selectedUserID.isEmpty {
                selectedUserID = session.authBootstrap?.selectedUserID ?? users.first?.id ?? "asaf"
                syncMethod()
            }
        }
        .accessibilityIdentifier("login-screen")
    }

    private var header: some View {
        VStack(spacing: 10) {
            Image(systemName: "shield.lefthalf.filled")
                .font(.system(size: 44, weight: .light))
                .foregroundStyle(.white)
            Text("בן יעקב")
                .font(.byLargeTitle)
                .foregroundStyle(.white)
            Text("מערכת ניהול העסק")
                .font(.byBody)
                .foregroundStyle(.white.opacity(0.75))
        }
    }

    private var card: some View {
        VStack(alignment: .leading, spacing: 20) {
            if users.count > 1 {
                userPicker
            }
            methodPicker
            codeSection
            if let statusMessage {
                Label(statusMessage, systemImage: "checkmark.circle")
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.Palette.green)
                    .accessibilityIdentifier("login-status")
            }
            if let errorMessage {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .font(.byCaption.weight(.medium))
                    .foregroundStyle(BYTheme.Palette.red)
                    .accessibilityIdentifier("login-error")
            }
            Toggle(isOn: $rememberMe) {
                Text("זכור אותי במכשיר הזה")
                    .font(.byBody)
            }
            .tint(BYTheme.Palette.brand)
            .accessibilityIdentifier("remember-toggle")
            primaryButton
        }
        .padding(22)
        .background(BYTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .shadow(color: .black.opacity(0.25), radius: 30, y: 12)
    }

    private var userPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("מי מתחבר?")
                .font(.byCaption.weight(.semibold))
                .foregroundStyle(BYTheme.textSecondary)
            HStack(spacing: 10) {
                ForEach(users) { user in
                    Button {
                        selectedUserID = user.id
                        emailCodeSent = false
                        statusMessage = nil
                        errorMessage = nil
                        syncMethod()
                        Haptics.tap()
                    } label: {
                        Text(user.displayName)
                            .font(.byRowTitle)
                            .padding(.horizontal, 18)
                            .padding(.vertical, 9)
                            .background(selectedUserID == user.id ? BYTheme.Palette.brand : BYTheme.insetBackground)
                            .foregroundStyle(selectedUserID == user.id ? .white : BYTheme.textPrimary)
                            .clipShape(Capsule())
                    }
                    .accessibilityIdentifier("user-\(user.id)")
                }
            }
        }
    }

    private var availableMethods: [Method] {
        guard let user = selectedUser else { return [.totp, .email] }
        var methods: [Method] = []
        if user.methods.totp { methods.append(.totp) }
        if user.methods.email { methods.append(.email) }
        return methods.isEmpty ? [.totp, .email] : methods
    }

    private var methodPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("אופן התחברות")
                .font(.byCaption.weight(.semibold))
                .foregroundStyle(BYTheme.textSecondary)
            HStack(spacing: 10) {
                ForEach(availableMethods) { candidate in
                    Button {
                        method = candidate
                        code = ""
                        statusMessage = nil
                        errorMessage = nil
                        Haptics.tap()
                    } label: {
                        Label(candidate.title, systemImage: candidate.icon)
                            .font(.byCaption.weight(.semibold))
                            .padding(.horizontal, 13)
                            .padding(.vertical, 9)
                            .frame(maxWidth: .infinity)
                            .background(method == candidate ? BYTheme.Palette.brand.opacity(0.12) : BYTheme.insetBackground)
                            .foregroundStyle(method == candidate ? BYTheme.Palette.brand : BYTheme.textSecondary)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .strokeBorder(method == candidate ? BYTheme.Palette.brand : .clear, lineWidth: 1.5)
                            )
                    }
                    .accessibilityIdentifier("method-\(candidate.rawValue)")
                }
            }
        }
    }

    @ViewBuilder
    private var codeSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(method == .totp ? "קוד מאפליקציית האימות" : "קוד שנשלח למייל")
                .font(.byCaption.weight(.semibold))
                .foregroundStyle(BYTheme.textSecondary)
            TextField("6 ספרות", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .font(.byNumber(26, weight: .semibold))
                .multilineTextAlignment(.center)
                .padding(.vertical, 12)
                .background(BYTheme.insetBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .focused($codeFocused)
                .onChange(of: code) { _, newValue in
                    code = String(newValue.filter(\.isNumber).prefix(6))
                }
                .accessibilityIdentifier("code-field")
        }
    }

    private var primaryButton: some View {
        Group {
            if method == .email && !emailCodeSent {
                BYPrimaryButton(title: "שליחת קוד למייל", icon: "paperplane.fill", isLoading: isWorking) {
                    Task { await sendEmailCode() }
                }
                .accessibilityIdentifier("send-code-button")
            } else {
                BYPrimaryButton(title: "כניסה", icon: "arrow.left.circle.fill", isLoading: isWorking) {
                    Task { await submit() }
                }
                .accessibilityIdentifier("login-button")
            }
        }
    }

    private func syncMethod() {
        if !availableMethods.contains(method) {
            method = availableMethods.first ?? .totp
        }
    }

    private func sendEmailCode() async {
        guard let user = selectedUser else { return }
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            statusMessage = try await session.api.sendEmailCode(userID: user.id, rememberMe: rememberMe)
            emailCodeSent = true
            codeFocused = true
        } catch {
            errorMessage = (error as? APIError)?.message ?? "לא הצלחתי לשלוח קוד. נסה שוב."
        }
    }

    private func submit() async {
        guard let user = selectedUser else { return }
        guard code.count == 6 else {
            errorMessage = "יש להזין קוד בן 6 ספרות."
            Haptics.error()
            return
        }
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            switch method {
            case .totp:
                try await session.api.verifyTOTP(userID: user.id, code: code, rememberMe: rememberMe)
            case .email:
                try await session.api.verifyEmailCode(code: code)
            }
            session.didAuthenticate(userName: user.displayName)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "ההתחברות נכשלה. נסה שוב."
            Haptics.error()
        }
    }
}
