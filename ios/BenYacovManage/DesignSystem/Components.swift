import SwiftUI

// MARK: - כרטיס

/// כרטיס סטנדרטי — הרכיב הבסיסי של כל המסכים.
struct BYCard<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder let content: Content

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(padding)
            .background(BYTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: BYTheme.cardRadius, style: .continuous))
            .shadow(color: .black.opacity(0.06), radius: 10, y: 4)
    }
}

// MARK: - תג סטטוס

struct StatusBadge: View {
    let text: String
    var tint: Color = BYTheme.Palette.gray

    /// תרגום ערכי סטטוס נפוצים מהשרת לעברית וצבע.
    static func styled(_ raw: String) -> (text: String, tint: Color)? {
        let value = raw.trimmingCharacters(in: .whitespaces)
        guard !value.isEmpty else { return nil }
        switch value.lowercased() {
        case "true", "yes", "כן", "paid", "שולם":
            return ("✓ כן", BYTheme.Palette.green)
        case "false", "no", "לא":
            return ("לא", BYTheme.Palette.gray)
        case "prod", "production":
            return ("פרודקשן", BYTheme.Palette.green)
        case "sandbox", "test":
            return ("בדיקה", BYTheme.Palette.amber)
        case "sb":
            return ("סנדבוקס", BYTheme.Palette.amber)
        case "active", "פעיל":
            return ("פעיל", BYTheme.Palette.green)
        case "inactive", "לא פעיל":
            return ("לא פעיל", BYTheme.Palette.gray)
        case "open", "פתוח":
            return ("פתוח", BYTheme.Palette.blue)
        case "completed", "done", "הושלם":
            return ("הושלם", BYTheme.Palette.green)
        case "pending", "ממתין":
            return ("ממתין", BYTheme.Palette.amber)
        case "email":
            return ("מייל", BYTheme.Palette.blue)
        case "whatsapp":
            return ("וואטסאפ", BYTheme.Palette.green)
        case "תשלום":
            return ("תשלום", BYTheme.Palette.red)
        case "גבייה", "הכנסה":
            return ("גבייה", BYTheme.Palette.green)
        case "ידני":
            return ("ידני", BYTheme.Palette.purple)
        case "construction":
            return ("בנייה", BYTheme.Palette.brown)
        case "textile":
            return ("טקסטיל", BYTheme.Palette.teal)
        case "supplier":
            return ("ספק", BYTheme.Palette.indigo)
        case "graphic_web":
            return ("עיצוב ואינטרנט", BYTheme.Palette.purple)
        default:
            return (value, BYTheme.Palette.blue)
        }
    }

    var body: some View {
        Text(text)
            .font(.byBadge)
            .foregroundStyle(tint)
            .padding(.horizontal, 8)
            .padding(.vertical, 3.5)
            .background(tint.opacity(0.13))
            .clipShape(RoundedRectangle(cornerRadius: BYTheme.chipRadius, style: .continuous))
    }
}

// MARK: - כותרת מקטע

struct SectionHeader: View {
    let title: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.bySection)
                .foregroundStyle(BYTheme.textPrimary)
            if let subtitle {
                Text(subtitle)
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.textSecondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 4)
    }
}

// MARK: - מצבים ריקים ושגיאות

struct EmptyStateView: View {
    var icon: String = "tray"
    var title: String = "אין נתונים להצגה"
    var subtitle: String? = nil

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(BYTheme.textSecondary)
            Text(title)
                .font(.byRowTitle)
                .foregroundStyle(BYTheme.textPrimary)
            if let subtitle {
                Text(subtitle)
                    .font(.byCaption)
                    .foregroundStyle(BYTheme.textSecondary)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 48)
        .accessibilityIdentifier("empty-state")
    }
}

struct ErrorStateView: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(BYTheme.Palette.red)
                .accessibilityIdentifier("error-state")
            Text(message)
                .font(.byBody)
                .foregroundStyle(BYTheme.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
            Button(action: retry) {
                Label("נסה שוב", systemImage: "arrow.clockwise")
                    .font(.byRowTitle)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(BYTheme.Palette.brand)
                    .foregroundStyle(.white)
                    .clipShape(Capsule())
                    .accessibilityIdentifier("retry-button")
            }
            .accessibilityIdentifier("retry-button")
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 48)
    }
}

// MARK: - שלד טעינה

struct ShimmerList: View {
    var rows: Int = 6
    @State private var pulse = false

    var body: some View {
        VStack(spacing: 10) {
            ForEach(0..<rows, id: \.self) { _ in
                BYCard {
                    VStack(alignment: .leading, spacing: 8) {
                        RoundedRectangle(cornerRadius: 5)
                            .fill(BYTheme.insetBackground)
                            .frame(width: 170, height: 14)
                        RoundedRectangle(cornerRadius: 5)
                            .fill(BYTheme.insetBackground)
                            .frame(width: 110, height: 11)
                    }
                }
            }
        }
        .opacity(pulse ? 0.55 : 1)
        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulse)
        .onAppear { pulse = true }
        // השלד הוא אלמנט נגישות אחד — גם VoiceOver נקי וגם מזהה יציב לטסטים.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("טוען נתונים")
        .accessibilityIdentifier("loading-shimmer")
    }
}

// MARK: - טוסט

struct ToastView: View {
    let message: SessionStore.ToastMessage

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: message.style == .success ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(message.style == .success ? BYTheme.Palette.green : BYTheme.Palette.red)
            Text(message.text)
                .font(.byBody.weight(.medium))
                .foregroundStyle(BYTheme.textPrimary)
                .lineLimit(2)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.regularMaterial)
        .clipShape(Capsule())
        .shadow(color: .black.opacity(0.15), radius: 14, y: 6)
        .accessibilityIdentifier("toast")
    }
}

/// מודיפייר שמציג טוסט גלובלי מעל התוכן ונעלם אחרי כמה שניות.
struct ToastPresenter: ViewModifier {
    @Environment(SessionStore.self) private var session

    func body(content: Content) -> some View {
        content.overlay(alignment: .bottom) {
            if let toast = session.toast {
                ToastView(message: toast)
                    .padding(.bottom, 70)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task(id: toast.id) {
                        try? await Task.sleep(nanoseconds: 2_800_000_000)
                        if session.toast?.id == toast.id {
                            withAnimation { session.toast = nil }
                        }
                    }
            }
        }
        .animation(.spring(duration: 0.35), value: session.toast)
    }
}

// MARK: - שורת פרט במסך פירוט

struct DetailFieldRow: View {
    let label: String
    let value: String
    var isLink: Bool = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(label)
                .font(.byCaption.weight(.medium))
                .foregroundStyle(BYTheme.textSecondary)
                .frame(width: 108, alignment: .leading)
            if isLink, let url = URL(string: value) {
                Link(destination: url) {
                    Text("פתיחת קישור")
                        .font(.byBody.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.blue)
                }
            } else {
                Text(value)
                    .font(.byBody)
                    .foregroundStyle(BYTheme.textPrimary)
                    .multilineTextAlignment(.leading)
                    .textSelection(.enabled)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 7)
    }
}

// MARK: - כפתור פעולה ראשי

struct BYPrimaryButton: View {
    let title: String
    var icon: String? = nil
    var isLoading: Bool = false
    var tint: Color = BYTheme.Palette.brand
    let action: () -> Void

    var body: some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            HStack(spacing: 8) {
                if isLoading {
                    ProgressView().tint(.white)
                } else if let icon {
                    Image(systemName: icon)
                }
                Text(title)
            }
            .font(.byRowTitle)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(tint)
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .disabled(isLoading)
    }
}
