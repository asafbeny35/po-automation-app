import UIKit
import SwiftUI
import UniformTypeIdentifiers

/// נקודת הכניסה של ה-Share Extension — טוען את הקובץ ששותף ומציג בחירה:
/// חשבונית לטאב כספים או הזמנת רכש לטאב הזמנות.
final class ShareViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear

        let rootView = ShareDecisionView(
            loadAttachment: { [weak self] in try await self?.loadSharedFile() },
            finish: { [weak self] in
                self?.extensionContext?.completeRequest(returningItems: nil)
            }
        )
        let host = UIHostingController(rootView: rootView)
        host.view.backgroundColor = .clear
        addChild(host)
        view.addSubview(host.view)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        host.didMove(toParent: self)
    }

    /// שולף את הקובץ הראשון ששותף (PDF או תמונה).
    private func loadSharedFile() async throws -> ShareDecisionView.SharedFile {
        let attachments = (extensionContext?.inputItems as? [NSExtensionItem])?
            .flatMap { $0.attachments ?? [] } ?? []

        for provider in attachments {
            if provider.hasItemConformingToTypeIdentifier(UTType.pdf.identifier) {
                let (data, name) = try await load(provider, type: UTType.pdf)
                return .init(data: data, filename: name ?? "shared.pdf", mimeType: "application/pdf")
            }
        }
        for provider in attachments {
            if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                let (data, name) = try await load(provider, type: UTType.image)
                return .init(data: data, filename: name ?? "shared.jpg", mimeType: "image/jpeg")
            }
        }
        for provider in attachments {
            if provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
                let (data, name) = try await load(provider, type: UTType.fileURL)
                let isPDF = (name ?? "").lowercased().hasSuffix(".pdf")
                return .init(data: data, filename: name ?? "shared.pdf",
                             mimeType: isPDF ? "application/pdf" : "image/jpeg")
            }
        }
        throw ShareUploadCore.UploadError(message: "לא נמצא קובץ PDF או תמונה בשיתוף.")
    }

    private func load(_ provider: NSItemProvider, type: UTType) async throws -> (Data, String?) {
        try await withCheckedThrowingContinuation { continuation in
            provider.loadItem(forTypeIdentifier: type.identifier) { item, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                if let url = item as? URL {
                    let accessed = url.startAccessingSecurityScopedResource()
                    defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                    if let data = try? Data(contentsOf: url) {
                        continuation.resume(returning: (data, url.lastPathComponent))
                        return
                    }
                }
                if let data = item as? Data {
                    continuation.resume(returning: (data, provider.suggestedName))
                    return
                }
                if let image = item as? UIImage, let data = image.jpegData(compressionQuality: 0.9) {
                    continuation.resume(returning: (data, provider.suggestedName ?? "shared.jpg"))
                    return
                }
                continuation.resume(throwing: ShareUploadCore.UploadError(message: "לא הצלחתי לקרוא את הקובץ ששותף."))
            }
        }
    }
}

/// מסך הבחירה — לאן הקובץ הולך.
struct ShareDecisionView: View {
    struct SharedFile {
        let data: Data
        let filename: String
        let mimeType: String
    }

    enum Phase {
        case loading
        case choose(SharedFile)
        case chooseConfirmation(SharedFile, [ShareUploadCore.DeliveryTarget])
        case uploadedToConfirmation(ShareUploadCore.DeliveryTarget)
        case working(String)
        case done(String)
        case failed(String)
    }

    let loadAttachment: () async throws -> SharedFile?
    let finish: () -> Void

