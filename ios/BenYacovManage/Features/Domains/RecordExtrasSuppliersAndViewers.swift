import SwiftUI

// MARK: - קבלה בשורת תשלומים (רק לשורות גבייה פתוחות עם חשבונית)

struct PaymentsReceiptSection: View {
    let record: DomainRecord

    var body: some View {
        let card = ReceiptCard(record: record)
        if card.isRelevant {
            card
        }
    }
}

// MARK: - שליחת הזמנת רכש לספק (מייל / וואטסאפ)

struct SupplierPOSendCard: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    @State private var showEmailSheet = false
    @State private var showWhatsappSheet = false
    @State private var emailRecipients = ""
    @State private var whatsappPhone = ""
    @State private var whatsappMessage = ""

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("שליחה לספק", systemImage: "paperplane.fill")
                    .font(.byRowTitle)
                    .accessibilityIdentifier("supplier-po-send-card")
                HStack(spacing: 10) {
                    sendButton("במייל", icon: "envelope.fill", tint: BYTheme.Palette.teal, id: "supplier-po-email") {
                        emailRecipients = record["supplier_email"]
                        showEmailSheet = true
                    }
                    sendButton("בוואטסאפ", icon: "message.fill", tint: BYTheme.Palette.green, id: "supplier-po-whatsapp") {
                        whatsappPhone = record["supplier_phone"]
                        whatsappMessage = "היי, מצורפת הזמנת רכש \(record["po_number"]) מבן יעקב פתרונות טקסטיל."
                        showWhatsappSheet = true
                    }
                }
            }
        }
        .sheet(isPresented: $showEmailSheet) {
            SendMessageSheet(
                title: "שליחת הזמנה לספק במייל",
                fieldLabel: "נמענים",
                fieldValue: $emailRecipients,
                fieldKeyboard: .emailAddress,
                submitID: "supplier-po-email-submit"
            ) { _ in
                let api = session.api
                let historyID = record.first(of: ["history_id", "row_id"])
                let recipients = emailRecipients
                return try await api.sendSupplierPOEmail(historyID: historyID, recipients: recipients)
            }
        }
        .sheet(isPresented: $showWhatsappSheet) {
            SendWhatsappSheet(
                title: "שליחת הזמנה לספק בוואטסאפ",
                phone: $whatsappPhone,
                message: $whatsappMessage,
                submitID: "supplier-po-whatsapp-submit"
            ) {
                let api = session.api
                let historyID = record.first(of: ["history_id", "row_id"])
                let phone = whatsappPhone
                let message = whatsappMessage
                try await api.sendSupplierPOWhatsapp(historyID: historyID, phone: phone, message: message)
                return "הזמנת הרכש נשלחה בוואטסאפ."
            }
        }
    }

    private func sendButton(_ title: String, icon: String, tint: Color, id: String,
                            action: @escaping () -> Void) -> some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            VStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .semibold))
                Text(title)
                    .font(.byCaption.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(tint.opacity(0.12))
            .foregroundStyle(tint)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .accessibilityIdentifier(id)
    }
}

// MARK: - צפייה בתעודת משלוח ספק (מסמך המקור)

struct SupplierNoteSourceCard: View {
    let record: DomainRecord
    @State private var showPreview = false

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("מסמך המקור", systemImage: "doc.richtext")
                    .font(.byRowTitle)
                Button {
                    Haptics.tap()
                    showPreview = true
                } label: {
                    Label("צפייה בתעודת המשלוח", systemImage: "eye.fill")
                        .font(.byBody.weight(.medium))
                }
                .accessibilityIdentifier("supplier-note-view")
            }
        }
        .sheet(isPresented: $showPreview) {
            DocumentPreviewView(
                title: "תעודת משלוח \(record["delivery_note_number"])",
                path: "supplier-delivery-note-source/\(record.first(of: ["record_id", "row_id"]))"
            )
        }
    }
}

// MARK: - צפייה בקובץ הערה של הזמנה בעבודה

struct WorkingOrderNoteFileCard: View {
    let record: DomainRecord
    @State private var showPreview = false

    /// מוצג רק כשקיים קובץ מצורף להערה.
    var isRelevant: Bool { !record["order_note_file_name"].isEmpty }

    var body: some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("קובץ מצורף להערה", systemImage: "paperclip")
                    .font(.byRowTitle)
                Button {
                    Haptics.tap()
                    showPreview = true
                } label: {
                    Label(record["order_note_file_name"], systemImage: "eye.fill")
                        .font(.byBody.weight(.medium))
                        .lineLimit(1)
                }
                .accessibilityIdentifier("working-order-note-file")
            }
        }
        .sheet(isPresented: $showPreview) {
            DocumentPreviewView(
                title: record["order_note_file_name"],
                path: "working-order-note-file/\(record["row_id"])"
            )
        }
    }
}

struct WorkingOrderExtrasSection: View {
    @Environment(SessionStore.self) private var session
    let record: DomainRecord

    /// הרשומה המלאה (מתוך payload_json) שנטענת לקומפוזר — כמו "יצירת הזמנה" בדסקטופ.
    @State private var composerRecord: DomainRecord?

    var body: some View {
        VStack(spacing: 14) {
            BYCard {
                VStack(alignment: .leading, spacing: 10) {
                    Label("המשך יצירת ההזמנה", systemImage: "doc.badge.gearshape.fill")
                        .font(.byRowTitle)
                    Text("ההזמנה פורסרה ושמורה בעבודה. אפשר לערוך את הפרטים וליצור את המסמכים בסנדבוקס או בפרודקשן — בפרודקשן היא תרד אוטומטית מהזמנות בעבודה.")
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                    BYPrimaryButton(title: "יצירת הזמנה", icon: "arrow.left.circle.fill") {
                        openComposer()
                    }
                    .accessibilityIdentifier("working-order-create")
                }
            }
            let card = WorkingOrderNoteFileCard(record: record)
            if card.isRelevant {
                card
            }
        }
        .sheet(item: $composerRecord) { loaded in
            OrderComposerView(initialRecord: loaded)
        }
    }

    private func openComposer() {
        Haptics.tap()
        guard let data = record["payload_json"].data(using: .utf8),
              let decoded = try? JSONDecoder().decode([String: JSONValue].self, from: data),
              !decoded.isEmpty else {
            session.showError("נתוני ההזמנה פגומים — אי אפשר לטעון אותה למסך.")
            return
        }
        var fields = decoded
        // כמו בדסקטופ: מזהה השורה נוסע עם ההזמנה, וה-finalize בפרודקשן מסיר אותה מ"בעבודה".
        fields["working_order_row_id"] = .string(record["row_id"])
        composerRecord = DomainRecord(fields: fields)
    }
}
