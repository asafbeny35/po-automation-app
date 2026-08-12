import SwiftUI

/// כל דומייני הנתונים שהשרת חושף דרך `/mobile/domains/{domain}`.
enum Domain: String, CaseIterable, Identifiable, Sendable {
    case customers
    case inactiveCustomers = "inactive_customers"
    case orderHistory = "order_history"
    case quoteHistory = "quote_history"
    case workingOrders = "working_orders"
    case projectManagers = "project_managers"
    case marketingPipeline = "marketing_pipeline"
    case marketingHistory = "marketing_history"
    case marketingReminders = "marketing_reminders"
    case marketingWorkManagers = "marketing_work_managers"
    case marketingConstructionCompanies = "marketing_construction_companies"
    case financeInvoices = "finance_invoices"
    case financeBankMovements = "finance_bank_movements"
    case financeCustomerWithholdings = "finance_customer_withholdings"
    case financeSettings = "finance_settings"
    case paymentsTransfer = "payments_transfer"
    case deliveryConfirmations = "delivery_confirmations"
    case deliveryContacts = "delivery_contacts"
    case pazomat
    case sibus
    case inventoryPurchaseOrders = "inventory_purchase_orders"
    case inventoryRaw = "inventory_raw"
    case inventoryFinish = "inventory_finish"
    case inventoryContacts = "inventory_contacts"
    case pricingItems = "pricing_items"
    case pricingComponents = "pricing_components"
    case supplierDeliveryNotes = "supplier_delivery_notes"
    case hrEmployees = "hr_employees"
    case hrHours = "hr_hours"
    case hrPayroll = "hr_payroll"
    case hrContributions = "hr_contributions"
    case hrDocuments = "hr_documents"
    case hrPayslipPrepHistory = "hr_payslip_prep_history"
    // דומיינים עם endpoint ייעודי (לא תחת /mobile/domains).
    case installationCases = "installation_cases"
    case installationVisits = "installation_visits"

    var id: String { rawValue }
    var spec: DomainSpec { DomainSpec.catalog[self]! }

    /// האם הדומיין מוגש דרך `/mobile/domains/{domain}` (33 הדומיינים של השרת).
    var isMobileDomain: Bool {
        self != .installationCases && self != .installationVisits
    }

    /// מזהה המקטע המקביל בתשובת `/mobile/bootstrap` (שונה משם הדומיין בחלק מהמקרים).
    /// נתיב epoch לבדיקת שינויים מרחוק — לדומיינים עם watch חי.
    var epochPath: String? {
        switch self {
        case .financeInvoices: return "finance-invoices-epoch"
        default: return nil
        }
    }

    var bootstrapSectionID: String {
        switch self {
        case .customers: return "customers-active"
        case .inactiveCustomers: return "customers-inactive"
        case .orderHistory: return "orders-history"
        case .quoteHistory: return "quotes-history"
        case .financeCustomerWithholdings: return "finance-withholdings"
        case .financeBankMovements: return "finance-bank"
        default: return rawValue.replacingOccurrences(of: "_", with: "-")
        }
    }
}

/// הגדרת תצוגה לדומיין: איך שורה נראית ברשימה, לפי מה מחפשים, ומה מציגים בפירוט.
struct DomainSpec: Sendable {
    let title: String
    let icon: String
    let tint: DomainTint
    /// מפתחות לכותרת השורה (הראשון שאינו ריק).
    let titleKeys: [String]
    let subtitleKeys: [String]
    /// מפתח לתג סטטוס (אופציונלי).
    let badgeKey: String?
    /// מפתח לסכום כספי (אופציונלי).
    let amountKey: String?
    let dateKeys: [String]
    let searchKeys: [String]
    /// סדר עדיפות של שדות במסך הפירוט. שדות שלא כאן מוצגים אחריהם.
    let detailKeys: [String]

    enum DomainTint: String, Sendable {
        case blue, teal, amber, purple, green, red, indigo, brown, pink, gray

