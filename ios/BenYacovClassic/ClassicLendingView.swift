import SwiftUI
import PDFKit

/// הלוואות ומשכנתאות בקלאסי — אותו endpoint ואותם נתונים כמו האפליקציה הראשית:
/// יתרות מחושבות להיום בשרת, תשלום הבא, פירוט מורחב ומסמכים לצפייה.
struct ClassicLoansView: View {
    @EnvironmentObject private var session: ClassicSession
    @State private var lending: APIClient.AdminLending?
    @State private var errorMessage: String?
    @State private var previewDoc: APIClient.AdminLendingDoc?
    @State private var expandedCards: Set<String> = []

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("classic-loans-screen")
                if let lending {
                    totalsBar(lending)
                    let loans = lending.loans.filter { $0.group != "mortgage" }
                    let mortgages = lending.loans.filter { $0.group == "mortgage" }
                    if !loans.isEmpty {
                        sectionTitle("הלוואות")
                        ForEach(loans) { card in creditCard(card) }
                    }
                    if !mortgages.isEmpty {
                        sectionTitle("משכנתאות")
                        ForEach(mortgages) { card in creditCard(card) }
                    }
                } else if let errorMessage {
                    VStack(spacing: 10) {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Button("נסה שוב") { Task { await load(force: true) } }
                            .buttonStyle(.borderedProminent)
                    }
                    .padding(.top, 30)
                } else {
                    ProgressView().padding(.top, 40)
                }
            }
            .padding(16)
        }
        .background(ClassicTheme.screen)
        .navigationTitle("הלוואות ומשכנתאות")
        .task { await load() }
        .refreshable { await load(force: true) }
        .sheet(item: $previewDoc) { doc in
            ClassicDocumentViewer(title: doc.label, path: "admin-drive-file/\(doc.key)")
        }
    }

    private func sectionTitle(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.headline)
            Spacer()
        }
        .padding(.top, 4)
    }

    private func totalsBar(_ lending: APIClient.AdminLending) -> some View {
        VStack(spacing: 8) {
            if !lending.loansTotal.isEmpty {
                totalPill(label: "סה״כ הלוואות שנותר לתשלום", value: lending.loansTotal, tint: .indigo)
            }
            if !lending.mortgagesTotal.isEmpty {
                totalPill(label: "סה״כ משכנתאות שנותר לתשלום", value: lending.mortgagesTotal, tint: .teal)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("classic-loans-totals")
    }

    private func totalPill(label: String, value: String, tint: Color) -> some View {
        HStack {
            Text(label).font(.caption.weight(.semibold))
            Spacer()
            Text(value).font(.subheadline.weight(.bold).monospacedDigit())
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
        .foregroundColor(tint)
    }

    private func creditCard(_ card: APIClient.AdminCreditCard) -> some View {
        let isExpanded = expandedCards.contains(card.id)
        return VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(card.kicker)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.secondary)
                Text(card.title)
                    .font(.headline)
            }
            VStack(spacing: 6) {
                ForEach(card.facts) { fact in
                    HStack(alignment: .firstTextBaseline) {
                        Text(fact.label)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(fact.value)
                            .font(.caption.weight(.bold).monospacedDigit())
                            .foregroundColor(fact.label.contains("יתרה") ? .indigo : .primary)
                    }
                }
            }
            if !card.blurb.isEmpty {
                Text(card.blurb)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            if isExpanded, !card.details.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(card.details, id: \.self) { detail in
                        Text("• \(detail)")
                            .font(.caption)
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(ClassicTheme.screen, in: RoundedRectangle(cornerRadius: 10))
            }
            HStack(spacing: 8) {
                if !card.details.isEmpty {
                    Button {
                        withAnimation(.easeOut(duration: 0.15)) {
                            if isExpanded { expandedCards.remove(card.id) } else { expandedCards.insert(card.id) }
                        }
                    } label: {
                        Text(isExpanded ? "- סגור" : "+ קרא עוד")
                            .font(.caption.weight(.semibold))
                            .foregroundColor(ClassicTheme.brand)
                    }
                    .accessibilityIdentifier("classic-loan-read-more")
                }
                Spacer()
                ForEach(card.docs) { doc in
                    ClassicDocChip(doc: doc) { previewDoc = doc }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("classic-loan-card")
    }

    private func load(force: Bool = false) async {
        if !force, lending != nil { return }
        errorMessage = nil
        do {
            lending = try await session.api.adminLending()
        } catch {
            if lending == nil {
                errorMessage = (error as? APIError)?.message ?? "לא הצלחתי לטעון את ההלוואות והמשכנתאות."
            }
        }
    }
}

/// צי רכבים וכלי עבודה בקלאסי.
struct ClassicVehiclesView: View {
    @EnvironmentObject private var session: ClassicSession
    @State private var lending: APIClient.AdminLending?
    @State private var errorMessage: String?
    @State private var previewDoc: APIClient.AdminLendingDoc?

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("classic-vehicles-screen")
                if let lending {
                    ForEach(lending.vehicles) { vehicle in vehicleCard(vehicle) }
                } else if let errorMessage {
                    VStack(spacing: 10) {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Button("נסה שוב") { Task { await load(force: true) } }
                            .buttonStyle(.borderedProminent)
                    }
                    .padding(.top, 30)
                } else {
                    ProgressView().padding(.top, 40)
                }
            }
            .padding(16)
        }
        .background(ClassicTheme.screen)
        .navigationTitle("צי רכבים וכלי עבודה")
        .task { await load() }
        .refreshable { await load(force: true) }
        .sheet(item: $previewDoc) { doc in
            ClassicDocumentViewer(title: doc.label, path: "admin-drive-file/\(doc.key)")
        }
    }

    private func vehicleCard(_ vehicle: APIClient.AdminVehicleCard) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                ClassicVehicleImage(path: vehicle.imagePath)
                    .frame(width: 96, height: 64)
                    .background(ClassicTheme.screen, in: RoundedRectangle(cornerRadius: 10))
                VStack(alignment: .leading, spacing: 3) {
                    Text(vehicle.title.isEmpty ? vehicle.name : vehicle.title)
                        .font(.headline)
                    if !vehicle.plate.isEmpty {
                        Text(vehicle.plate)
                            .font(.caption.weight(.bold).monospacedDigit())
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(Color.yellow.opacity(0.25), in: RoundedRectangle(cornerRadius: 6))
                    }
                }
                Spacer()
            }
            if !vehicle.subtitle.isEmpty {
                Text(vehicle.subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            VStack(spacing: 6) {
                ForEach(vehicle.facts) { fact in
                    HStack(alignment: .firstTextBaseline) {
                        Text(fact.label)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(fact.value)
                            .font(.caption.weight(.bold))
                    }
                }
            }
            if !vehicle.docs.isEmpty {
                HStack(spacing: 8) {
                    ForEach(vehicle.docs) { doc in
                        ClassicDocChip(doc: doc) { previewDoc = doc }
                    }
                    Spacer()
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ClassicTheme.card, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("classic-vehicle-card")
    }

    private func load(force: Bool = false) async {
        if !force, lending != nil { return }
        errorMessage = nil
        do {
            lending = try await session.api.adminLending()
        } catch {
            if lending == nil {
                errorMessage = (error as? APIError)?.message ?? "לא הצלחתי לטעון את צי הרכבים."
            }
        }
    }
}

/// צ'יפ מסמך משותף לשני המסכים.
private struct ClassicDocChip: View {
    let doc: APIClient.AdminLendingDoc
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: "doc.text.fill")
                    .font(.system(size: 10, weight: .semibold))
                Text(doc.label)
                    .font(.caption.weight(.semibold))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(ClassicTheme.brand.opacity(0.12), in: Capsule())
            .foregroundColor(ClassicTheme.brand)
        }
        .accessibilityIdentifier("classic-lending-doc-open")
    }
}

