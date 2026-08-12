import Foundation

/// ערך JSON גנרי — שורות הדאטה מהשרת מגיעות כמילונים חופשיים,
/// לכן המודל חייב לעכל כל צורה בלי להישבר.
enum JSONValue: Codable, Equatable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "ערך JSON לא מזוהה")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    /// ייצוג טקסטואלי נוח לתצוגה.
    var displayText: String {
        switch self {
        case .string(let value): return value
        case .number(let value):
            if value.rounded() == value && abs(value) < 1e12 {
                return String(Int(value))
            }
            return String(value)
        case .bool(let value): return value ? "כן" : "לא"
        case .null: return ""
        case .array(let items): return items.map(\.displayText).joined(separator: ", ")
        case .object: return "…"
        }
    }

    var isEmptyDisplay: Bool {
        displayText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