        var color: Color {
            switch self {
            case .blue: return BYTheme.Palette.blue
            case .teal: return BYTheme.Palette.teal
            case .amber: return BYTheme.Palette.amber
            case .purple: return BYTheme.Palette.purple
            case .green: return BYTheme.Palette.green
            case .red: return BYTheme.Palette.red
            case .indigo: return BYTheme.Palette.indigo
            case .brown: return BYTheme.Palette.brown
            case .pink: return BYTheme.Palette.pink
            case .gray: return BYTheme.Palette.gray
            }
        }
    }
}

extension DomainSpec {
    static let catalog: [Domain: DomainSpec] = [
        .customers: DomainSpec(
            title: "לקוחות פעילים", icon: "person.2.fill", tint: .blue,
            titleKeys: ["customer_name"],
            subtitleKeys: ["city", "contact_person", "phone", "mobile"],
            badgeKey: "customer_domain", amountKey: "balance_amount",
            dateKeys: ["last_update_date"],
            searchKeys: ["customer_name", "customer_id", "phone", "mobile", "emails", "city", "contact_person"],
            detailKeys: ["customer_name", "customer_id", "customer_domain", "contact_person", "phone", "mobile", "emails", "address", "city", "payment_terms_days", "accounting_key", "income_amount", "payment_amount", "balance_amount", "remarks"]
        ),
        .inactiveCustomers: DomainSpec(
            title: "לקוחות לא פעילים", icon: "person.2.slash.fill", tint: .gray,
            titleKeys: ["customer_name"],
            subtitleKeys: ["city", "contact_person", "phone"],
            badgeKey: "customer_domain", amountKey: "balance_amount",
            dateKeys: ["last_update_date"],
            searchKeys: ["customer_name", "customer_id", "phone", "emails", "city"],
            detailKeys: ["customer_name", "customer_id", "customer_domain", "contact_person", "phone", "mobile", "emails", "address", "city", "payment_terms_days", "remarks"]
        ),
        .orderHistory: DomainSpec(
            title: "היסטוריית הזמנות", icon: "shippingbox.fill", tint: .indigo,
            titleKeys: ["customer_name"],
            subtitleKeys: ["project", "delivery_address"],
            badgeKey: "mode", amountKey: "total",
            dateKeys: ["created_at", "po_date"],
            searchKeys: ["customer_name", "po_number", "quote_number", "project", "delivery_address", "contact_name", "tax_invoice_number", "delivery_number"],
            detailKeys: ["customer_name", "po_number", "quote_number", "po_date", "project", "delivery_address", "contact_name", "contact_phone", "payment_terms_label", "delivery_number", "tax_invoice_number", "subtotal", "vat", "total", "input_source", "created_at"]
        ),
        .quoteHistory: DomainSpec(
            title: "הצעות מחיר", icon: "doc.text.fill", tint: .teal,
            titleKeys: ["customer_name"],
            subtitleKeys: ["item_description", "project", "delivery_address"],
            badgeKey: "mode", amountKey: "total",
            dateKeys: ["quote_date", "created_at"],
            searchKeys: ["customer_name", "quote_number", "project", "contact_name", "item_description"],
            detailKeys: ["customer_name", "quote_number", "quote_date", "item_description", "project", "delivery_address", "contact_name", "contact_phone", "payment_terms_label", "subtotal", "vat", "total", "input_source", "created_at"]
        ),
        .workingOrders: DomainSpec(
            title: "הזמנות בעבודה", icon: "hammer.fill", tint: .amber,
            titleKeys: ["customer_name"],
            subtitleKeys: ["project", "delivery_address"],
            badgeKey: nil, amountKey: "total",
            dateKeys: ["po_date", "created_at"],
            searchKeys: ["customer_name", "po_number", "project", "delivery_address", "contact_name"],
            detailKeys: ["customer_name", "po_number", "po_date", "project", "delivery_address", "contact_name", "contact_phone", "customer_phone", "subtotal", "vat", "total", "order_note_text", "source_file_name", "created_at", "updated_at"]
        ),
        .projectManagers: DomainSpec(
            title: "מנהלי פרויקטים", icon: "person.badge.shield.checkmark.fill", tint: .purple,
            titleKeys: ["contact_name", "company"],
            subtitleKeys: ["company", "site_address", "item"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["order_date", "updated_at"],
            searchKeys: ["contact_name", "company", "site_address", "contact_phone", "item"],
            detailKeys: ["contact_name", "contact_phone", "company", "tax_id", "site_address", "item", "order_date", "history_dates", "updated_at"]
        ),
        .marketingPipeline: DomainSpec(
            title: "לקוחות בתהליך שיווק", icon: "megaphone.fill", tint: .pink,
            titleKeys: ["customer_name"],
            subtitleKeys: ["item_name", "contact_name"],
            badgeKey: "comm_status", amountKey: nil,
            dateKeys: ["quote_date", "comm_sent_at"],
            searchKeys: ["customer_name", "quote_number", "contact_name", "item_name", "emails", "phone"],
            detailKeys: ["customer_name", "customer_id", "quote_number", "quote_date", "item_name", "contact_name", "phone", "emails", "note_text", "comm_status", "comm_sent_at", "mail_subject", "mail_sent_at"]
        ),
        .marketingHistory: DomainSpec(
            title: "היסטוריית שיווק", icon: "clock.arrow.circlepath", tint: .pink,
            titleKeys: ["customer_name", "subject", "action_type"],
            subtitleKeys: ["subject", "action_type"],
            badgeKey: "channel", amountKey: nil,
            dateKeys: ["created_at"],
            searchKeys: ["customer_name", "subject", "action_type", "channel", "result"],
            detailKeys: ["customer_name", "action_type", "channel", "subject", "result", "created_at"]
        ),
        .marketingReminders: DomainSpec(
            title: "תזכורות שיווק", icon: "bell.badge.fill", tint: .red,
            titleKeys: ["customer_name"],
            subtitleKeys: ["note_text", "contact_name"],
            badgeKey: "status", amountKey: nil,
            dateKeys: ["due_date"],
            searchKeys: ["customer_name", "contact_name", "note_text", "phone", "emails"],
            detailKeys: ["customer_name", "contact_name", "phone", "emails", "note_text", "due_date", "due_time", "status", "channel", "message", "comm_status", "comm_sent_at", "created_at", "completed_at"]
        ),
        .marketingWorkManagers: DomainSpec(
            title: "מנהלי עבודה", icon: "person.crop.rectangle.stack.fill", tint: .purple,
            titleKeys: ["full_name"],
            subtitleKeys: ["company_name", "current_workplace"],
            badgeKey: "active_status", amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["full_name", "company_name", "phone_1", "phone_2", "email", "current_employer", "current_workplace"],
            detailKeys: ["full_name", "company_name", "phone_1", "phone_2", "phone_3", "email", "active_status", "current_employer", "current_workplace", "project_manager_match", "updated_at"]
        ),
        .marketingConstructionCompanies: DomainSpec(
            title: "חברות בנייה", icon: "building.2.fill", tint: .brown,
            titleKeys: ["company_name"],
            subtitleKeys: ["address", "notes"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["company_name", "company_id", "phone", "email", "address", "notes"],
            detailKeys: ["company_name", "company_id", "phone", "email", "address", "notes", "details_url", "updated_at"]
        ),
        .financeInvoices: DomainSpec(
            title: "חשבוניות ספקים", icon: "doc.plaintext.fill", tint: .green,
            titleKeys: ["supplier_name"],
            subtitleKeys: ["service_or_product"],
            badgeKey: nil, amountKey: "total",
            dateKeys: ["invoice_date"],
            searchKeys: ["supplier_name", "reference_number", "service_or_product", "invoice_date"],
            detailKeys: ["supplier_name", "invoice_date", "reference_number", "allocation_number", "service_or_product", "subtotal", "vat", "total", "source_file_name"]
        ),
        .financeBankMovements: DomainSpec(
            title: "תנועות בנק", icon: "building.columns.fill", tint: .green,
            titleKeys: ["description"],
            subtitleKeys: ["account_name", "operation_type"],
            badgeKey: "channel", amountKey: "amount",
            dateKeys: ["transaction_date"],
            searchKeys: ["description", "account_name", "company_name", "reference", "operation_type"],
            detailKeys: ["description", "transaction_date", "value_date", "amount", "balance", "account_name", "account_number", "company_name", "operation_type", "reference", "channel", "fee_or_notes"]
        ),
        .financeCustomerWithholdings: DomainSpec(
            title: "ניכויי מס לקוחות", icon: "percent", tint: .green,
            titleKeys: ["customer_name"],
            subtitleKeys: ["invoice_number", "receipt_number"],
            badgeKey: "withholding_applied", amountKey: "withheld_amount",
            dateKeys: ["receipt_date"],
            searchKeys: ["customer_name", "invoice_number", "receipt_number"],
            detailKeys: ["customer_name", "receipt_date", "invoice_number", "receipt_number", "gross_amount", "withholding_percent", "withheld_amount", "paid_amount", "withholding_applied"]
        ),
        .financeSettings: DomainSpec(
            title: "הגדרות כספים", icon: "gearshape.fill", tint: .gray,
            titleKeys: ["setting_key"],
            subtitleKeys: ["setting_value"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["setting_key", "setting_value"],
            detailKeys: ["setting_key", "setting_value", "updated_at"]
        ),
        .paymentsTransfer: DomainSpec(
            title: "תשלומים והעברות", icon: "arrow.left.arrow.right.circle.fill", tint: .green,
            titleKeys: ["customer_name"],
            subtitleKeys: ["notes", "po_number"],
            badgeKey: "payment_direction", amountKey: "amount",
            dateKeys: ["due_date"],
            searchKeys: ["customer_name", "po_number", "tax_invoice_number", "notes", "receipt_number"],
            detailKeys: ["customer_name", "payment_direction", "amount", "due_date", "invoice_date", "paid", "po_number", "tax_invoice_number", "proforma_invoice_number", "receipt_number", "delivery_number", "payment_terms_days", "notes"]
        ),
        .deliveryConfirmations: DomainSpec(
            title: "אישורי מסירה", icon: "checkmark.seal.fill", tint: .teal,
            titleKeys: ["company"],
            subtitleKeys: ["po_number", "target_email"],
            badgeKey: nil, amountKey: "order_total",
            dateKeys: ["order_date", "invoice_date"],
            searchKeys: ["company", "po_number", "tax_invoice_number", "target_email"],
            detailKeys: ["company", "po_number", "order_date", "invoice_date", "tax_invoice_number", "order_total", "target_email", "signed_delivery_name", "coc_name"]
        ),
        .deliveryContacts: DomainSpec(
            title: "אנשי קשר הנה\"ח", icon: "person.text.rectangle.fill", tint: .teal,
            titleKeys: ["accounting_contact_name", "company"],
            subtitleKeys: ["company", "email"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["company", "accounting_contact_name", "phone", "mobile", "email"],
            detailKeys: ["company", "accounting_contact_name", "phone", "mobile", "email", "updated_at"]
        ),
        .pazomat: DomainSpec(
            title: "פזומט", icon: "fuelpump.fill", tint: .amber,
            titleKeys: ["month"],
            subtitleKeys: ["subject", "invoice_number"],
            badgeKey: "status", amountKey: "total_amount",
            dateKeys: ["debit_date"],
            searchKeys: ["month", "invoice_number", "subject"],
            detailKeys: ["month", "status", "invoice_number", "fuel_doc_number", "total_amount", "fuel_amount", "service_amount", "debit_date", "vehicle_count", "card_count", "liters_total", "notes"]
        ),
        .sibus: DomainSpec(
            title: "סיבוס", icon: "fork.knife", tint: .amber,
            titleKeys: ["month"],
            subtitleKeys: ["billing_period", "invoice_number"],
            badgeKey: "status", amountKey: "total_amount",
            dateKeys: ["due_date", "invoice_date"],
            searchKeys: ["month", "invoice_number", "billing_period"],
            detailKeys: ["month", "status", "invoice_number", "invoice_date", "billing_period", "due_date", "subtotal_amount", "vat_amount", "total_amount", "customer_number", "notes"]
        ),
        .inventoryPurchaseOrders: DomainSpec(
            title: "הזמנות רכש לספקים", icon: "cart.fill", tint: .indigo,
            titleKeys: ["supplier_name"],
            subtitleKeys: ["item_description"],
            badgeKey: "mode", amountKey: "total",
            dateKeys: ["po_date", "created_at"],
            searchKeys: ["supplier_name", "po_number", "item_description", "item_sku"],
            detailKeys: ["supplier_name", "po_number", "po_date", "item_description", "item_sku", "item_quantity", "item_unit", "item_unit_price", "subtotal", "vat", "total", "remarks", "created_at"]
        ),
        .inventoryRaw: DomainSpec(
            title: "מלאי חומרי גלם", icon: "square.stack.3d.up.fill", tint: .brown,
            // בדאטה האמיתי product לרוב ריק — החומר או הספק הם הכותרת.
            titleKeys: ["product", "material", "supplier"],
            subtitleKeys: ["supplier", "material"],
            badgeKey: nil, amountKey: "price",
            dateKeys: ["updated_at"],
            searchKeys: ["product", "supplier", "material", "supplier_sku"],
            detailKeys: ["product", "supplier", "supplier_sku", "material", "length", "width", "thickness", "price", "unit", "actual_quantity", "unit_count", "notes", "updated_at"]
        ),
        .inventoryFinish: DomainSpec(
            title: "מלאי גמר", icon: "shippingbox.circle.fill", tint: .brown,
            titleKeys: ["product"],
            subtitleKeys: ["notes"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["product", "notes"],
            detailKeys: ["product", "width", "length", "actual_quantity", "notes", "updated_at"]
        ),
        .inventoryContacts: DomainSpec(
            title: "ספקים ואנשי קשר", icon: "phone.badge.checkmark", tint: .brown,
            titleKeys: ["name", "company"],
            subtitleKeys: ["company", "email"],
            badgeKey: nil, amountKey: nil,
            dateKeys: [],
            searchKeys: ["name", "company", "company_phone", "direct_phone", "email"],
            detailKeys: ["name", "company", "company_phone", "direct_phone", "email"]
        ),
        .pricingItems: DomainSpec(
            title: "פריטי תמחור", icon: "tag.fill", tint: .purple,
            titleKeys: ["name", "item_id"],
            subtitleKeys: ["kind", "pricing_unit"],
            badgeKey: "active", amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["name", "item_id", "kind"],
            detailKeys: ["name", "item_id", "kind", "pricing_unit", "default_width_m", "default_length_m", "labor_minutes", "labor_hour_cost", "shipping_total_cost", "order_quantity", "notes", "active", "updated_at"]
        ),
        .pricingComponents: DomainSpec(
            title: "רכיבי תמחור", icon: "puzzlepiece.fill", tint: .purple,
            titleKeys: ["name", "component_id"],
            subtitleKeys: ["kind", "notes"],
            badgeKey: "active", amountKey: "unit_cost",
            dateKeys: ["updated_at"],
            searchKeys: ["name", "component_id", "kind"],
            detailKeys: ["name", "component_id", "kind", "unit", "unit_cost", "waste_percent", "notes", "active", "updated_at"]
        ),
        .supplierDeliveryNotes: DomainSpec(
            title: "תעודות משלוח ספק", icon: "doc.badge.arrow.up.fill", tint: .indigo,
            titleKeys: ["supplier_name"],
            subtitleKeys: ["item_description", "delivery_note_number"],
            badgeKey: nil, amountKey: nil,
            dateKeys: ["delivery_date"],
            searchKeys: ["supplier_name", "delivery_note_number", "item_description", "customer_name", "product"],
            detailKeys: ["supplier_name", "delivery_note_number", "delivery_date", "item_description", "product", "material", "length", "width", "thickness", "quantity", "unit", "customer_name", "delivery_address", "contact_name", "contact_phone", "notes", "updated_at"]
        ),
        .hrEmployees: DomainSpec(
            title: "עובדים", icon: "person.crop.circle.fill.badge.checkmark", tint: .blue,
            titleKeys: ["full_name"],
            subtitleKeys: ["employment_type", "phone"],
            badgeKey: "active_status", amountKey: "base_salary",
            dateKeys: ["start_date"],
            searchKeys: ["full_name", "id_number", "phone", "email"],
            detailKeys: ["full_name", "id_number", "employment_type", "active_status", "start_date", "base_salary", "hourly_rate", "phone", "email", "pension_fund", "notes", "updated_at"]
        ),
        .hrHours: DomainSpec(
            title: "דיווחי שעות", icon: "clock.fill", tint: .blue,
            titleKeys: ["employee_name"],
            subtitleKeys: ["month_key"],
            badgeKey: "status", amountKey: nil,
            dateKeys: ["updated_at"],
            searchKeys: ["employee_name", "month_key"],
            detailKeys: ["employee_name", "month_key", "regular_hours", "overtime_hours", "hourly_rate", "status", "hours_file_name", "updated_at"]
        ),
        .hrPayroll: DomainSpec(
            title: "שכר", icon: "banknote.fill", tint: .blue,
            titleKeys: ["employee_name"],
            subtitleKeys: ["month_key"],
            badgeKey: "salary_paid", amountKey: "net_amount",
            dateKeys: ["salary_paid_date", "updated_at"],
            searchKeys: ["employee_name", "month_key", "salary_reference"],
            detailKeys: ["employee_name", "month_key", "employment_type", "gross_amount", "net_amount", "salary_paid", "salary_paid_date", "salary_reference", "payslip_file_name", "updated_at"]
        ),
        .hrContributions: DomainSpec(
            title: "הפרשות סוציאליות", icon: "chart.pie.fill", tint: .blue,
            titleKeys: ["employee_name"],
            subtitleKeys: ["month_key"],
            badgeKey: "paid", amountKey: "employer_contribution",
            dateKeys: ["paid_date", "updated_at"],
            searchKeys: ["employee_name", "month_key", "reference_number"],
            detailKeys: ["employee_name", "month_key", "employee_contribution", "employer_contribution", "compensation_amount", "paid", "paid_date", "reference_number", "updated_at"]
        ),
        .hrDocuments: DomainSpec(
            title: "מסמכי עובדים", icon: "folder.fill.badge.person.crop", tint: .blue,
            titleKeys: ["title", "file_name"],
            subtitleKeys: ["employee_name", "category"],
            badgeKey: "category", amountKey: nil,
            dateKeys: ["month_key", "updated_at"],
            searchKeys: ["title", "employee_name", "category", "file_name"],
            detailKeys: ["title", "employee_name", "category", "month_key", "file_name", "updated_at"]
        ),
        .installationCases: DomainSpec(
            title: "התקנות", icon: "wrench.and.screwdriver.fill", tint: .amber,
            titleKeys: ["customer_name"],
            subtitleKeys: ["delivery_address", "project"],
            badgeKey: "status", amountKey: nil,
            dateKeys: ["next_visit_date", "po_date"],
            searchKeys: ["customer_name", "po_number", "delivery_address", "project", "status", "contact_name"],
            detailKeys: ["customer_name", "po_number", "po_date", "status", "delay_reason", "next_visit_date", "last_visit_date", "visit_count", "delivery_address", "project", "contact_name", "contact_phone", "total_ordered_quantity", "total_installed_quantity", "total_remaining_quantity", "notes"]
        ),
        .installationVisits: DomainSpec(
            title: "ביקורי התקנה", icon: "figure.walk.arrival", tint: .amber,
            titleKeys: ["visit_date", "scheduled_date"],
            subtitleKeys: ["summary_text", "notes"],
            badgeKey: "status", amountKey: nil,
            dateKeys: ["visit_date"],
            searchKeys: ["visit_date", "notes", "summary_text", "status"],
            detailKeys: ["visit_date", "scheduled_date", "status", "installed_total_quantity", "summary_text", "notes", "created_at"]
        ),
        .hrPayslipPrepHistory: DomainSpec(
            title: "הכנת תלושים", icon: "envelope.badge.fill", tint: .blue,
            titleKeys: ["month_label", "month_key"],
            subtitleKeys: ["sent_to"],
            badgeKey: "send_mode", amountKey: nil,
            dateKeys: ["sent_at"],
            searchKeys: ["month_label", "month_key", "sent_to"],
            detailKeys: ["month_label", "month_key", "send_mode", "sent_to", "sent_at", "employees_total", "gross_total_label", "attachments_count", "notes"]
        ),
    ]
}
