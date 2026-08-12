import XCTest
import SwiftUI
@testable import BenYacovManage

/// בדיקות ויזואליות — רינדור מסכי מפתח לתמונה והשוואה לתמונת ייחוס.
/// תופס רגרסיות פריסה/צבע/RTL שטסטים פונקציונליים לא רואים.
///
/// הקלטת ייחוסים מחדש (אחרי שינוי עיצוב מכוון):
/// `TEST_RUNNER_BY_RECORD_SNAPSHOTS=1 xcodebuild test -only-testing:BenYacovManageTests/SnapshotTests`
/// ואז להעתיק את התמונות מה-Documents של האפליקציה לתיקיית Snapshots ולהריץ שוב.
@MainActor
final class SnapshotTests: XCTestCase {
    private let canvas = CGSize(width: 393, height: 852)

    override func setUpWithError() throws {
        // תמונות הייחוס מוקלטות על סימולטור — במכשיר פיזי הרינדור שונה (קנה מידה, מסך).
        #if !targetEnvironment(simulator)
        throw XCTSkip("בדיקות snapshot רצות רק על סימולטור")
        #endif
    }
    private var isRecording: Bool {
        ProcessInfo.processInfo.environment["BY_RECORD_SNAPSHOTS"] == "1"
            // הסימולטור לא תמיד מקבל את משתני TEST_RUNNER_ — דגל קובץ כגיבוי.
            || FileManager.default.fileExists(atPath: "/tmp/by_record_snapshots")
    }

    // MARK: - תשתית

    private func makeSession(authenticated: Bool = true) async -> SessionStore {
        let client = APIClient(
            baseURL: URL(string: "https://mock.test")!,
            transport: MockTransport(startAuthenticated: authenticated)
        )
        let session = SessionStore(api: client)
        await session.start()
        return session
    }

