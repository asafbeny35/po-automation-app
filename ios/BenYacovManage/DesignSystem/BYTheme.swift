import SwiftUI

/// מערכת העיצוב של האפליקציה — צבעים, מרווחים ורדיוסים.
/// כל הצבעים אדפטיביים למצב כהה.
enum BYTheme {
    enum Palette {
        /// כחול-נייבי עמוק — צבע המותג הראשי.
        static let brand = Color(light: "12315B", dark: "9DBCF0")
        /// ענבר חם — צבע המשנה (עולם הבנייה).
        static let accent = Color(light: "C97B22", dark: "F0B35C")

        static let blue = Color(light: "2563EB", dark: "7CA8FF")
        static let teal = Color(light: "0D9488", dark: "5EEAD4")
        static let amber = Color(light: "B45309", dark: "FBBF24")
        static let purple = Color(light: "7C3AED", dark: "C4B5FD")
        static let green = Color(light: "15803D", dark: "6EE7A0")
        static let red = Color(light: "DC2626", dark: "FCA5A5")
        static let indigo = Color(light: "4338CA", dark: "A5B4FC")
        static let brown = Color(light: "92400E", dark: "D6A05C")
        static let pink = Color(light: "DB2777", dark: "F9A8D4")
        static let gray = Color(light: "52525B", dark: "A1A1AA")
    }

    /// רקע המסך — אפור חמים בהיר / כהה אמיתי.
    static let screenBackground = Color(light: "F4F4F6", dark: "0C0C0F")
    /// רקע כרטיס.
    static let cardBackground = Color(light: "FFFFFF", dark: "1A1A20")
    /// רקע כרטיס משני (בתוך כרטיס).
    static let insetBackground = Color(light: "F7F7F9", dark: "24242C")
    static let separator = Color(light: "E7E7EC", dark: "2E2E38")

    static let textPrimary = Color(light: "17171C", dark: "F2F2F7")
    static let textSecondary = Color(light: "6E6E78", dark: "9C9CA8")

    static let cardRadius: CGFloat = 18
    static let chipRadius: CGFloat = 9

    /// גרדיאנט הכותרת של מסך הבית.
    static var heroGradient: LinearGradient {
        LinearGradient(
            colors: [Color(light: "12315B", dark: "16233C"), Color(light: "1D4E89", dark: "1E3356")],
            startPoint: .topTrailing,
            endPoint: .bottomLeading
        )
    }
}

extension Color {
    /// יוצר צבע אדפטיבי משני קודים הקסדצימליים (בהיר/כהה).
    init(light: String, dark: String) {
        self.init(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light)
        })
    }
}

extension UIColor {
    convenience init(hex: String) {
        var value: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&value)
        self.init(
            red: CGFloat((value >> 16) & 0xFF) / 255,
            green: CGFloat((value >> 8) & 0xFF) / 255,
            blue: CGFloat(value & 0xFF) / 255,
            alpha: 1
        )
    }
}

// MARK: - טיפוגרפיה

extension Font {
    /// מספרים בולטים (KPI) — עיצוב מעוגל.
    static func byNumber(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .rounded)
    }

    static let byLargeTitle = Font.system(size: 30, weight: .heavy)
    static let byTitle = Font.system(size: 21, weight: .bold)
    static let bySection = Font.system(size: 16, weight: .bold)
    static let byRowTitle = Font.system(size: 16, weight: .semibold)
    static let byBody = Font.system(size: 15, weight: .regular)
    static let byCaption = Font.system(size: 13, weight: .regular)
    static let byBadge = Font.system(size: 11, weight: .bold)
}
