import Foundation

/// חישובי "לגבייה" ו"לתשלום" — שיקוף מדויק של הלוגיקה בשרת
/// (`_build_payment_transfer_state` ב-services/google_sheets.py):
/// רק גיליונות 2025/2026, חשבוניות מ-2025 ואילך, שורות ששולמו נכללות רק אם
/// תאריך החשבונית/יעד ב-2026, וכל שורה שאינה "תשלום" נחשבת גבייה.
enum PaymentsMath {
    /// תחילת עונת התשלומים הנוכחית — זהה לשרת.
    static let seasonStart = DateComponents(calendar: .init(identifier: .gregorian), year: 2026, month: 1, day: 1).date!
    /// תאריך חשבונית מינימלי — זהה לשרת.
    static let minimumInvoiceDate = DateComponents(calendar: .init(identifier: .gregorian), year: 2025, month: 1, day: 1).date!
    static let allowedSheetYears: Set<Int> = [2025, 2026]

    static func sheetYear(_ sheetTitle: String) -> Int? {
        guard let range = sheetTitle.range(of: #"20\d\d"#, options: .regularExpression) else { return nil }
        return Int(sheetTitle[range])
    }

    /// dd/MM/yyyy — הפורמט של גיליון התשלומים.
    static func parseSheetDate(_ raw: String) -> Date? {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "dd/MM/yyyy"
        return formatter.date(from: trimmed)
    }

    /// מסווג את השורות לגבייה/תשלום עם אותם סינונים כמו בדסקטופ.
    static func categorize(_ rows: [DomainRecord], today: Date = .now) -> (collection: [DomainRecord], payment: [DomainRecord]) {
        var collection: [DomainRecord] = []
        var payment: [DomainRecord] = []

        for row in rows {
            guard let year = sheetYear(row["_sheet_title"]), allowedSheetYears.contains(year) else {
                continue
            }
            let invoiceDate = parseSheetDate(row["invoice_date"])
            let dueDate = parseSheetDate(row["due_date"])
            if let invoiceDate, invoiceDate < minimumInvoiceDate {
                continue
            }

            let paid = row.bool("paid")
            let inSeason = (invoiceDate.map { $0 >= seasonStart } ?? false)
                || (dueDate.map { $0 >= seasonStart } ?? false)
            // שורה נכללת אם היא בעונה הנוכחית, או שהיא עדיין לא שולמה.
            guard inSeason || !paid else { continue }

            if row["payment_direction"] == "תשלום" {
                payment.append(row)
            } else {
                collection.append(row)
            }
        }
        return (collection, payment)
    }

    /// סטטוס שורה — כמו כפתורי הסינון בדסקטופ:
    /// paid = ירוק (התקבל/שולם), open = לבן (בתוקף), overdue = אדום (המועד חלף).
    enum RowStatus {
        case paid
        case open
        case overdue
    }

    static func status(of row: DomainRecord, today: Date = .now) -> RowStatus {
        if row.bool("paid") { return .paid }
        let dayStart = Calendar.current.startOfDay(for: today)
        if let due = parseSheetDate(row["due_date"]), due < dayStart { return .overdue }
        return .open
    }

    /// סכום השורות הפתוחות (שטרם שולמו) — כולל שורות שמועדן חלף.
    /// זה המספר שמוצג בריבועי הבית: כל מה שעדיין לא נגבה/שולם בפועל.
    static func openTotal(_ rows: [DomainRecord]) -> Double {
        rows.filter { !$0.bool("paid") }
            .compactMap { $0.number("amount") }
            .reduce(0, +)
    }

    /// החלק מתוך הסכום הפתוח שמועד היעד שלו כבר עבר ("מועד הגבייה חלף").
    static func overdueTotal(_ rows: [DomainRecord], today: Date = .now) -> Double {
        let dayStart = Calendar.current.startOfDay(for: today)
        return rows
            .filter { row in
                guard !row.bool("paid"), let due = parseSheetDate(row["due_date"]) else { return false }
                return due < dayStart
            }
            .compactMap { $0.number("amount") }
            .reduce(0, +)
    }
}
