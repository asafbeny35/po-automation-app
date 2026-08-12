import SwiftUI

/// זרימות ייעודיות שנפתחות מכפתור בסרגל ה-hub.
enum HubFlow: String, Identifiable {
    case orderComposer
    case quoteComposer
    case supplierPOComposer
    case invoiceUpload

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .orderComposer: return "doc.badge.plus"
        case .quoteComposer: return "doc.text.badge.plus"
        case .supplierPOComposer: return "shippingbox.and.arrow.backward.fill"
        case .invoiceUpload: return "square.and.arrow.up.on.square.fill"
        }
    }
}

/// מסך hub עצמאי (טאב) — עוטף את תוכן ה-hub ב-NavigationStack.
struct DomainHubView: View {
    let title: String
    let tabs: [Domain]
    var creationForms: [Domain: EditFormKind] = [:]
    var flows: [Domain: HubFlow] = [:]

    var body: some View {
        NavigationStack {
            DomainHubContent(title: title, tabs: tabs, creationForms: creationForms, flows: flows)
        }
        .accessibilityIdentifier("hub-\(title)")
    }
}

/// תוכן hub — צ'יפים לבחירת דומיין + רשימה. משמש גם בתוך ניווט קיים.
struct DomainHubContent: View {
    let title: String
    let tabs: [Domain]
    var creationForms: [Domain: EditFormKind] = [:]
    var flows: [Domain: HubFlow] = [:]

    @State private var selected: Domain
    @State private var creationForm: EditFormKind?
    @State private var activeFlow: HubFlow?

    init(title: String, tabs: [Domain], creationForms: [Domain: EditFormKind] = [:], flows: [Domain: HubFlow] = [:]) {
        self.title = title
        self.tabs = tabs
        self.creationForms = creationForms
        self.flows = flows
        _selected = State(initialValue: tabs[0])
    }

    var body: some View {
        VStack(spacing: 0) {
            chips
            DomainListView(domain: selected, embedded: true)
                .id(selected)
        }
        .background(BYTheme.screenBackground)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            if let flow = flows[selected] {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Haptics.tap()
                        activeFlow = flow
                    } label: {
                        Image(systemName: flow.icon)
                            .font(.system(size: 18))
                    }
                    .accessibilityIdentifier("flow-button")
                }
            }
            if let form = creationForms[selected] {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Haptics.tap()
                        creationForm = form
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 20))
                    }
                    .accessibilityIdentifier("add-button")
                }
            }
        }
        .sheet(item: $creationForm) { form in
            RecordFormView(kind: form, domain: selected, existing: nil)
        }
        .sheet(item: $activeFlow) { flow in
            switch flow {
            case .orderComposer: OrderComposerView()
            case .quoteComposer: QuoteComposerView()
            case .supplierPOComposer: SupplierPOComposerView()
            case .invoiceUpload: InvoiceUploadView()
            }
        }
    }

    private var chips: some View {
        // פריסה עוטפת — כל הצ'יפים גלויים תמיד, בלי גלילה אופקית.
        ChipFlowLayout(spacing: 8) {
            ForEach(tabs) { domain in
                Button {
                    Haptics.tap()
                    withAnimation(.snappy(duration: 0.2)) { selected = domain }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: domain.spec.icon)
                            .font(.system(size: 12, weight: .semibold))
                        Text(domain.spec.title)
                            .font(.byCaption.weight(.semibold))
                    }
                    .padding(.horizontal, 13)
                    .padding(.vertical, 8)
                    .background(selected == domain ? domain.spec.tint.color : BYTheme.cardBackground)
                    .foregroundStyle(selected == domain ? .white : BYTheme.textSecondary)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule().strokeBorder(selected == domain ? .clear : BYTheme.separator, lineWidth: 1)
                    )
                }
                .accessibilityIdentifier("chip-\(domain.rawValue)")
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}

/// פריסת flow פשוטה — שוברת שורה כשנגמר המקום, מיושרת לפי כיוון הפריסה (RTL).
struct ChipFlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        let width = proposal.width ?? rows.map(\.width).max() ?? 0
        let height = rows.reduce(0) { $0 + $1.height } + spacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = computeRows(proposal: ProposedViewSize(width: bounds.width, height: nil), subviews: subviews)
        var y = bounds.minY
        for row in rows {
            var x = bounds.minX
            for index in row.indices {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(
                    at: CGPoint(x: x, y: y + (row.height - size.height) / 2),
                    proposal: ProposedViewSize(size)
                )
                x += size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row {
        var indices: [Int] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func computeRows(proposal: ProposedViewSize, subviews: Subviews) -> [Row] {
        let maxWidth = proposal.width ?? .infinity
        var rows: [Row] = []
        var current = Row()
        for (index, subview) in subviews.enumerated() {
            let size = subview.sizeThatFits(.unspecified)
            let needed = current.indices.isEmpty ? size.width : current.width + spacing + size.width
            if needed > maxWidth && !current.indices.isEmpty {
                rows.append(current)
                current = Row()
            }
            current.width = current.indices.isEmpty ? size.width : current.width + spacing + size.width
            current.height = max(current.height, size.height)
            current.indices.append(index)
        }
        if !current.indices.isEmpty {
            rows.append(current)
        }
        return rows
    }
}