    @State private var phase: Phase = .loading
    @State private var markUnpaid = false
    @State private var requiresInstallation = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            card
                .padding(16)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.001))
        .environment(\.layoutDirection, .rightToLeft)
        .task {
            do {
                if let file = try await loadAttachment() {
                    phase = .choose(file)
                } else {
                    phase = .failed("לא נמצא קובץ בשיתוף.")
                }
            } catch {
                phase = .failed(error.localizedDescription)
            }
        }
    }

    private var card: some View {
        VStack(spacing: 16) {
            HStack {
                Text("בן יעקב — ניהול")
                    .font(.headline)
                Spacer()
                Button {
                    finish()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(.secondary)
                }
                .accessibilityIdentifier("share-close")
            }

            switch phase {
            case .loading:
                ProgressView("טוען את הקובץ…")
                    .padding(.vertical, 24)

            case .choose(let file):
                VStack(spacing: 14) {
                    Label(file.filename, systemImage: file.mimeType == "application/pdf" ? "doc.fill" : "photo.fill")
                        .font(.subheadline.weight(.medium))
                        .lineLimit(1)
                        .foregroundStyle(.secondary)
                    Text("לאן לשלוח את הקובץ?")
                        .font(.title3.weight(.semibold))
                    destinationButton(
                        title: "חשבונית ספק",
                        subtitle: "פרסור ושמירה בטאב כספים",
                        icon: "doc.text.fill",
                        color: .teal
                    ) {
                        Task { await upload(kind: .invoice, file: file) }
                    }
                    Toggle(isOn: $markUnpaid) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("טרם שולמה")
                                .font(.footnote.weight(.semibold))
                            Text("תצטרף גם ל'לתשלום' בתשלומים והעברות")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .tint(.teal)
                    .padding(.horizontal, 6)
                    .accessibilityIdentifier("share-unpaid-toggle")
                    destinationButton(
                        title: "הזמנת רכש",
                        subtitle: "העלאה להזמנות בעבודה בטאב הזמנות",
                        icon: "shippingbox.fill",
                        color: .blue
                    ) {
                        Task { await upload(kind: .order, file: file) }
                    }
                    Toggle(isOn: $requiresInstallation) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("דורשת התקנה")
                                .font(.footnote.weight(.semibold))
                            Text("ייפתח תיק התקנה כשההזמנה תושלם")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .tint(.blue)
                    .padding(.horizontal, 6)
                    .accessibilityIdentifier("share-installation-toggle")
                    destinationButton(
                        title: "אישור מסירה",
                        subtitle: "צירוף תעודה חתומה לרשומה פתוחה — שליחה ללקוח רק אם תרצה",
                        icon: "signature",
                        color: .orange
                    ) {
                        Task { await loadConfirmations(file: file) }
                    }
                }

            case .chooseConfirmation(let file, let targets):
                VStack(spacing: 12) {
                    Text("לאיזו רשומת אישור מסירה לצרף?")
                        .font(.title3.weight(.semibold))
                        .accessibilityIdentifier("share-delivery-list")
                    if targets.isEmpty {
                        Text("אין רשומות אישור מסירה פתוחות.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .padding(.vertical, 16)
                    } else {
                        ScrollView {
                            VStack(spacing: 8) {
                                ForEach(targets) { target in
                                    Button {
                                        Task { await uploadToConfirmation(file: file, target: target) }
                                    } label: {
                                        HStack(spacing: 10) {
                                            Image(systemName: "shippingbox.and.arrow.backward")
                                                .foregroundStyle(.orange)
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(target.displayTitle)
                                                    .font(.subheadline.weight(.semibold))
                                                    .foregroundStyle(.primary)
                                                    .lineLimit(1)
                                                Text(target.displaySubtitle)
                                                    .font(.caption)
                                                    .foregroundStyle(.secondary)
                                            }
                                            Spacer()
                                            Image(systemName: "chevron.backward")
                                                .font(.system(size: 11, weight: .semibold))
                                                .foregroundStyle(.tertiary)
                                        }
                                        .padding(10)
                                        .background(Color(.secondarySystemBackground),
                                                    in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                        .frame(maxHeight: 280)
                    }
                }

            case .uploadedToConfirmation(let target):
                VStack(spacing: 14) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(.green)
                        .accessibilityIdentifier("share-delivery-uploaded")
                    Text("התעודה החתומה צורפה לרשומה של \(target.displayTitle).")
                        .font(.subheadline.weight(.medium))
                        .multilineTextAlignment(.center)
                    Text("אפשר לשלוח ללקוח עכשיו, או להמשיך אחר כך מהאפליקציה או מהדסקטופ.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button {
                        Task { await sendConfirmation(target: target) }
                    } label: {
                        Label("שליחה ללקוח עכשיו", systemImage: "paperplane.fill")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(.orange, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .foregroundStyle(.white)
                    }
                    .accessibilityIdentifier("share-delivery-send-now")
                    Button("סיום — אשלח מאוחר יותר") { finish() }
                        .font(.subheadline)
                        .accessibilityIdentifier("share-delivery-later")
                }
                .padding(.vertical, 8)

            case .working(let text):
                VStack(spacing: 10) {
                    ProgressView()
                    Text(text)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 24)

            case .done(let message):
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(.green)
                    Text(message)
                        .font(.subheadline.weight(.medium))
                        .multilineTextAlignment(.center)
                    Button("סגירה") { finish() }
                        .buttonStyle(.borderedProminent)
                }
                .padding(.vertical, 12)

            case .failed(let message):
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 38))
                        .foregroundStyle(.orange)
                    Text(message)
                        .font(.subheadline)
                        .multilineTextAlignment(.center)
                    Button("סגירה") { finish() }
                        .buttonStyle(.bordered)
                }
                .padding(.vertical, 12)
            }
        }
        .padding(18)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func destinationButton(title: String, subtitle: String, icon: String,
                                   color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(color)
                    .frame(width: 44, height: 44)
                    .background(color.opacity(0.14))
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.body.weight(.semibold))
                        .foregroundStyle(.primary)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.backward")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(12)
            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    private func loadConfirmations(file: SharedFile) async {
        phase = .working("טוען את אישורי המסירה הפתוחים…")
        do {
            let targets = try await ShareUploadCore.fetchOpenDeliveryConfirmations(
                baseURL: ShareUploadCore.sharedBaseURL(),
                cookieHeader: ShareUploadCore.sharedCookieHeader(),
                send: liveSender
            )
            phase = .chooseConfirmation(file, targets)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func uploadToConfirmation(file: SharedFile, target: ShareUploadCore.DeliveryTarget) async {
        phase = .working("מעלה את התעודה החתומה…")
        do {
            try await ShareUploadCore.uploadSignedDelivery(
                to: target,
                fileData: file.data, filename: file.filename, mimeType: file.mimeType,
                baseURL: ShareUploadCore.sharedBaseURL(),
                cookieHeader: ShareUploadCore.sharedCookieHeader(),
                send: liveSender
            )
            phase = .uploadedToConfirmation(target)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func sendConfirmation(target: ShareUploadCore.DeliveryTarget) async {
        phase = .working("שולח את אישור המסירה ללקוח…")
        do {
            let message = try await ShareUploadCore.sendDeliveryConfirmation(
                for: target,
                baseURL: ShareUploadCore.sharedBaseURL(),
                cookieHeader: ShareUploadCore.sharedCookieHeader(),
                send: liveSender
            )
            phase = .done(message)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    /// Session עם timeout ארוך — פרסור חשבונית מרובת-דפים (OCR + Claude לכל דף)
    /// עשוי לקחת יותר מ-60 השניות הדיפולטיות, מה שהפיל את ההעלאה עם "החיבור נכשל".
    /// תואם ל-APIClient של האפליקציה הראשית.
    private static func longTimeoutSession() -> URLSession {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 300
        configuration.timeoutIntervalForResource = 600
        return URLSession(configuration: configuration)
    }

    private var liveSender: ShareUploadCore.Sender {
        let session = Self.longTimeoutSession()
        return { request in
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw ShareUploadCore.UploadError(message: "תגובת שרת לא תקינה.")
            }
            return (data, http)
        }
    }

    private func upload(kind: ShareUploadCore.Kind, file: SharedFile) async {
        phase = .working(kind == .invoice ? "מעלה ומפרסר את החשבונית…" : "מעלה את ההזמנה…")
        do {
            let session = Self.longTimeoutSession()
            let message = try await ShareUploadCore.upload(
                kind: kind,
                fileData: file.data, filename: file.filename, mimeType: file.mimeType,
                markUnpaid: kind == .invoice && markUnpaid,
                requiresInstallation: kind == .order && requiresInstallation,
                baseURL: ShareUploadCore.sharedBaseURL(),
                cookieHeader: ShareUploadCore.sharedCookieHeader(),
                send: { request in
                    let (data, response) = try await session.data(for: request)
                    guard let http = response as? HTTPURLResponse else {
                        throw ShareUploadCore.UploadError(message: "תגובת שרת לא תקינה.")
                    }
                    return (data, http)
                }
            )
            phase = .done(message)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }
}
