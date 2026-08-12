import SwiftUI
import PDFKit

/// צפיין מסמכים נייטיבי — PDF דרך PDFKit ותמונות דרך Image.
struct DocumentPreviewView: View {
    @Environment(SessionStore.self) private var session
    @Environment(\.dismiss) private var dismiss

    let title: String
    /// נתיב יחסי בשרת להורדת הקובץ (עם עוגיית ההתחברות).
    let path: String

    @State private var data: Data?
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Group {
                if let data {
                    if let image = UIImage(data: data) {
                        ScrollView([.horizontal, .vertical]) {
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFit()
                                .frame(maxWidth: .infinity)
                        }
                        .accessibilityIdentifier("document-image")
                    } else if PDFDocument(data: data) != nil {
                        PDFKitView(data: data)
                            .accessibilityIdentifier("document-pdf")
                    } else {
                        EmptyStateView(icon: "doc.questionmark", title: "פורמט קובץ לא נתמך לתצוגה")
                    }
                } else if let errorMessage {
                    ErrorStateView(message: errorMessage) {
                        Task { await load() }
                    }
                } else {
                    ProgressView("טוען מסמך…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .background(BYTheme.screenBackground)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("document-close")
                }
                if let data {
                    ToolbarItem(placement: .primaryAction) {
                        ShareLink(item: sharedFileURL(data: data)) {
                            Image(systemName: "square.and.arrow.up")
                        }
                        .accessibilityIdentifier("document-share")
                    }
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task { await load() }
        .accessibilityIdentifier("document-preview")
    }

    private func load() async {
        errorMessage = nil
        do {
            data = try await session.api.fetchDocumentData(path)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "לא הצלחתי לטעון את המסמך."
        }
    }

    private func sharedFileURL(data: Data) -> URL {
        let isPDF = PDFDocument(data: data) != nil
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("\(title).\(isPDF ? "pdf" : "png")")
        try? data.write(to: url)
        return url
    }
}

/// עטיפה נייטיבית ל-PDFKit.
struct PDFKitView: UIViewRepresentable {
    let data: Data

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.document = PDFDocument(data: data)
        view.backgroundColor = .clear
        return view
    }

    func updateUIView(_ uiView: PDFView, context: Context) {
        if uiView.document == nil {
            uiView.document = PDFDocument(data: data)
        }
    }
}
