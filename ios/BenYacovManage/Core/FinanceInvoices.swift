import Foundation

/// מיון וסינון חשבוניות ספקים — שיקוף מיון הטבלה וכפתורי הדיווח (מועדי מע"מ) בדסקטופ.
enum FinanceInvoices {
    /// אפשרויות המיון ברשימה. ברירת המחדל כמו בדסקטופ: תאריך חשבונית, מהחדש לישן.
    enum Sort: String, CaseIterable, Identifiable {
        case dateDesc
        case amountDesc
        case amountAsc
        case supplierAlphabetical

        var id: String { rawValue }

        var title: String {
            switch self {
            case .dateDesc: return "תאריך — מהחדש לישן"
            case .amountDesc: return "סכום — מהגבוה לנמוך"
            case .amountAsc: return "סכום — מהנמוך לגבוה"
            case .supplierAlphabetical: return "ספק — לפי א׳-ב׳ / ABC"
            }
        }

        var icon: String {
            switch self {
            case .dateDesc: return "calendar"
            case .amountDesc: return "arrow.down.right.circle"
            case .amountAsc: return "arrow.up.right.circle"
            case .supplierAlphabetical: return "textformat.abc"
            }
        }
    }

    /// ממיר תאריך מהשרת (31/12/2025 או 2026-06-03T09:14:16) למפתח מיון לקסיקוגרפי.
    static func dateSortKey(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        let parts = trimmed.split(separator: "/")
        guard parts.count == 3 else { return trimmed } // ISO כבר ממוין כמחרוזת
        let day = String(parts[0]), month = String(parts[1]), year = String(parts[2])
        func pad(_ value: String, to width: Int) -> String {
            String(repeating: "0", count: max(0, width - value.count)) + value
        }
        return "\(pad(year, to: 4))-\(pad(month, to: 2))-\(pad(day, to: 2))"
    }

    static func amount(_ record: DomainRecord) -> Double {
        record.number("total") ?? 0
    }

    static func sorted(_ rows: [DomainRecord], by sort: Sort) -> [DomainRecord] {
        switch sort {
        case .dateDesc:
            return rows.sorted { dateSortKey($0["invoice_date"]) > dateSortKey($1["invoice_date"]) }
        case .amountDesc:
            return rows.sorted { amount($0) > amount($1) }
        case .amountAsc:
            return rows.sorted { amount($0) < amount($1) }
        case .supplierAlphabetical:
            // מיון עברי — מסדר נכון גם א׳-ב׳ וגם ABC (לטינית אחרי עברית).
            return rows.sorted {
                $0["supplier_name"].compare($1["supplier_name"], options: [.caseInsensitive],
                                            range: nil, locale: Formatters.hebrewLocale) == .orderedAscending
            }
        }
    }

    /// כל מועדי הדיווח של שורה — report_due_date + report_due_overrides,
    /// כמו financeInvoiceAllDueDates בדסקטופ.
    static func dueDates(of record: DomainRecord) -> [String] {
        var values = [record["report_due_date"]]
        values += record["report_due_overrides"].split(separator: ",").map {
            $0.trimmingCharacters(in: .whitespaces)
        }
        var seen = Set<String>()
        return values.filter { !$0.isEmpty && seen.insert($0).inserted }
    }

    static func matches(_ record: DomainRecord, dueDate: String) -> Bool {
        dueDates(of: record).contains(dueDate)
    }

    /// מועדי הדיווח הזמינים בשורות הטעונות — מהחדש לישן, כמו כפתורי הדסקטופ.
    static func availableDueDates(_ rows: [DomainRecord]) -> [String] {
        var seen = Set<String>()
        return rows.flatMap { dueDates(of: $0) }
            .filter { seen.insert($0).inserted }
            .sorted { dateSortKey($0) > dateSortKey($1) }
    }

    /// תווית קצרה לצ'יפ דיווח — "15.7.26" כמו "חשבוניות 15.7.26" בדסקטופ.
    static func chipLabel(_ dueDate: String) -> String {
        let parts = dueDate.split(separator: "/")
        guard parts.count == 3 else { return dueDate }
        let day = Int(parts[0]).map(String.init) ?? String(parts[0])
        let month = Int(parts[1]).map(String.init) ?? String(parts[1])
        return "\(day).\(month).\(parts[2].suffix(2))"
    }
}
