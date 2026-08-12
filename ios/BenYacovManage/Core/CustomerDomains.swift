import Foundation

/// סוגי הלקוחות (תחומים) — שיקוף מדויק של customerDomainValue/Label בדסקטופ.
enum CustomerDomains {
    struct Option: Identifiable, Equatable {
        let value: String      // הערך בשדה customer_domain ("" = ללא שיוך)
        let label: String      // הנוסח המלא של הדסקטופ
        let short: String      // תווית קצרה לצ'יפ
        var id: String { value }
    }

    static let options: [Option] = [
        Option(value: "construction", label: "תחום הבנייה", short: "בנייה"),
        Option(value: "textile", label: "עיבוד טכני בטקסטיל", short: "טקסטיל"),
        Option(value: "supplier", label: "ספק", short: "ספק"),
        Option(value: "graphic_web", label: "עיצוב גרפי ואינטרנט", short: "גרפיקה"),
        Option(value: "", label: "ללא שיוך", short: "ללא שיוך"),
    ]

    /// נרמול כמו בדסקטופ: ערך לא מוכר ⇒ "" (ללא שיוך).
    static func normalized(_ raw: String) -> String {
        let value = raw.trimmingCharacters(in: .whitespaces).lowercased()
        return ["construction", "textile", "supplier", "graphic_web"].contains(value) ? value : ""
    }

    static func label(for raw: String) -> String {
        options.first { $0.value == normalized(raw) }?.label ?? "ללא שיוך"
    }

    /// מיון הלקוחות של הדסקטופ: אלפביתי עברי לפי שם.
    static func sorted(_ rows: [DomainRecord]) -> [DomainRecord] {
        rows.sorted {
            $0["customer_name"].compare($1["customer_name"], options: [], range: nil,
                                        locale: Locale(identifier: "he_IL")) == .orderedAscending
        }
    }
}
