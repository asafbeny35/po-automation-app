import SwiftUI

/// טאב "עוד" — שיווק, עובדים, מלאי, הנהלה והגדרות.
struct MoreHubView: View {
    @Environment(SessionStore.self) private var session

    private struct Entry: Identifiable {
        let id: String
        let title: String
        let subtitle: String
        let icon: String
        let tint: Color
    }

    private let entries: [Entry] = [
        Entry(id: "marketing", title: "שיווק", subtitle: "פייפליין, תזכורות, מנהלי עבודה וחברות בנייה",
              icon: "megaphone.fill", tint: BYTheme.Palette.pink),
        Entry(id: "hr", title: "עובדים ושכר", subtitle: "עובדים, שעות, שכר, הפרשות ומסמכים",
              icon: "person.3.fill", tint: BYTheme.Palette.blue),
        Entry(id: "inventory", title: "מלאי ותמחור", subtitle: "רכש, חומרי גלם, גמר ותמחור",
              icon: "square.stack.3d.up.fill", tint: BYTheme.Palette.brown),
        Entry(id: "admin", title: "הנהלה", subtitle: "פזומט, סיבוס, אנשי קשר ומנהלי פרויקטים",
              icon: "building.columns.fill", tint: BYTheme.Palette.indigo),
        Entry(id: "documents", title: "מסמכים", subtitle: "מסמכי שיווק ומנהלה — תצוגה ושליחה",
              icon: "doc.on.doc.fill", tint: BYTheme.Palette.teal),
        Entry(id: "labels", title: "מדבקות משלוח", subtitle: "יצירת מדבקות בלי הזמנה — ישר למדפסת",
              icon: "tag.fill", tint: BYTheme.Palette.amber),
        Entry(id: "loans", title: "הלוואות ומשכנתאות", subtitle: "יתרות, תשלום הבא ולוחות סילוקין",
              icon: "banknote.fill", tint: BYTheme.Palette.green),
        Entry(id: "vehicles", title: "צי רכבים וכלי עבודה", subtitle: "טסטים, ביטוחים ומסמכי רכב",
              icon: "car.fill", tint: BYTheme.Palette.red),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    ForEach(entries) { entry in
                        NavigationLink(value: entry.id) {
                            BYCard {
                                HStack(spacing: 14) {
                                    Image(systemName: entry.icon)
                                        .font(.system(size: 20, weight: .semibold))
                                        .foregroundStyle(entry.tint)
                                        .frame(width: 46, height: 46)
                                        .background(entry.tint.opacity(0.12))
                                        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(entry.title)
                                            .font(.byRowTitle)
                                            .foregroundStyle(BYTheme.textPrimary)
                                        Text(entry.subtitle)
                                            .font(.byCaption)
                                            .foregroundStyle(BYTheme.textSecondary)
                                            .lineLimit(2)
                                    }
                                    Spacer()
                                    Image(systemName: "chevron.backward")
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(BYTheme.textSecondary.opacity(0.5))
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("more-\(entry.id)")
                    }
                    settingsCard
                }
                .padding(16)
            }
            .accessibilityIdentifier("more-screen")
            .background(BYTheme.screenBackground)
            .navigationTitle("עוד")
            .navigationBarTitleDisplayMode(.large)
            .navigationDestination(for: String.self) { id in
                switch id {
                case "marketing":
                    DomainHubContent(
                        title: "שיווק",
                        tabs: [.marketingPipeline, .marketingReminders, .marketingWorkManagers, .marketingConstructionCompanies, .marketingHistory],
                        creationForms: [.marketingReminders: .reminder,
                                        .marketingWorkManagers: .workManager,
                                        .marketingConstructionCompanies: .constructionCompany]
                    )
                case "hr":
                    DomainHubContent(
                        title: "עובדים ושכר",
                        tabs: [.hrEmployees, .hrHours, .hrPayroll, .hrContributions, .hrDocuments, .hrPayslipPrepHistory],
                        creationForms: [.hrEmployees: .hrEmployee, .hrHours: .hrHours]
                    )
                case "inventory":
                    DomainHubContent(
                        title: "מלאי ותמחור",
                        tabs: [.inventoryPurchaseOrders, .inventoryRaw, .inventoryFinish, .inventoryContacts, .supplierDeliveryNotes, .pricingItems, .pricingComponents],
                        flows: [.inventoryPurchaseOrders: .supplierPOComposer]
                    )
                case "labels":
                    LabelsOnlyView()
                case "loans":
                    LoansView()
                case "vehicles":
                    VehiclesView()
                case "admin":
                    DomainHubContent(
                        title: "הנהלה",
                        tabs: [.pazomat, .sibus, .deliveryContacts, .projectManagers, .financeSettings]
                    )
                case "documents":
                    DocumentsView()
                default:
                    EmptyView()
                }
            }
        }
        .accessibilityIdentifier("more-screen")
    }

    // MARK: - הגדרות

    @Environment(BiometricLock.self) private var biometricLock

    private var settingsCard: some View {
        BYCard {
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    Image(systemName: "person.crop.circle.fill")
                        .font(.system(size: 34))
                        .foregroundStyle(BYTheme.Palette.brand)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(session.currentUserName.isEmpty ? "מחובר" : session.currentUserName)
                            .font(.byRowTitle)
                            .foregroundStyle(BYTheme.textPrimary)
                            .accessibilityIdentifier("settings-user-name")
                        Text("מחובר למערכת · \(AppConfig.baseURL.host() ?? "")")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                    }
                    Spacer()
                }
                .padding(.bottom, 12)
                if biometricLock.isSupported {
                    Divider().overlay(BYTheme.separator)
                    Toggle(isOn: Binding(
                        get: { biometricLock.isEnabled },
                        set: { wantsOn in
                            if wantsOn {
                                Task {
                                    if await biometricLock.enableAfterVerification() {
                                        session.showSuccess("הכניסה עם \(biometricLock.biometryLabel) הופעלה.")
                                    } else {
                                        session.showError("האימות נכשל — הכניסה הביומטרית לא הופעלה.")
                                    }
                                }
                            } else {
                                biometricLock.isEnabled = false
                            }
                        }
                    )) {
                        HStack(spacing: 10) {
                            Image(systemName: "faceid")
                                .font(.system(size: 18))
                                .foregroundStyle(BYTheme.Palette.brand)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("כניסה עם \(biometricLock.biometryLabel)")
                                    .font(.byRowTitle)
                                    .foregroundStyle(BYTheme.textPrimary)
                                Text("נעילת האפליקציה בכל פתיחה")
                                    .font(.byCaption)
                                    .foregroundStyle(BYTheme.textSecondary)
                            }
                        }
                    }
                    .tint(BYTheme.Palette.brand)
                    .padding(.vertical, 10)
                    .accessibilityIdentifier("faceid-toggle")
                }
                Divider().overlay(BYTheme.separator)
                Button {
                    Haptics.tap()
                    Task { await session.logout() }
                } label: {
                    HStack {
                        Image(systemName: "rectangle.portrait.and.arrow.left")
                        Text("התנתקות")
                        Spacer()
                    }
                    .font(.byRowTitle)
                    .foregroundStyle(BYTheme.Palette.red)
                    .padding(.top, 12)
                }
                .accessibilityIdentifier("logout-button")
            }
        }
    }
}
