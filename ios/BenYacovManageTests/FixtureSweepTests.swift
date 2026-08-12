import XCTest
@testable import BenYacovManage

/// סריקת עומק על כל שורות ה-fixtures בכל דומיין — כל מה שהרשימה והפירוט מציגים
/// חייב להתפרסר ולהתפרמט בלי ליפול ובלי להיעלם.
final class FixtureSweepTests: XCTestCase {
    private var client: APIClient!

    override func setUp() {
        super.setUp()
        client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: true)
        )
    }

    func testEveryFixtureRowRendersListFields() async throws {
        for domain in Domain.allCases {
            let records = try await client.domainRows(domain)
            XCTAssertFalse(records.isEmpty, "\(domain.rawValue): fixture ריק")
            let spec = domain.spec

            for record in records {
                // כותרת — חובה לכל שורה.
                XCTAssertFalse(record.first(of: spec.titleKeys).isEmpty,
                               "\(domain.rawValue): שורה בלי כותרת (\(record.id))")
                // תג סטטוס — ערך לא ריק חייב לקבל עיצוב.
                if let badgeKey = spec.badgeKey {
                    let value = record[badgeKey]
                    if !value.isEmpty {
                        XCTAssertNotNil(StatusBadge.styled(value),
                                        "\(domain.rawValue): ערך תג לא מעוצב '\(value)'")
                    }
                }
                // סכום — ערך לא ריק מתפרמט למטבע או נשאר קריא.
                if let amountKey = spec.amountKey {
                    let raw = record[amountKey]
                    if !raw.isEmpty {
                        XCTAssertFalse(Formatters.currencyText(raw).isEmpty,
                                       "\(domain.rawValue): סכום נעלם '\(raw)'")
                    }
                }
                // תאריך — ערך לא ריק לא נעלם בפורמט.
                let rawDate = record.first(of: spec.dateKeys)
                if !rawDate.isEmpty {
                    XCTAssertFalse(Formatters.dateText(rawDate).isEmpty,
                                   "\(domain.rawValue): תאריך נעלם '\(rawDate)'")
                }
            }

            // מזהים יציבים וייחודיים בתוך הדומיין (בסיס ה-List וה-detail lookup).
            let ids = records.map(\.id)
            XCTAssertEqual(ids.count, Set(ids).count,
                           "\(domain.rawValue): מזהי שורות כפולים")
        }
    }

    func testDetailFieldsHaveHebrewLabels() async throws {
        // כל מפתח שמוגדר במסך פירוט חייב תווית עברית אמיתית (לא fallback באנגלית).
        for domain in Domain.allCases {
            for key in domain.spec.detailKeys {
                let label = FieldLabels.label(for: key)
                XCTAssertFalse(label.contains("_"),
                               "\(domain.rawValue): למפתח \(key) אין תווית עברית")
            }
        }
    }

    // MARK: - ולידציית multipart אמיתית

    func testMultipartEncodingIsParseable() async throws {
        // ההעלאה מצליחה רק אם ה-mock הצליח לפרסר את הקובץ מהגוף.
        let drafts = try await client.uploadInvoices(files: [("real.pdf", Data("%PDF-1.4 test".utf8))])
        XCTAssertFalse(drafts.isEmpty)
    }

    func testMultipartWithoutFileIsRejected() async throws {
        do {
            _ = try await client.uploadInvoices(files: [])
            XCTFail("העלאה בלי קבצים הייתה אמורה להידחות")
        } catch let error as APIError {
            XCTAssertEqual(error.statusCode, 400)
        }
    }

    func testProcessMultipartCarriesTheFile() async throws {
        let record = try await client.processPurchaseOrder(
            pdf: Data("%PDF-1.4 po".utf8), filename: "po.pdf", mode: "sandbox"
        )
        XCTAssertFalse(record["po_number"].isEmpty)
    }
}
