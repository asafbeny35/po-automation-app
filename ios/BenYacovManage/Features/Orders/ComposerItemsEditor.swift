import SwiftUI

/// עורך שורות הפריטים המשותף להצעת מחיר ולהזמנה ידנית — מק״ט, תיאור, כמות,
/// יחידה ומחיר יחידה לכל שורה, בדיוק כמו "הוסף מוצר" בדסקטופ.
struct ComposerItemsEditor: View {
    @Binding var items: [ComposerItem]
    var idPrefix: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(Array($items.enumerated()), id: \.element.id) { index, $item in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(index == 0 ? "פריט" : "מוצר נוסף \(index + 1)")
                            .font(.byCaption.weight(.bold))
                            .foregroundStyle(BYTheme.textSecondary)
                        Spacer()
                        if items.count > 1 {
                            Button {
                                Haptics.tap()
                                items.remove(at: index)
                            } label: {
                                Image(systemName: "trash")
                                    .foregroundStyle(BYTheme.Palette.red)
                            }
                            .accessibilityIdentifier("\(idPrefix)-item-remove-\(index)")
                        }
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("תיאור מוצר")
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(BYTheme.textSecondary)
                        TextField("", text: $item.description, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(10)
                            .background(BYTheme.insetBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            .accessibilityIdentifier("\(idPrefix)-item-description-\(index)")
                    }

                    LabeledContent("מק״ט") {
                        TextField("", text: $item.sku)
                            .multilineTextAlignment(.leading)
                            .accessibilityIdentifier("\(idPrefix)-item-sku-\(index)")
                    }

                    HStack(spacing: 12) {
                        LabeledContent("כמות") {
                            TextField("", text: $item.quantity)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("\(idPrefix)-item-quantity-\(index)")
                        }
                        LabeledContent("מחיר יח'") {
                            TextField("", text: $item.unitPrice)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.leading)
                                .accessibilityIdentifier("\(idPrefix)-item-price-\(index)")
                        }
                    }

                    Picker("יחידה", selection: $item.unit) {
                        ForEach(ComposerMath.units, id: \.self) { Text($0).tag($0) }
                    }
                    .accessibilityIdentifier("\(idPrefix)-item-unit-\(index)")

                    HStack {
                        Text("סה״כ שורה")
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                        Spacer()
                        Text(Formatters.currencyValue(item.lineTotal, detailed: true))
                            .font(.byNumber(15))
                            .accessibilityIdentifier("\(idPrefix)-item-line-total-\(index)")
                    }
                }
                if index < items.count - 1 { Divider() }
            }

            Button {
                Haptics.tap()
                items.append(ComposerItem())
            } label: {
                Label("הוסף מוצר", systemImage: "plus.circle.fill")
                    .font(.byCaption.weight(.semibold))
            }
            .accessibilityIdentifier("\(idPrefix)-item-add")
        }
    }
}

/// שורות הסיכום — ביניים, מע״מ וסה״כ — משותפות לשני הקומפוזרים.
struct ComposerTotalsView: View {
    let items: [ComposerItem]
    var idPrefix: String

    var body: some View {
        let subtotal = ComposerMath.subtotal(of: items)
        let vat = ComposerMath.vat(subtotal)
        let total = ComposerMath.total(subtotal)
        return VStack(spacing: 8) {
            totalRow("סה״כ לפני מע״מ", subtotal, id: "\(idPrefix)-subtotal")
            totalRow("מע״מ 18%", vat, id: "\(idPrefix)-vat")
            Divider()
            HStack {
                Text("סה״כ כולל מע״מ").font(.byRowTitle)
                Spacer()
                Text(Formatters.currencyValue(total, detailed: true))
                    .font(.byNumber(20))
                    .foregroundStyle(BYTheme.Palette.teal)
                    .accessibilityIdentifier("\(idPrefix)-total")
            }
        }
    }

    private func totalRow(_ label: String, _ value: Double, id: String) -> some View {
        HStack {
            Text(label).font(.byCaption).foregroundStyle(BYTheme.textSecondary)
            Spacer()
            Text(Formatters.currencyValue(value, detailed: true))
                .font(.byNumber(15))
                .accessibilityIdentifier(id)
        }
    }
}
