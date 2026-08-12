import Foundation

/// הפרדת עובדים פעילים מעובדי עבר — אותו כלל כמו `hrEmployeeIsFormer` בדסקטופ:
/// עובד נחשב "עבר" רק כאשר הסטטוס שלו inactive.
enum HREmployees {
    static func isFormer(_ record: DomainRecord) -> Bool {
        let status = record["active_status"].trimmingCharacters(in: .whitespaces).lowercased()
        return (status.isEmpty ? "active" : status) == "inactive"
    }
}