/// תמונת רכב — נטענת עם עוגיית ההתחברות דרך ה-API (עובד גם מול ה-mock).
private struct ClassicVehicleImage: View {
    @EnvironmentObject private var session: ClassicSession
    let path: String

    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
            } else {
                Image(systemName: "car.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.secondary.opacity(0.4))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task {
            guard image == nil, !path.isEmpty else { return }
            if let data = try? await session.api.fetchDocumentData(path) {
                image = UIImage(data: data)
            }
        }
    }
}

/// צפיין מסמכים תואם iOS 16 — PDF דרך PDFKit ותמונות דרך Image.
struct ClassicDocumentViewer: View {
    @EnvironmentObject private var session: ClassicSession
    @Environment(\.dismiss) private var dismiss

    let title: String
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
                    } else if PDFDocument(data: data) != nil {
                        ClassicPDFView(data: data)
                            .accessibilityIdentifier("classic-document-pdf")
                    } else {
                        Text("פורמט קובץ לא נתמך לתצוגה")
                            .foregroundColor(.secondary)
                    }
                } else if let errorMessage {
                    VStack(spacing: 10) {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Button("נסה שוב") { Task { await load() } }
                            .buttonStyle(.borderedProminent)
                    }
                } else {
                    ProgressView("טוען מסמך…")
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(ClassicTheme.screen)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("סגירה") { dismiss() }
                        .accessibilityIdentifier("classic-document-close")
                }
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .task { await load() }
    }

    private func load() async {
        errorMessage = nil
        do {
            data = try await session.api.fetchDocumentData(path)
        } catch {
            errorMessage = (error as? APIError)?.message ?? "לא הצלחתי לטעון את המסמך."
        }
    }
}

/// עטיפה נייטיבית ל-PDFKit (עותק לקלאסי — הראשית לא משותפת).
private struct ClassicPDFView: UIViewRepresentable {
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
