import SwiftUI

/// סוגי טפסי עריכה/יצירה הנתמכים באפליקציה.
enum EditFormKind: String, Identifiable {
    case customer
    case reminder
    case paymentRow
    case hrEmployee
    case hrHours
    case workingOrderNote
    case workManager
    case constructionCompany
    case withholding

    var id: String { rawValue }

    /// איזה טופס עריכה זמין לכל דומיין (אם בכלל).
    static func form(for domain: Domain) -> EditFormKind? {
        switch domain {
        case .customers, .inactiveCustomers: return .customer
        case .marketingReminders: return .reminder
        case .paymentsTransfer: return .paymentRow
        case .hrEmployees: return .hrEmployee
        case .hrHours: return .hrHours
        case .workingOrders: return .workingOrderNote
        case .marketingWorkManagers: return .workManager
        case .marketingConstructionCompanies: return .constructionCompany
        case .financeCustomerWithholdings: return .withholding
        default: return nil
        }
    }

    var title: String {
        switch self {
        case .customer: return "פרטי לקוח"
        case .reminder: return "תזכורת"
        case .paymentRow: return "שורת תשלום"
        case .hrEmployee: return "פרטי עובד"
        case .hrHours: return "דיווח שעות"
        case .workingOrderNote: return "הערה להזמנה"
        case .workManager: return "מנהל עבודה"
        case .constructionCompany: return "חברת בנייה"
        case .withholding: return "ניכוי מס במקור"
        }
    }

    struct Field: Identifiable {
        let key: String
        let label: String
        var keyboard: UIKeyboardType = .default
        var multiline: Bool = false
        /// אפשרויות סגורות (value, label) — מוצג כתפריט במקום שדה טקסט.
        var options: [(value: String, label: String)]? = nil
        var id: String { key }
    }

    var fields: [Field] {
        switch self {
        case .customer:
            return [
                Field(key: "customer_name", label: "שם לקוח"),
                Field(key: "customer_id", label: "ח.פ / ע.מ", keyboard: .numberPad),
                Field(key: "contact_person", label: "איש קשר"),
                Field(key: "phone", label: "טלפון", keyboard: .phonePad),
                Field(key: "mobile", label: "נייד", keyboard: .phonePad),
                Field(key: "emails", label: "אימייל", keyboard: .emailAddress),
                Field(key: "address", label: "כתובת"),
                Field(key: "city", label: "עיר"),
                Field(key: "payment_terms_days", label: "ימי אשראי", keyboard: .numberPad),
                Field(key: "customer_domain", label: "תחום"),
                Field(key: "remarks", label: "הערות", multiline: true),
            ]
        case .reminder:
            return [
                Field(key: "customer_name", label: "לקוח"),
                Field(key: "contact_name", label: "איש קשר"),
                Field(key: "phone", label: "טלפון", keyboard: .phonePad),
                Field(key: "emails", label: "אימייל", keyboard: .emailAddress),
                Field(key: "due_date", label: "תאריך יעד (YYYY-MM-DD)"),
                Field(key: "due_time", label: "שעה (HH:MM)"),
                Field(key: "channel", label: "ערוץ", options: [
                    ("phone", "טלפון"), ("email", "מייל"), ("whatsapp", "ווטסאפ"),
                ]),
                Field(key: "note_text", label: "תוכן התזכורת", multiline: true),
            ]
        case .paymentRow:
            return [
                Field(key: "customer_name", label: "לקוח / ספק"),
                Field(key: "payment_direction", label: "כיוון (תשלום/גבייה)"),
                Field(key: "amount", label: "סכום", keyboard: .decimalPad),
                Field(key: "due_date", label: "תאריך יעד (DD/MM/YYYY)"),
                Field(key: "invoice_date", label: "תאריך חשבונית (DD/MM/YYYY)"),
                Field(key: "po_number", label: "מס' הזמנה"),
                Field(key: "tax_invoice_number", label: "מס' חשבונית מס"),
                Field(key: "notes", label: "הערות", multiline: true),
            ]
        case .hrEmployee:
            return [
                Field(key: "full_name", label: "שם מלא"),
                Field(key: "id_number", label: "ת.ז", keyboard: .numberPad),
                Field(key: "employment_type", label: "סוג העסקה (global/hourly)"),
                Field(key: "base_salary", label: "שכר בסיס", keyboard: .decimalPad),
                Field(key: "hourly_rate", label: "תעריף שעה", keyboard: .decimalPad),
                Field(key: "phone", label: "טלפון", keyboard: .phonePad),
                Field(key: "email", label: "אימייל", keyboard: .emailAddress),
                Field(key: "start_date", label: "תחילת עבודה (YYYY-MM-DD)"),
                Field(key: "notes", label: "הערות", multiline: true),
            ]
        case .hrHours:
            return [
                Field(key: "employee_name", label: "עובד"),
                Field(key: "month_key", label: "חודש (YYYY-MM)"),
                Field(key: "regular_hours", label: "שעות רגילות", keyboard: .decimalPad),
                Field(key: "overtime_hours", label: "שעות נוספות", keyboard: .decimalPad),
                Field(key: "hourly_rate", label: "תעריף שעה", keyboard: .decimalPad),
            ]
        case .workingOrderNote:
            // הרשומה מחזיקה את ההערה ב-order_note_text; פרמטר השליחה לשרת הוא note_text.
            return [
                Field(key: "order_note_text", label: "הערה להזמנה", multiline: true),
            ]
        case .workManager:
            return [
                Field(key: "full_name", label: "שם מלא"),
                Field(key: "company_name", label: "חברה"),
                Field(key: "phone_1", label: "טלפון", keyboard: .phonePad),
                Field(key: "phone_2", label: "טלפון נוסף", keyboard: .phonePad),
                Field(key: "email", label: "אימייל", keyboard: .emailAddress),
                Field(key: "current_workplace", label: "מקום עבודה נוכחי"),
            ]
        case .constructionCompany:
            return [
                Field(key: "company_name", label: "שם חברה"),
                Field(key: "company_id", label: "ח.פ", keyboard: .numberPad),
                Field(key: "phone", label: "טלפון", keyboard: .phonePad),
                Field(key: "email", label: "אימייל", keyboard: .emailAddress),
                Field(key: "address", label: "כתובת"),
                Field(key: "notes", label: "הערות", multiline: true),
            ]
        case .withholding:
            return [
                Field(key: "customer_name", label: "לקוח"),
                Field(key: "invoice_number", label: "מס' חשבונית"),
                Field(key: "receipt_number", label: "מס' קבלה"),
                Field(key: "receipt_date", label: "תאריך קבלה (YYYY-MM-DD)"),
                Field(key: "gross_amount", label: "סכום ברוטו", keyboard: .decimalPad),
                Field(key: "withholding_applied", label: "נוכה במקור (TRUE/FALSE)"),
            ]
        }
    }

    /// שדה חובה ראשי לוולידציה.
    var requiredKey: String? {
        switch self {
        case .customer: return "customer_name"
        case .reminder: return "customer_name"
        case .paymentRow: return "customer_name"
        case .hrEmployee: return "full_name"
        case .hrHours: return "employee_name"
        case .workingOrderNote: return nil
        case .workManager: return "full_name"
        case .constructionCompany: return "company_name"
        case .withholding: return "customer_name"
        }
    }
}
