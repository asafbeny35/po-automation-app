import Foundation

/// עיצוב ערכים לתצוגה — סכומים, תאריכים וטלפונים בפורמט ישראלי.
enum Formatters {
    static let hebrewLocale = Locale(identifier: "he_IL")

    private static let currency: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "ILS"
        formatter.currencySymbol = "₪"
        formatter.maximumFractionDigits = 0
        formatter.locale = hebrewLocale
        return formatter
    }()

    private static let currencyDetailed: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "ILS"
        formatter.currencySymbol = "₪"
        formatter.minimumFractionDigits = 2
        formatter.maximumFractionDigits = 2
        formatter.locale = hebrewLocale
        return formatter
    }()

    /// ממיר טקסט סכום גולמי (למשל "₪7,009.00" או "3192.22") לתצוגה אחידה.
    static func currencyText(_ raw: String, detailed: Bool = false) -> String {
        let cleaned = raw.replacingOccurrences(of: "₪", with: "")
            .replacingOccurrences(of: ",", with: "")
            .trimmingCharacters(in: .whitespaces)
        guard let value = Double(cleaned) else { return raw }
        let formatter = detailed ? currencyDetailed : currency
        return formatter.string(from: NSNumber(value: value)) ?? raw
    }

    static func currencyValue(_ value: Double, detailed: Bool = false) -> String {
        let formatter = detailed ? currencyDetailed : currency
        return formatter.string(from: NSNumber(value: value)) ?? String(value)
    }

    /// מזהה פורמטים נפוצים של תאריך מהשרת ומחזיר תצוגה עברית קצרה.
    static func dateText(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return "" }

        // ISO עם או בלי שעה: 2026-07-02T16:15:35 / 2026-07-02
        let isoFormats = ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd"]
        for format in isoFormats {
            if let date = parse(trimmed, format: format) {
                return display(date, withTime: format.contains("HH"))
            }
        }
        // פורמט ישראלי: 27/05/2026
        if let date = parse(trimmed, format: "dd/MM/yyyy") {
            return display(date, withTime: false)
        }
        // Epoch (למשל creation_date מחשבונית ירוקה)
        if let epoch = Double(trimmed), epoch > 1_000_000_000, epoch < 10_000_000_000 {
            return display(Date(timeIntervalSince1970: epoch), withTime: false)
        }
        // חודש בפורמט 2026-06
        if trimmed.count == 7, trimmed.contains("-"), let date = parse(trimmed + "-01", format: "yyyy-MM-dd") {
            let formatter = DateFormatter()
            formatter.locale = hebrewLocale
            formatter.dateFormat = "MMMM yyyy"
            return formatter.string(from: date)
        }
        return trimmed
    }

    private static func parse(_ text: String, format: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = format
        return formatter.date(from: text)
    }

    private static func display(_ date: Date, withTime: Bool) -> String {
        let formatter = DateFormatter()
        formatter.locale = hebrewLocale
        formatter.dateFormat = withTime ? "d.M.yyyy · HH:mm" : "d.M.yyyy"
        return formatter.string(from: date)
    }

    /// מנרמל טלפון ישראלי לחיוג/וואטסאפ.
    static func normalizedPhone(_ raw: String) -> String {
        var digits = raw.filter { $0.isNumber || $0 == "+" }
        if digits.hasPrefix("+") { return digits }
        if digits.hasPrefix("0") { digits = "+972" + digits.dropFirst() }
        return digits
    }

    static func whatsappURL(phone: String, message: String = "") -> URL? {
        let normalized = normalizedPhone(phone).replacingOccurrences(of: "+", with: "")
        guard !normalized.isEmpty else { return nil }
        var components = URLComponents(string: "https://wa.me/\(normalized)")
        if !message.isEmpty {
            components?.queryItems = [URLQueryItem(name: "text", value: message)]
        }
        return components?.url
    }

    static func callURL(phone: String) -> URL? {
        let normalized = normalizedPhone(phone)
        guard !normalized.isEmpty else { return nil }
        return URL(string: "tel://\(normalized)")
    }

    static func mailURL(_ email: String) -> URL? {
        let first = email.split(whereSeparator: { $0 == "," || $0 == ";" || $0 == " " }).first.map(String.init) ?? ""
        guard first.contains("@") else { return nil }
        return URL(string: "mailto:\(first)")
    }
}
