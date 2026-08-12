import SwiftUI

/// התחברות — אותם מנגנונים כמו האפליקציה הראשית: TOTP או קוד למייל.
struct ClassicLoginView: View {
    @EnvironmentObject private var session: ClassicSession

    @State private var selectedUserID = ""
    @State private var method = "totp"
    @State private var code = ""
    @State private var emailSent = false
    @State private var isWorking = false
    @State private var errorMessage: String?

    private var users: [AuthBootstrap.User] { session.authBootstrap?.authUsers ?? [] }
    private var selectedUser: AuthBootstrap.User? { users.first { $0.id == selectedUserID } }

    var body: some View {
        ZStack {
            ClassicTheme.hero.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 18) {
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 44, weight: .light))
                        .foregroundColor(.white)
                    Text("בן יעקב — קלאסי")
                        .font(.largeTitle.bold())
                        .foregroundColor(.white)
                        .accessibilityIdentifier("classic-login")

                    VStack(spacing: 10) {
                        ForEach(users) { user in
                            Button {
                                selectedUserID = user.id
                                emailSent = false
                            } label: {
                                HStack {
                                    Text(user.displayName)
                                        .font(.headline)
                                    Spacer()
                                    if selectedUserID == user.id {
                                        Image(systemName: "checkmark.circle.fill")
                                    }
                                }
                                .padding(14)
                                .background(Color.white.opacity(selectedUserID == user.id ? 0.28 : 0.12),
                                            in: RoundedRectangle(cornerRadius: 14))
                                .foregroundColor(.white)
                            }
                            .accessibilityIdentifier("classic-user-\(user.id)")
                            .accessibilityAddTraits(selectedUserID == user.id ? .isSelected : [])
                        }
                    }

                    if let user = selectedUser {
                        Picker("שיטה", selection: $method) {
                            if user.methods.totp { Text("אפליקציית אימות").tag("totp") }
                            if user.methods.email { Text("קוד למייל").tag("email") }
                        }
                        .pickerStyle(.segmented)
                        .accessibilityIdentifier("classic-method")

                        if method == "email", !emailSent {
                            actionButton("שליחת קוד למייל", id: "classic-send-code") {
                                await sendCode()
                            }
                        } else {
                            TextField("קוד אימות", text: $code)
                                .keyboardType(.numberPad)
                                .multilineTextAlignment(.center)
                                .font(.title2.monospacedDigit())
                                // הרקע לבן קבוע — מקבעים גם את צבע הטקסט, אחרת
                                // במצב כהה הטקסט לבן ובלתי נראה.
                                .foregroundColor(.black)
                                .tint(ClassicTheme.brand)
                                .padding(12)
                                .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                                .accessibilityIdentifier("classic-code")
                            actionButton("כניסה", id: "classic-submit") {
                                await submit()
                            }
                        }
                    }

                    if let errorMessage {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .font(.subheadline.weight(.semibold))
                            .foregroundColor(.yellow)
                            .accessibilityIdentifier("classic-login-error")
                    }
                }
                .padding(24)
                .frame(maxWidth: 480)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            if session.authBootstrap == nil { await session.start() }
            if selectedUserID.isEmpty {
                // דיפולט: המשתמש האחרון שהתחבר במכשיר הזה, אחר כך הזכור בשרת, אחר כך הראשון.
                let remembered = session.lastLoggedInUserID ?? session.authBootstrap?.selectedUserID ?? ""
                selectedUserID = users.first { $0.id == remembered }?.id ?? users.first?.id ?? ""
            }
        }
    }

    private func actionButton(_ title: String, id: String, action: @escaping () async -> Void) -> some View {
        Button {
            Task { await action() }
        } label: {
            HStack {
                if isWorking { ProgressView().tint(ClassicTheme.brand) }
                Text(title).font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 14))
            .foregroundColor(ClassicTheme.brand)
        }
        .disabled(isWorking)
        .accessibilityIdentifier(id)
    }

    private func sendCode() async {
        isWorking = true
        defer { isWorking = false }
        do {
            _ = try await session.api.sendEmailCode(userID: selectedUserID, rememberMe: true)
            emailSent = true
            errorMessage = nil
        } catch {
            errorMessage = (error as? APIError)?.message ?? "שליחת הקוד נכשלה."
        }
    }

    private func submit() async {
        isWorking = true
        defer { isWorking = false }
        do {
            if method == "totp" {
                try await session.api.verifyTOTP(userID: selectedUserID, code: code, rememberMe: true)
            } else {
                try await session.api.verifyEmailCode(code: code)
            }
            errorMessage = nil
            session.didAuthenticate(userName: selectedUser?.displayName ?? "", userID: selectedUserID)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "הקוד לא התקבל — נסה שוב."
        }
    }
}
