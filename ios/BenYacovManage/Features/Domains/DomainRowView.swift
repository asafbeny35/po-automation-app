import SwiftUI

/// שורת רשימה גנרית — נבנית מה-spec של הדומיין.
struct DomainRowView: View {
    let domain: Domain
    let record: DomainRecord

    private var spec: DomainSpec { domain.spec }
    private var title: String {
        let value = record.first(of: spec.titleKeys)
        return value.isEmpty ? "ללא שם" : value
    }
    private var subtitle: String { record.first(of: spec.subtitleKeys) }
    private var amount: String {
        guard let key = spec.amountKey else { return "" }
        let raw = record[key]
        return raw.isEmpty ? "" : Formatters.currencyText(raw)
    }
    private var date: String { Formatters.dateText(record.first(of: spec.dateKeys)) }
    private var badge: (text: String, tint: Color)? {
        guard let key = spec.badgeKey else { return nil }
        return StatusBadge.styled(record[key])
    }

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            RoundedRectangle(cornerRadius: 3)
                .fill(spec.tint.color.opacity(0.85))
                .frame(width: 4, height: 40)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 8) {
                    Text(title)
                        .font(.byRowTitle)
                        .foregroundStyle(BYTheme.textPrimary)
                        .lineLimit(1)
                    if let badge {
                        StatusBadge(text: badge.text, tint: badge.tint)
                    }
                    Spacer(minLength: 0)
                }
                // שורת פרטים נוספת לתיקי התקנה: התקדמות, ביקורים ומועד הבא.
                if domain == .installationCases {
                    let progress = InstallationStatus.progressSummary(record)
                    if !progress.isEmpty {
                        Text(progress)
                            .font(.byCaption.weight(.medium))
                            .foregroundStyle(InstallationStatus.tint(record["status"]))
                            .lineLimit(1)
                            .accessibilityIdentifier("installation-progress")
                    }
                }
                HStack(spacing: 8) {
                    if !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                            .lineLimit(1)
                    }
                    Spacer(minLength: 0)
                    if !date.isEmpty {
                        Text(date)
                            .font(.byCaption)
                            .foregroundStyle(BYTheme.textSecondary)
                            .layoutPriority(1)
                    }
                }
            }
            if !amount.isEmpty {
                Text(amount)
                    .font(.byNumber(15, weight: .semibold))
                    .foregroundStyle(BYTheme.textPrimary)
                    .layoutPriority(2)
            }
            Image(systemName: "chevron.backward")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(BYTheme.textSecondary.opacity(0.5))
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 14)
        .background(BYTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .contentShape(Rectangle())
    }
}
