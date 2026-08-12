import Foundation

/// סיווג אישורי מסירה ל"טרם נשלח" מול "נשלח", באותו כלל שהדסקטופ מפעיל
/// (`isDeliveryConfirmationSent`): רק הערך TRUE בעמודת `sent` נחשב שנשלח.
enum DeliveryConfirmations {
    static func isSent(_ record: DomainRecord) -> Bool {
        record["sent"].trimmingCharacters(in: .whitespaces).uppercased() == "TRUE"
    }
}
