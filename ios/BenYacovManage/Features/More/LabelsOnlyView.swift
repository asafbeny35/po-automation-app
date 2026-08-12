import SwiftUI

/// יצירת מדבקות משלוח בלבד (בלי הזמנה) — כמו הכלי בדסקטופ.
struct LabelsOnlyView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    struct LabelEntry: Identifiable {
        let id = UUID()
        var customer = ""
        var address = ""
        var contactName = ""
        var phone = ""
        var labelCount = "1"
    }

    @State private var entries: [LabelEntry] = [LabelEntry()]
    @State private var isSending = false
    @State private var errorMessage: String?
    @State private var doneMessage: String?
    @State private var recentCustomers: [DomainRecord] = []

    var body: some View {
        Group {
            if let doneMessage {
                doneView(doneMessage)
            } else {
                formView
            }
        }
        .background(BYTheme.screenBackground)
        .navigationTitle("מדבקות משלוח")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            recentCustomers = (try? await session.api.recentManualCustomers()) ?? []
        }
        .scrollDismissesKeyboard(.immediately)
    }

    private var formView: some View {
        ScrollView {
            VStack(spacing: 14) {
                // עוגן זיהוי לטסטים — לא על המיכל, כדי לא לדרוס מזהי ילדים.
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("labels-screen")
                ForEach($entries) { $entry in
                    BYCard {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Label("מדבקה", systemImage: "tag.fill")
                                    .font(.byRowTitle)
                                Spacer()
                                if !recentCustomers.isEmpty {
                                    Menu {
                                        ForEach(recentCustomers.prefix(8)) { customer in
                                            Button(customer["customer_name"]) {
                                                entry.customer = customer["customer_name"]
                                                entry.phone = customer["customer_phone"]
                                                Haptics.tap()
                                            }
                                        }
                                    } label: {
                                        Image(systemName: "clock.arrow.circlepath")
                                            .font(.system(size: 15, weight: .semibold))
                                    }
                                    .accessibilityIdentifier("labels-recent-customers")
                                }
                                if entries.count > 1 {
                                    Button {
                                        entries.removeAll { $0.id == entry.id }
                                    } label: {
                                        Image(systemName: "minus.circle")
                                            .foregroundStyle(BYTheme.Palette.red)
                                    }
                                }
                            }
                            row("לקוח", text: $entry.customer, id: "labels-customer")
                            row("כתובת", text: $entry.address, id: "labels-address")
                            row("איש קשר", text: $entry.contactName, id: "labels-contact")
                            row("טלפון", text: $entry.phone, id: "labels-phone", keyboard: .phonePad)
                            row("מספר מדבקות", text: $entry.labelCount, id: "labels-count", keyboard: .numberPad)
                        }
                    }
                }
                Button {
                    Haptics.tap()
                    entries.append(LabelEntry())
                } label: {
                    Label("הוספת מדבקה נוספת", systemImage: "plus.circle.fill")
                        .font(.byBody.weight(.semibold))
                }
                .accessibilityIdentifier("labels-add")
                BYPrimaryButton(title: "יצירת המדבקות", icon: "printer.fill", isLoading: isSending) {
                    Task { await create() }
                }
                .accessibilityIdentifier("labels-create")
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.byCaption.weight(.medium))
                        .foregroundStyle(BYTheme.Palette.red)
                        .accessibilityIdentifier("labels-error")
                }
            }
            .padding(16)
        }
    }

    private func doneView(_ message: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(BYTheme.Palette.green)
                .accessibilityIdentifier("labels-done")
            Text(message)
                .font(.byTitle)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .accessibilityIdentifier("labels-done-message")
            BYPrimaryButton(title: "סגירה", icon: "checkmark") { dismiss() }
                .padding(.horizontal, 40)
                .accessibilityIdentifier("labels-done-close")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func row(_ label: String, text: Binding<String>, id: String,
                     keyboard: UIKeyboardType = .default) -> some View {
        LabeledContent(label) {
            TextField("", text: text)
                .keyboardType(keyboard)
                .multilineTextAlignment(.leading)
                .accessibilityIdentifier(id)
        }
    }

    private func create() async {
        let valid = entries.filter { !$0.customer.trimmingCharacters(in: .whitespaces).isEmpty }
        guard !valid.isEmpty else {
            errorMessage = "יש למלא שם לקוח לפחות במדבקה אחת."
            Haptics.error()
            return
        }
        errorMessage = nil
        isSending = true
        defer { isSending = false }
        let labels: [[String: Any]] = valid.map { entry in
            [
                "customer": entry.customer, "address": entry.address,
                "contact_name": entry.contactName, "phone": entry.phone,
                "label_count": Int(entry.labelCount) ?? 1,
            ]
        }
        do {
            let message = try await session.api.createLabelsOnly(labels: labels)
            doneMessage = message
            Haptics.success()
        } catch {
            errorMessage = (error as? APIError)?.message ?? "יצירת המדבקות נכשלה."
            Haptics.error()
        }
    }
}
