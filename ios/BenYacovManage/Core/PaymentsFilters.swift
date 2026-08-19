import Foundation

/// סינון שורות תשלומים לפי אות ראשונה וטווח תאריכים — אותם כללים כמו בדסקטופ.
enum PaymentsFilters {
    /// האות שלפיה השורה מסווגת: התו הראשון של שם הלקוח, בלי גרשיים/פיסוק מוביל.
    static func letter(of row: DomainRecord) -> String {
        let trimmed = row["customer_name"].trimmingCharacters(in: .whitespaces)
        let cleaned = trimmed.drop { "\"'״׳ -–—._,".contains($0) }
        guard let first = cleaned.first else { return "" }
        return String(first).uppercased()
    }

    static func availableLetters(_ rows: [DomainRecord]) -> [String] {
        Array(Set(rows.map(letter).filter { !$0.isEmpty }))
            .sorted { $0.localizedCompare($1) == .orderedAscending }
    }

    /// הגבולות נבדקים ביום מקומי מלא — "עד" כולל את היום עצמו.
    static func inRange(_ row: DomainRecord, field: String, from: Date?, to: Date?) -> Bool {
        guard from != nil || to != nil else { return true }
        guard let value = PaymentsMath.parseSheetDate(row[field]) else { return false }
        let calendar = Calendar.current
        if let from, value < calendar.startOfDay(for: from) { return false }
        if let to {
            guard let end = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: to)) else { return true }
            if value >= end { return false }
        }
        return true
    }
}
