import Foundation

/// שורת פריט בקומפוזר — אותו מבנה שהדסקטופ שולח ב-`items`/`ordered_items`.
struct ComposerItem: Identifiable, Equatable {
    let id = UUID()
    var sku: String = ""
    var description: String = ""
    var quantity: String = "1"
    var unit: String = ComposerMath.units[0]
    var unitPrice: String = ""

    var quantityValue: Double { ComposerMath.number(quantity) }
    var unitPriceValue: Double { ComposerMath.number(unitPrice) }
    var lineTotal: Double { (quantityValue * unitPriceValue).rounded(toPlaces: 2) }

    /// שורה נחשבת מלאה רק אם יש תיאור וכמות — בדיוק כמו `collectManualItemsFromForm` בדסקטופ.
    var isComplete: Bool {
        !description.trimmingCharacters(in: .whitespaces).isEmpty && quantityValue > 0
    }

    var payload: [String: Any] {
        [
            "description": description.trimmingCharacters(in: .whitespaces),
            "sku": sku.trimmingCharacters(in: .whitespaces),
            "unit": unit,
            "quantity": quantityValue,
            "unit_price": unitPriceValue,
            "line_total": lineTotal,
        ]
    }
}

/// חישובי הכסף של הקומפוזרים, במקום אחד כדי שהאפליקציה והדסקטופ לא יתפצלו.
enum ComposerMath {
    /// שיעור המע״מ — זהה ל-`recalculateManualFinancials` בדסקטופ (0.18).
    /// היה כאן 0.17 והצעות שנוצרו מהאייפון יצאו עם מע״מ וסה״כ נמוכים מהאמת.
    static let vatRate = 0.18

    /// אותן יחידות שמופיעות בסלקט "יחידה" בדסקטופ.
    static let units = ["ללא", "יחידה", "פלטות", "גלילים", "מטר רץ", "מטר מרובע"]

    /// אפשרויות "שוטף +" של הדסקטופ: התווית שמוצגת והימים שנשלחים.
    static let paymentTerms: [(label: String, days: String)] = [
        ("מיידי", "ddp"),
        ("שוטף", "0"),
        ("שוטף + 30", "30"),
        ("שוטף + 60", "60"),
        ("שוטף + 75", "75"),
        ("שוטף + 90", "90"),
        ("שוטף + 120", "120"),
    ]

    /// קידומות הטלפון של הדסקטופ.
    static let phonePrefixes = ["050", "051", "052", "053", "054", "055", "058", "02", "03", "04", "08", "09", "073", "077"]

    static func number(_ raw: String) -> Double {
        let cleaned = raw.replacingOccurrences(of: ",", with: "")
            .replacingOccurrences(of: "₪", with: "")
            .trimmingCharacters(in: .whitespaces)
        return Double(cleaned) ?? 0
    }

    static func subtotal(of items: [ComposerItem]) -> Double {
        items.filter(\.isComplete).reduce(0) { $0 + $1.lineTotal }.rounded(toPlaces: 2)
    }

    static func vat(_ subtotal: Double) -> Double {
        subtotal > 0 ? (subtotal * vatRate).rounded(toPlaces: 2) : 0
    }

    static func total(_ subtotal: Double) -> Double {
        subtotal > 0 ? (subtotal + vat(subtotal)).rounded(toPlaces: 2) : 0
    }
}

extension Double {
    func rounded(toPlaces places: Int) -> Double {
        let divisor = pow(10.0, Double(places))
        return (self * divisor).rounded() / divisor
    }
}
