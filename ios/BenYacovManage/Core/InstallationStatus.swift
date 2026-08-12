import SwiftUI

/// סטטוסי התקנה — צבע אחיד לכל הגרסאות (ראשית + קלאסי).
enum InstallationStatus {
    static func tint(_ status: String) -> Color {
        switch status {
        case "ממתין לתיאום": return BYTheme.Palette.amber
        case "תואם": return BYTheme.Palette.blue
        case "הותקן חלקית": return BYTheme.Palette.purple
        case "הושלם": return BYTheme.Palette.green
        case "מושהה": return BYTheme.Palette.gray
        case "בוטל": return BYTheme.Palette.red
        default: return BYTheme.Palette.indigo
        }
    }

    /// שורת ההתקדמות של תיק התקנה: "הותקן 3 מתוך 5 · 2 ביקורים".
    static func progressSummary(_ record: DomainRecord) -> String {
        var parts: [String] = []
        let installed = record["total_installed_quantity"]
        let ordered = record["total_ordered_quantity"]
        if !installed.isEmpty, !ordered.isEmpty {
            parts.append("הותקן \(installed) מתוך \(ordered)")
        }
        let visits = record["visit_count"]
        if !visits.isEmpty, visits != "0" {
            parts.append("\(visits) ביקורים")
        }
        if !record["next_visit_date"].isEmpty {
            parts.append("ביקור הבא: \(record["next_visit_date"])")
        } else if !record["delay_reason"].isEmpty {
            parts.append(record["delay_reason"])
        }
        return parts.joined(separator: " · ")
    }
}
