import SwiftUI

/// הלוואות ומשכנתאות — שיקוף סקשן "הלוואות ומשכנתאות" מטאב המנהלה בדסקטופ:
/// יתרות מחושבות להיום (בשרת), תשלום הבא, פירוט מורחב ומסמכים לצפייה.
struct LoansView: View {
    @Environment(SessionStore.self) private var session
    @State private var state: LoadState<APIClient.AdminLending> = .idle
    @State private var previewDoc: APIClient.AdminLendingDoc?
    @State private var expandedCards: Set<String> = []

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("loans-screen")
                switch state {
                case .idle, .loading:
                    ShimmerList()
                case .failed(let message):
                    ErrorStateView(message: message) {
                        Task { await load(force: true) }
                    }
                case .loaded(let lending):
                    totalsBar(lending)
                    let loans = lending.loans.filter { $0.group != "mortgage" }
                    let mortgages = lending.loans.filter { $0.group == "mortgage" }
                    if !loans.isEmpty {
                        SectionHeader(title: "הלוואות", subtitle: "יתרות ותשלומים מעודכנים להיום")
                        ForEach(loans) { card in creditCard(card) }
                    }
                    if !mortgages.isEmpty {
                        SectionHeader(title: "משכנתאות", subtitle: "מסלולים, יתרות ולוחות סילוקין")
                        ForEach(mortgages) { card in creditCard(card) }
                    }
                }
            }
            .padding(16)
        }
        .background(BYTheme.screenBackground)
        .navigationTitle("הלוואות ומשכנתאות")
        .navigationBarTitleDisplayMode(.large)
        .task { await load() }
        .refreshable { await load(force: true) }
        .sheet(item: $previewDoc) { doc in
            DocumentPreviewView(title: doc.label, path: "admin-drive-file/\(doc.key)")
        }
    }

    private func totalsBar(_ lending: APIClient.AdminLending) -> some View {
        VStack(spacing: 8) {
            if !lending.loansTotal.isEmpty {
                totalPill(label: "סה״כ הלוואות שנותר לתשלום", value: lending.loansTotal, tint: BYTheme.Palette.indigo)
            }
            if !lending.mortgagesTotal.isEmpty {
                totalPill(label: "סה״כ משכנתאות שנותר לתשלום", value: lending.mortgagesTotal, tint: BYTheme.Palette.teal)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("loans-totals")
    }

    private func totalPill(label: String, value: String, tint: Color) -> some View {
        HStack {
            Text(label)
                .font(.byCaption.weight(.semibold))
            Spacer()
            Text(value)
                .font(.byRowTitle.weight(.bold).monospacedDigit())
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(tint.opacity(0.1))
        .foregroundStyle(tint)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private func creditCard(_ card: APIClient.AdminCreditCard) -> some View {
        let isExpanded = expandedCards.contains(card.id)
        return BYCard {
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(card.kicker)
                        .font(.byCaption.weight(.semibold))
                        .foregroundStyle(BYTheme.textSecondary)
                    Text(card.title)
                        .font(.byRowTitle.weight(.bold))
                        .foregroundStyle(BYTheme.textPrimary)
                }
                VStack(spacing: 6) {
                    ForEach(card.facts) { fact in
                        HStack(alignment: .firstTextBaseline) {
                            Text(fact.label)
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                            Spacer()
                            Text(fact.value)
                                .font(.byCaption.weight(.bold).monospacedDigit())
                                .foregroundStyle(fact.label.contains("יתרה") ? BYTheme.Palette.indigo : BYTheme.textPrimary)
                                .multilineTextAlignment(.leading)
                        }
                    }
                }
                if !card.blurb.isEmpty {
                    Text(card.blurb)
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                }
                if isExpanded, !card.details.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(card.details, id: \.self) { detail in
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                Circle()
                                    .fill(BYTheme.textSecondary.opacity(0.5))
                                    .frame(width: 4, height: 4)
                                    .padding(.top, 5)
                                Text(detail)
                                    .font(.byCaption)
                                    .foregroundStyle(BYTheme.textPrimary)
                            }
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(BYTheme.screenBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
                HStack(spacing: 8) {
                    if !card.details.isEmpty {
                        Button {
                            Haptics.tap()
                            withAnimation(.snappy(duration: 0.18)) {
                                if isExpanded { expandedCards.remove(card.id) } else { expandedCards.insert(card.id) }
                            }
                        } label: {
                            Text(isExpanded ? "- סגור" : "+ קרא עוד")
                                .font(.byCaption.weight(.semibold))
                                .foregroundStyle(BYTheme.Palette.brand)
                        }
                        .accessibilityIdentifier("loan-read-more")
                    }
                    Spacer()
                    ForEach(card.docs) { doc in
                        docChip(doc)
                    }
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("loan-card")
    }

    private func docChip(_ doc: APIClient.AdminLendingDoc) -> some View {
        Button {
            Haptics.tap()
            previewDoc = doc
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "doc.text.fill")
                    .font(.system(size: 10, weight: .semibold))
                Text(doc.label)
                    .font(.byCaption.weight(.semibold))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(BYTheme.Palette.brand.opacity(0.1))
            .foregroundStyle(BYTheme.Palette.brand)
            .clipShape(Capsule())
        }
        .accessibilityIdentifier("lending-doc-open")
    }

    private func load(force: Bool = false) async {
        if !force, case .loaded = state { return }
        if !force { state = .loading }
        do {
            state = .loaded(try await session.api.adminLending())
        } catch {
            state = .failed((error as? APIError)?.message ?? "לא הצלחתי לטעון את ההלוואות והמשכנתאות.")
        }
    }
}

/// צי רכבים וכלי עבודה — שיקוף סקשן הרכבים מטאב המנהלה בדסקטופ:
/// תמונה, מספר רכב, טסט, ביטוח ומסמכים לצפייה.
struct VehiclesView: View {
    @Environment(SessionStore.self) private var session
    @State private var state: LoadState<APIClient.AdminLending> = .idle
    @State private var previewDoc: APIClient.AdminLendingDoc?

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Color.clear
                    .frame(height: 1)
                    .accessibilityElement()
                    .accessibilityIdentifier("vehicles-screen")
                switch state {
                case .idle, .loading:
                    ShimmerList()
                case .failed(let message):
                    ErrorStateView(message: message) {
                        Task { await load(force: true) }
                    }
                case .loaded(let lending):
                    if lending.vehicles.isEmpty {
                        EmptyStateView(icon: "car.fill", title: "אין רכבים להצגה")
                    } else {
                        ForEach(lending.vehicles) { vehicle in
                            vehicleCard(vehicle)
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(BYTheme.screenBackground)
        .navigationTitle("צי רכבים וכלי עבודה")
        .navigationBarTitleDisplayMode(.large)
        .task { await load() }
        .refreshable { await load(force: true) }
        .sheet(item: $previewDoc) { doc in
            DocumentPreviewView(title: doc.label, path: "admin-drive-file/\(doc.key)")
        }
    }

    private func vehicleCard(_ vehicle: APIClient.AdminVehicleCard) -> some View {
        BYCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    VehicleImage(path: vehicle.imagePath)
                        .frame(width: 86, height: 60)
                        .background(BYTheme.screenBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(vehicle.title.isEmpty ? vehicle.name : vehicle.title)
                            .font(.byRowTitle.weight(.bold))
                            .foregroundStyle(BYTheme.textPrimary)
                        if !vehicle.plate.isEmpty {
                            Text(vehicle.plate)
                                .font(.byCaption.weight(.bold).monospacedDigit())
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(BYTheme.Palette.amber.opacity(0.18))
                                .foregroundStyle(BYTheme.textPrimary)
                                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                        }
                    }
                    Spacer()
                }
                if !vehicle.subtitle.isEmpty {
                    Text(vehicle.subtitle)
                        .font(.byCaption)
                        .foregroundStyle(BYTheme.textSecondary)
                }
                VStack(spacing: 6) {
                    ForEach(vehicle.facts) { fact in
                        HStack(alignment: .firstTextBaseline) {
                            Text(fact.label)
                                .font(.byCaption)
                                .foregroundStyle(BYTheme.textSecondary)
                            Spacer()
                            Text(fact.value)
                                .font(.byCaption.weight(.bold))
                                .foregroundStyle(BYTheme.textPrimary)
                        }
                    }
                }
                if !vehicle.docs.isEmpty {
                    ChipFlowLayout(spacing: 8) {
                        ForEach(vehicle.docs) { doc in
                            Button {
                                Haptics.tap()
                                previewDoc = doc
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "doc.text.fill")
                                        .font(.system(size: 10, weight: .semibold))
                                    Text(doc.label)
                                        .font(.byCaption.weight(.semibold))
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 7)
                                .background(BYTheme.Palette.brand.opacity(0.1))
                                .foregroundStyle(BYTheme.Palette.brand)
                                .clipShape(Capsule())
                            }
                            .accessibilityIdentifier("lending-doc-open")
                        }
                    }
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("vehicle-card")
    }

    private func load(force: Bool = false) async {
        if !force, case .loaded = state { return }
        if !force { state = .loading }
        do {
            state = .loaded(try await session.api.adminLending())
        } catch {
            state = .failed((error as? APIError)?.message ?? "לא הצלחתי לטעון את צי הרכבים.")
        }
    }
}

/// תמונת רכב מהשרת — נטענת עם עוגיית ההתחברות דרך ה-API (עובד גם מול ה-mock בטסטים).
private struct VehicleImage: View {
    @Environment(SessionStore.self) private var session
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
                    .foregroundStyle(BYTheme.textSecondary.opacity(0.4))
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