    private func render(_ view: some View, dark: Bool) -> UIImage {
        let host = UIHostingController(
            rootView: AnyView(
                view
                    .environment(\.layoutDirection, .rightToLeft)
                    .environment(\.locale, Formatters.hebrewLocale)
                    .tint(BYTheme.Palette.brand)
            )
        )
        // בלי חיבור ל-scene החלון לא מצייר בסביבת טסטים.
        let scene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first
        let window: UIWindow
        if let scene {
            window = UIWindow(windowScene: scene)
        } else {
            window = UIWindow(frame: CGRect(origin: .zero, size: canvas))
        }
        window.frame = CGRect(origin: .zero, size: canvas)
        window.overrideUserInterfaceStyle = dark ? .dark : .light
        window.rootViewController = host
        window.isHidden = false
        host.view.frame = window.bounds
        host.view.layoutIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.6))

        let renderer = UIGraphicsImageRenderer(bounds: window.bounds)
        let image = renderer.image { context in
            window.layer.render(in: context.cgContext)
        }
        window.isHidden = true
        return image
    }

    /// השוואה סובלנית: מותר עד 1% פיקסלים שונים (אנטי-אליאסינג), מעבר לזה = רגרסיה.
    private func assertSnapshot(_ view: some View, named name: String, dark: Bool = false,
                                file: StaticString = #filePath, line: UInt = #line) {
        // ייחוסים נפרדים לכל idiom — פריסת אייפד שונה בכוונה, לא רגרסיה.
        let idiomSuffix = UIDevice.current.userInterfaceIdiom == .pad ? "_ipad" : ""
        let fullName = (dark ? "\(name)_dark" : name) + idiomSuffix
        let image = render(view, dark: dark)
        guard let pngData = image.pngData() else {
            XCTFail("רינדור \(fullName) נכשל", file: file, line: line)
            return
        }

        if isRecording {
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let target = documents.appendingPathComponent("Snapshots", isDirectory: true)
            try? FileManager.default.createDirectory(at: target, withIntermediateDirectories: true)
            try? pngData.write(to: target.appendingPathComponent("\(fullName).png"))
            print("SNAPSHOT-RECORDED: \(target.appendingPathComponent("\(fullName).png").path)")
            return
        }

        guard let referenceURL = Bundle(for: SnapshotTests.self)
            .url(forResource: fullName, withExtension: "png", subdirectory: "Snapshots")
            ?? Bundle(for: SnapshotTests.self).url(forResource: fullName, withExtension: "png"),
              let reference = UIImage(contentsOfFile: referenceURL.path) else {
            XCTFail("חסרה תמונת ייחוס \(fullName).png — יש להקליט עם BY_RECORD_SNAPSHOTS=1",
                    file: file, line: line)
            return
        }

        let diff = pixelDifferenceRatio(image, reference)
        XCTAssertLessThanOrEqual(
            diff, 0.01,
            "\(fullName): \(String(format: "%.2f", diff * 100))% מהפיקסלים שונים מתמונת הייחוס — רגרסיה ויזואלית",
            file: file, line: line
        )
    }

    private func pixelData(_ image: UIImage) -> [UInt8]? {
        guard let cgImage = image.cgImage else { return nil }
        let width = 128, height = 277
        var data = [UInt8](repeating: 0, count: width * height * 4)
        guard let context = CGContext(
            data: &data, width: width, height: height, bitsPerComponent: 8,
            bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }
        context.interpolationQuality = .medium
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        return data
    }

    private func pixelDifferenceRatio(_ left: UIImage, _ right: UIImage) -> Double {
        guard let a = pixelData(left), let b = pixelData(right), a.count == b.count else { return 1 }
        var different = 0
        let pixels = a.count / 4
        for index in stride(from: 0, to: a.count, by: 4) {
            let delta = abs(Int(a[index]) - Int(b[index]))
                + abs(Int(a[index + 1]) - Int(b[index + 1]))
                + abs(Int(a[index + 2]) - Int(b[index + 2]))
            if delta > 24 { different += 1 }
        }
        return Double(different) / Double(pixels)
    }

    // MARK: - המסכים

    func testLoginScreenSnapshot() async {
        let session = await makeSession(authenticated: false)
        assertSnapshot(LoginView().environment(session), named: "login")
        assertSnapshot(LoginView().environment(session), named: "login", dark: true)
    }

    func testCustomersListSnapshot() async {
        let session = await makeSession()
        await session.loadDomain(.customers)
        let view = DomainListView(domain: .customers).environment(session)
        assertSnapshot(view, named: "customers_list")
        assertSnapshot(view, named: "customers_list", dark: true)
    }

    func testCustomerDetailSnapshot() async throws {
        let session = await makeSession()
        await session.loadDomain(.customers)
        let record = try XCTUnwrap(session.records(for: .customers).first)
        let view = RecordDetailView(domain: .customers, recordID: record.id).environment(session)
        assertSnapshot(view, named: "customer_detail")
        assertSnapshot(view, named: "customer_detail", dark: true)
    }

    func testPaymentsListSnapshot() async {
        let session = await makeSession()
        await session.loadDomain(.paymentsTransfer)
        let view = DomainListView(domain: .paymentsTransfer).environment(session)
        assertSnapshot(view, named: "payments_list")
        assertSnapshot(view, named: "payments_list", dark: true)
    }

    func testOrderComposerSnapshot() async {
        let session = await makeSession()
        assertSnapshot(OrderComposerView().environment(session), named: "order_composer")
        assertSnapshot(OrderComposerView().environment(session), named: "order_composer", dark: true)
    }

    func testMoreScreenSnapshot() async {
        let session = await makeSession()
        // BiometricLock נדרש בסביבה; מזריקים מופע ללא-אייפון כדי שהטוגל לא ישתנה בין מכשירים.
        let lock = BiometricLock(authenticator: UITestBiometricAuthenticator(), isPhone: false)
        assertSnapshot(MoreHubView().environment(session).environment(lock), named: "more_screen")
        assertSnapshot(MoreHubView().environment(session).environment(lock), named: "more_screen", dark: true)
    }
}
