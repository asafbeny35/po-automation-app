import XCTest
@testable import BenYacovManage

/// מכונת המצבים של הנעילה הביומטרית — אייפון בלבד, נעילה ברקע, כשל/הצלחה.
@MainActor
final class BiometricLockTests: XCTestCase {

    private struct FixedAuthenticator: BiometricAuthenticating {
        let result: Bool
        var isAvailable: Bool { true }
        var biometryLabel: String { "Face ID" }
        func authenticate(reason: String) async -> Bool { result }
    }

    override func setUp() {
        super.setUp()
        UserDefaults.standard.removeObject(forKey: BiometricLock.enabledDefaultsKey)
    }

    override func tearDown() {
        UserDefaults.standard.removeObject(forKey: BiometricLock.enabledDefaultsKey)
        super.tearDown()
    }

    func testDisabledNeverLocks() {
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: true)
        XCTAssertFalse(lock.isLocked, "בלי הפעלה — אין נעילה בעלייה")
        lock.lockOnBackground()
        XCTAssertFalse(lock.isLocked, "בלי הפעלה — גם רקע לא נועל")
    }

    func testEnabledLocksOnLaunchAndBackground() {
        UserDefaults.standard.set(true, forKey: BiometricLock.enabledDefaultsKey)
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: true)
        XCTAssertTrue(lock.isLocked, "כשהתכונה פעילה — נעול כבר בעלייה")

        lock.isLocked = false
        lock.lockOnBackground()
        XCTAssertTrue(lock.isLocked, "יציאה לרקע נועלת מחדש")
    }

    func testUnlockSuccessOpens() async {
        UserDefaults.standard.set(true, forKey: BiometricLock.enabledDefaultsKey)
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: true)
        await lock.unlock()
        XCTAssertFalse(lock.isLocked)
        XCTAssertFalse(lock.lastAttemptFailed)
    }

    func testUnlockFailureStaysLockedWithIndicator() async {
        UserDefaults.standard.set(true, forKey: BiometricLock.enabledDefaultsKey)
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: false), isPhone: true)
        await lock.unlock()
        XCTAssertTrue(lock.isLocked, "אימות כושל חייב להשאיר את המסך נעול")
        XCTAssertTrue(lock.lastAttemptFailed)
    }

    func testIPadNeverSupportsOrLocks() {
        UserDefaults.standard.set(true, forKey: BiometricLock.enabledDefaultsKey)
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: false)
        XCTAssertFalse(lock.isSupported, "Face ID הוא פיצ'ר אייפון בלבד — לפי ההגדרה")
        XCTAssertFalse(lock.isEnabled, "גם עם דגל שמור — באייפד לעולם לא פעיל")
        XCTAssertFalse(lock.isLocked)
        lock.lockOnBackground()
        XCTAssertFalse(lock.isLocked)
    }

    func testEnableAfterVerificationRequiresSuccess() async {
        let failing = BiometricLock(authenticator: FixedAuthenticator(result: false), isPhone: true)
        let failed = await failing.enableAfterVerification()
        XCTAssertFalse(failed)
        XCTAssertFalse(failing.isEnabled, "אימות כושל לא מדליק את התכונה")

        let succeeding = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: true)
        let succeeded = await succeeding.enableAfterVerification()
        XCTAssertTrue(succeeded)
        XCTAssertTrue(succeeding.isEnabled)
    }

    func testDisablingClearsLock() {
        UserDefaults.standard.set(true, forKey: BiometricLock.enabledDefaultsKey)
        let lock = BiometricLock(authenticator: FixedAuthenticator(result: true), isPhone: true)
        XCTAssertTrue(lock.isLocked)
        lock.isEnabled = false
        XCTAssertFalse(lock.isLocked, "כיבוי התכונה משחרר את הנעילה מיד")
    }
}
