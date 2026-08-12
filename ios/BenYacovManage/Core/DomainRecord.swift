import Foundation

/// שורת נתונים גנרית מאחד הדומיינים של השרת.
struct DomainRecord: Identifiable, Equatable, Sendable {
    let fields: [String: JSONValue]
    /// מזהה יציב — נגזר משדות מזהים מוכרים, ואם אין כאלה מתוכן השורה.
    let id: String

    init(fields: [String: JSONValue]) {
        self.fields = fields
        let idKeys = ["row_id", "history_id", "reminder_id", "employee_id", "customer_guid",
                      "customer_key", "fulfillment_id", "record_id", "installation_id", "visit_id",
                      "id", "quote_number", "po_number"]
        if let key = idKeys.first(where: { !(fields[$0]?.isEmptyDisplay ?? true) }),
           let value = fields[key] {
            self.id = "\(key):\(value.displayText)"
        } else if let sheetRow = fields["_sheet_row"], !sheetRow.isEmptyDisplay {
            // שורות גיליון (תשלומים והעברות) — זהות יציבה גם כשהתוכן משתנה.
            let sheet = fields["_sheet_title"]?.displayText ?? ""
            self.id = "sheet:\(sheet):\(sheetRow.displayText)"
        } else {
            let digest = fields
                .map { "\($0.key)=\($0.value.displayText)" }
                .sorted()
                .joined(separator: "|")
            self.id = "hash:\(digest.hashValue)"
        }
    }

    subscript(key: String) -> String {
        fields[key]?.displayText.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    /// הערך הראשון שאינו ריק מבין רשימת מפתחות.
    func first(of keys: [String]) -> String {
        for key in keys {
            let value = self[key]
            if !value.isEmpty { return value }
        }
        return ""
    }

    func number(_ key: String) -> Double? {
        guard let value = fields[key] else { return nil }
        switch value {
        case .number(let number): return number
        case .string(let text):
            let cleaned = text.replacingOccurrences(of: "₪", with: "")
                .replacingOccurrences(of: ",", with: "")
                .trimmingCharacters(in: .whitespaces)
            return Double(cleaned)
        default: return nil
        }
    }

    func bool(_ key: String) -> Bool {
        guard let value = fields[key] else { return false }
        switch value {
        case .bool(let flag): return flag
        case .string(let text):
            return ["true", "yes", "כן", "1", "paid", "active"].contains(text.trimmingCharacters(in: .whitespaces).lowercased())
        case .number(let number): return number != 0
        default: return false
        }
    }

    var jsonObject: [String: Any] {
        func unwrap(_ value: JSONValue) -> Any {
            switch value {
            case .string(let text): return text
            case .number(let number): return number
            case .bool(let flag): return flag
            case .null: return NSNull()
            case .array(let items): return items.map(unwrap)
            case .object(let object): return object.mapValues(unwrap)
            }
        }
        return fields.mapValues(unwrap)
    }
}

extension DomainRecord {
    static func records(fromRowsJSON data: Data) throws -> [DomainRecord] {
        let decoded = try JSONDecoder().decode([String: JSONValue].self, from: data)
        guard case .array(let rows)? = decoded["rows"] else { return [] }
        return rows.compactMap { value in
            if case .object(let fields) = value { return DomainRecord(fields: fields) }
            return nil
        }
    }
}
