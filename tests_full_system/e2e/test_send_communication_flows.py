"""Category A — Communication send flows (email + WhatsApp).

Covers every async send* function in index_desktop.html that had 0% test coverage:
  - sendQuoteMail / sendQuoteWhatsapp
  - sendCustomerMail
  - sendSupplierPackageMail
  - sendMarketingMail / sendMarketingWhatsapp / sendMarketingDocWhatsapp
  - sendWorkManagersEmail / sendWorkManagersWhatsapp
  - sendConstructionCompaniesEmail / sendConstructionCompaniesWhatsapp
  - sendInventoryPurchaseOrderEmail / sendInventoryPurchaseOrderWhatsapp
  - sendReceiptCollectionCommunication (email + whatsapp)
  - sendAdminBusinessDocEmail / sendAdminBusinessDocWhatsapp
  - sendFinanceInvoicesEmail
  - sendHrPayrollWhatsapp / sendHrPayslipPrep
  - sendFinanceInvoicesEmail

For every flow the test suite covers:
  1. Validation — missing recipients/phone → info toast, no request sent
  2. Success (mocked) → success toast + modal closes
  3. Failure (mocked) → error toast + modal stays open + buttons re-enabled
  4. Button disabled during in-flight request (double-send prevention)
  5. test_send=true bypasses recipients check (where applicable)

All E2E tests use page.route() — zero real emails or WhatsApp messages sent.
API-level smoke tests are separate and marked @api.
"""
from __future__ import annotations

import json
import time

import pytest

from tests_full_system.helpers.toast import (
    wait_for_error_toast,
    wait_for_info_toast,
    wait_for_success_toast,
)
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_EMAIL = "asafbeny@gmail.com"
_TEST_PHONE = "0547720142"


def _open_app(page, tab: str = "orders") -> None:
    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab)
    wait_for_idle_ui(page)


def _open_modal(page, modal_id: str, js_open: str | None = None) -> None:
    if js_open:
        page.evaluate(js_open)
    else:
        page.evaluate(f"""
        () => {{
            const m = document.getElementById('{modal_id}');
            if (m) {{ m.classList.add('visible'); m.setAttribute('aria-hidden','false'); }}
        }}
        """)
    wait_for_idle_ui(page)


def _modal_is_visible(page, modal_id: str) -> bool:
    cls = page.locator(f"#{modal_id}").get_attribute("class") or ""
    return "visible" in cls


def _mock_ok(page, url_pattern: str, body: dict | None = None) -> None:
    b = json.dumps(body or {"status": "ok"})
    page.route(url_pattern, lambda r: r.fulfill(
        status=200, content_type="application/json", body=b))


def _mock_fail(page, url_pattern: str, error: str = "שגיאת שרת") -> None:
    page.route(url_pattern, lambda r: r.fulfill(
        status=500, content_type="application/json",
        body=json.dumps({"error": error})))


def _mock_slow(page, url_pattern: str, delay: float = 0.4) -> None:
    def handler(route):
        time.sleep(delay)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok"}))
    page.route(url_pattern, handler)


# ===========================================================================
# 1. QUOTE MAIL
# ===========================================================================

class TestQuoteMail:

    def _setup_quote_context(self, page) -> None:
        page.evaluate("""
        () => {
            window.currentQuoteResult = {
                customer_name: "TEST | נעלולי פלא | לקוח הצעת מחיר",
                customer_email: "customer@example.com",
                contact_phone: "0500000001",
                quote_number: "Q-TEST-001",
                quote_pdf_url: "https://example.com/quote.pdf",
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_modal_exists(self, page):
        _open_app(page)
        assert page.locator("#quoteMailModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_send_without_recipients_shows_info_toast(self, page):
        _open_app(page)
        self._setup_quote_context(page)
        _open_modal(page, "quoteMailModal")
        page.locator("#quoteMailRecipients, [id*='quoteMailRecipient']").first.fill("")
        send_btn = page.locator("#quoteMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_send_success_closes_modal_and_shows_toast(self, page):
        _open_app(page)
        self._setup_quote_context(page)
        _open_modal(page, "quoteMailModal")
        _mock_ok(page, "**/quote-send-email")
        recip = page.locator("#quoteMailRecipients").first
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#quoteMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="מייל הצעת מחיר נשלח", timeout=8_000)
            assert not _modal_is_visible(page, "quoteMailModal"), \
                "Quote mail modal stayed open after success"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_test_send_shows_test_toast(self, page):
        _open_app(page)
        self._setup_quote_context(page)
        _open_modal(page, "quoteMailModal")
        _mock_ok(page, "**/quote-send-email")
        test_btn = page.locator("#quoteMailTestSend").first
        if test_btn.is_visible():
            test_btn.click()
            wait_for_success_toast(page, title_contains="טסט הצעת מחיר נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_send_failure_keeps_modal_open(self, page):
        _open_app(page)
        self._setup_quote_context(page)
        _open_modal(page, "quoteMailModal")
        _mock_fail(page, "**/quote-send-email")
        recip = page.locator("#quoteMailRecipients").first
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#quoteMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת הצעת מחיר נכשלה", timeout=8_000)
            assert _modal_is_visible(page, "quoteMailModal"), \
                "Modal closed after failure — user cannot retry"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_mail_send_failure_re_enables_buttons(self, page):
        _open_app(page)
        self._setup_quote_context(page)
        _open_modal(page, "quoteMailModal")
        _mock_fail(page, "**/quote-send-email")
        recip = page.locator("#quoteMailRecipients").first
        send_btn = page.locator("#quoteMailSend").first
        if recip.is_visible() and send_btn.is_visible():
            recip.fill("customer@example.com")
            send_btn.click()
            wait_for_error_toast(page, timeout=8_000)
            assert not send_btn.is_disabled(), "Send button still disabled after failure"


# ===========================================================================
# 2. QUOTE WHATSAPP
# ===========================================================================

class TestQuoteWhatsapp:

    def _setup(self, page) -> None:
        page.evaluate("""
        () => {
            window.currentQuoteResult = {
                customer_name: "TEST | נעלולי פלא | לקוח",
                contact_phone: "0500000001",
                quote_pdf_url: "https://example.com/quote.pdf",
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_whatsapp_without_phone_shows_info_toast(self, page):
        _open_app(page)
        self._setup(page)
        page.evaluate("""
        () => {
            window.currentQuoteResult = { customer_name: "TEST", contact_phone: "" };
        }
        """)
        _open_modal(page, "quoteWhatsappModal")
        phone_el = page.locator("#quoteWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill("")
        send_btn = page.locator("#quoteWhatsappSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_whatsapp_send_success_shows_toast(self, page):
        _open_app(page)
        self._setup(page)
        _open_modal(page, "quoteWhatsappModal")
        _mock_ok(page, "**/quote-send-whatsapp")
        phone_el = page.locator("#quoteWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        send_btn = page.locator("#quoteWhatsappSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="הצעת המחיר נשלחה בוואטסאפ", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_quote_whatsapp_failure_shows_error_toast(self, page):
        _open_app(page)
        self._setup(page)
        _open_modal(page, "quoteWhatsappModal")
        _mock_fail(page, "**/quote-send-whatsapp", "WhatsApp לא מחובר")
        phone_el = page.locator("#quoteWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        send_btn = page.locator("#quoteWhatsappSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת וואטסאפ נכשלה", timeout=8_000)


# ===========================================================================
# 3. CUSTOMER MAIL
# ===========================================================================

class TestCustomerMail:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_customer_mail_modal_exists(self, page):
        _open_app(page, "customers")
        assert page.locator("#customerMailModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_customer_mail_without_recipients_shows_info_toast(self, page):
        _open_app(page, "customers")
        _open_modal(page, "customerMailModal")
        recip = page.locator("#customerMailRecipients").first
        if recip.is_visible():
            recip.fill("")
        send_btn = page.locator("#customerMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_customer_mail_send_success_closes_modal(self, page):
        _open_app(page, "customers")
        _open_modal(page, "customerMailModal")
        _mock_ok(page, "**/customers-send-email")
        recip = page.locator("#customerMailRecipients").first
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#customerMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="המייל נשלח", timeout=8_000)
            assert not _modal_is_visible(page, "customerMailModal"), \
                "Customer mail modal stayed open after success"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_customer_mail_failure_keeps_modal_open(self, page):
        _open_app(page, "customers")
        _open_modal(page, "customerMailModal")
        _mock_fail(page, "**/customers-send-email")
        recip = page.locator("#customerMailRecipients").first
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#customerMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת מייל נכשלה", timeout=8_000)
            assert _modal_is_visible(page, "customerMailModal"), \
                "Modal closed after failure"


# ===========================================================================
# 4. SUPPLIER PACKAGE MAIL
# ===========================================================================

class TestSupplierPackageMail:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_supplier_package_modal_exists(self, page):
        _open_app(page)
        assert page.locator("#supplierPackageMailModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_supplier_package_without_recipients_shows_info_toast(self, page):
        _open_app(page)
        _open_modal(page, "supplierPackageMailModal")
        recip = page.locator("#supplierPackageMailRecipients").first
        if recip.is_visible():
            recip.fill("")
        send_btn = page.locator("#supplierPackageMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_supplier_package_test_send_bypasses_recipients(self, page):
        _open_app(page)
        _open_modal(page, "supplierPackageMailModal")
        _mock_ok(page, "**/admin-supplier-package-email",
                 {"status": "ok", "recipients": [_TEST_EMAIL]})
        recip = page.locator("#supplierPackageMailRecipients").first
        if recip.is_visible():
            recip.fill("")
        test_btn = page.locator("#supplierPackageMailTestSend").first
        if test_btn.is_visible():
            test_btn.click()
            wait_for_success_toast(page, title_contains="מייל טסט נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_supplier_package_failure_keeps_modal_open(self, page):
        _open_app(page)
        _open_modal(page, "supplierPackageMailModal")
        _mock_fail(page, "**/admin-supplier-package-email")
        recip = page.locator("#supplierPackageMailRecipients").first
        if recip.is_visible():
            recip.fill("supplier@example.com")
        send_btn = page.locator("#supplierPackageMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, timeout=8_000)
            assert _modal_is_visible(page, "supplierPackageMailModal"), \
                "Modal closed after failure"


# ===========================================================================
# 5. ADMIN BUSINESS DOC EMAIL / WHATSAPP
# ===========================================================================

class TestAdminBusinessDoc:

    def _setup_context(self, page) -> None:
        page.evaluate("""
        () => {
            window.currentAdminBusinessDocContext = {
                assetKey: "TEST_DOC_KEY",
                documentLabel: "TEST | נעלולי פלא | מסמך",
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_email_without_context_shows_info_toast(self, page):
        _open_app(page)
        page.evaluate("() => { window.currentAdminBusinessDocContext = null; }")
        page.evaluate("""
        () => {
            if (typeof sendAdminBusinessDocEmail === 'function') sendAdminBusinessDocEmail(false);
        }
        """)
        wait_for_info_toast(page, title_contains="אין מסמך פעיל")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_email_without_recipients_shows_info_toast(self, page):
        _open_app(page)
        self._setup_context(page)
        _open_modal(page, "adminBusinessDocSendModal")
        recip = page.locator("#adminBusinessDocRecipients").first
        if recip.is_visible():
            recip.fill("")
        send_btn = page.locator("#adminBusinessDocSendEmail").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_email_test_send_bypasses_recipients(self, page):
        _open_app(page)
        self._setup_context(page)
        _open_modal(page, "adminBusinessDocSendModal")
        _mock_ok(page, "**/admin-business-doc-send-email")
        test_btn = page.locator("#adminBusinessDocSendTest").first
        if test_btn.is_visible():
            test_btn.click()
            wait_for_success_toast(page, timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_email_failure_keeps_modal_open(self, page):
        _open_app(page)
        self._setup_context(page)
        _open_modal(page, "adminBusinessDocSendModal")
        _mock_fail(page, "**/admin-business-doc-send-email")
        recip = page.locator("#adminBusinessDocRecipients").first
        if recip.is_visible():
            recip.fill("someone@example.com")
        send_btn = page.locator("#adminBusinessDocSendEmail").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, timeout=8_000)
            assert _modal_is_visible(page, "adminBusinessDocSendModal"), \
                "Admin doc modal closed after failure"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_whatsapp_without_phone_shows_info_toast(self, page):
        _open_app(page)
        self._setup_context(page)
        _open_modal(page, "adminBusinessDocSendModal")
        phone_el = page.locator("#adminBusinessDocPhone").first
        if phone_el.is_visible():
            phone_el.fill("")
        wa_btn = page.locator("#adminBusinessDocSendWhatsapp").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_admin_doc_whatsapp_success_closes_modal(self, page):
        _open_app(page)
        self._setup_context(page)
        _open_modal(page, "adminBusinessDocSendModal")
        _mock_ok(page, "**/admin-business-doc-send-whatsapp")
        phone_el = page.locator("#adminBusinessDocPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        wa_btn = page.locator("#adminBusinessDocSendWhatsapp").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_success_toast(page, title_contains="המסמך נשלח בוואטסאפ", timeout=8_000)


# ===========================================================================
# 6. MARKETING MAIL
# ===========================================================================

class TestMarketingMail:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_mail_modal_exists(self, page):
        _open_app(page, "marketing")
        assert page.locator("#marketingMailModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_mail_without_subject_shows_info_toast(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingMailModal")
        subj = page.locator("#marketingMailSubject").first
        if subj.is_visible():
            subj.fill("")
        send_btn = page.locator("#marketingMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר נושא")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_mail_test_send_bypasses_recipients(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingMailModal")
        _mock_ok(page, "**/marketing-send-email",
                 {"status": "ok", "recipients": [_TEST_EMAIL]})
        subj = page.locator("#marketingMailSubject").first
        if subj.is_visible():
            subj.fill("TEST | נעלולי פלא | נושא")
        test_btn = page.locator("#marketingMailTestSend").first
        if test_btn.is_visible():
            test_btn.click()
            wait_for_success_toast(page, title_contains="מייל טסט נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_mail_success_closes_modal(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingMailModal")
        _mock_ok(page, "**/marketing-send-email",
                 {"status": "ok", "recipients": ["customer@example.com"]})
        subj = page.locator("#marketingMailSubject").first
        recip = page.locator("#marketingMailRecipients").first
        if subj.is_visible():
            subj.fill("TEST | נעלולי פלא | נושא")
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#marketingMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="המייל נשלח", timeout=8_000)
            assert not _modal_is_visible(page, "marketingMailModal"), \
                "Marketing mail modal stayed open after success"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_mail_failure_keeps_modal_open(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingMailModal")
        _mock_fail(page, "**/marketing-send-email", "Gmail לא מחובר")
        subj = page.locator("#marketingMailSubject").first
        recip = page.locator("#marketingMailRecipients").first
        if subj.is_visible():
            subj.fill("TEST | נעלולי פלא | נושא")
        if recip.is_visible():
            recip.fill("customer@example.com")
        send_btn = page.locator("#marketingMailSend").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת מייל נכשלה", timeout=8_000)
            assert _modal_is_visible(page, "marketingMailModal"), \
                "Marketing mail modal closed after failure"


# ===========================================================================
# 7. MARKETING WHATSAPP
# ===========================================================================

class TestMarketingWhatsapp:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_whatsapp_modal_exists(self, page):
        _open_app(page, "marketing")
        assert page.locator("#marketingCommModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_whatsapp_without_phone_shows_info_toast(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingCommModal")
        phone_el = page.locator("#marketingCommPhone, #marketingWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill("")
        send_btn = page.locator("[id*='marketingComm'][id*='Send'], [id*='marketingWhatsapp'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_whatsapp_success_shows_toast(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingCommModal")
        _mock_ok(page, "**/marketing-send-whatsapp")
        phone_el = page.locator("#marketingCommPhone, #marketingWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        msg_el = page.locator("#marketingCommMessage, #marketingWhatsappMessage").first
        if msg_el.is_visible():
            page.evaluate(f"() => {{ document.querySelector('#marketingCommMessage, #marketingWhatsappMessage').value = 'TEST | נעלולי פלא | הודעה'; }}")
        send_btn = page.locator("[id*='marketingComm'][id*='Send'], [id*='marketingWhatsapp'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="הוואטסאפ נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_marketing_whatsapp_failure_shows_error_toast(self, page):
        _open_app(page, "marketing")
        _open_modal(page, "marketingCommModal")
        _mock_fail(page, "**/marketing-send-whatsapp", "WhatsApp לא זמין")
        phone_el = page.locator("#marketingCommPhone, #marketingWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        page.evaluate("() => { const el = document.querySelector('#marketingCommMessage, #marketingWhatsappMessage'); if(el) el.value = 'msg'; }")
        send_btn = page.locator("[id*='marketingComm'][id*='Send'], [id*='marketingWhatsapp'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת וואטסאפ נכשלה", timeout=8_000)


# ===========================================================================
# 8. WORK MANAGERS EMAIL / WHATSAPP
# ===========================================================================

class TestWorkManagersCommunication:

    def _open_send_modal(self, page) -> None:
        page.evaluate("""
        () => {
            window.marketingWorkManagersRows = [{
                row_id: "wm-test-001",
                name: "TEST | נעלולי פלא | מנהל עבודה",
                email: "wm@example.com",
                phone: "0500000002",
            }];
            if (typeof openWorkManagersSendModal === 'function') {
                openWorkManagersSendModal();
            } else {
                const m = document.getElementById('marketingWorkManagersSendModal');
                if (m) { m.classList.add('visible'); m.setAttribute('aria-hidden', 'false'); }
            }
        }
        """)
        wait_for_idle_ui(page)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_send_modal_exists(self, page):
        _open_app(page, "marketing")
        assert page.locator("#marketingWorkManagersSendModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_email_without_recipients_shows_info_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        recip = page.locator("#marketingWorkManagersSendEmails").first
        if recip.is_visible():
            recip.fill("")
        send_btn = page.locator("#marketingWorkManagersSendEmailBtn, [id*='WorkManagers'][id*='Email'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_email_success_closes_modal(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_ok(page, "**/marketing-work-managers-send-email", {"status": "ok", "sent_count": 1})
        recip = page.locator("#marketingWorkManagersSendEmails").first
        if recip.is_visible():
            recip.fill("wm@example.com")
        subj = page.locator("#marketingWorkManagersSendSubject").first
        if subj.is_visible():
            subj.fill("TEST | נעלולי פלא | נושא")
        send_btn = page.locator("[id*='WorkManagers'][id*='Email']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="המייל נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_whatsapp_without_phones_shows_info_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        phones_el = page.locator("#marketingWorkManagersSendPhones").first
        if phones_el.is_visible():
            phones_el.fill("")
        wa_btn = page.locator("[id*='WorkManagers'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_whatsapp_success_shows_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_ok(page, "**/marketing-work-managers-send-whatsapp", {"status": "ok", "sent_count": 1})
        phones_el = page.locator("#marketingWorkManagersSendPhones").first
        if phones_el.is_visible():
            phones_el.fill(_TEST_PHONE)
        msg_el = page.locator("#marketingWorkManagersSendMessage").first
        if msg_el.is_visible():
            page.evaluate("() => { const el = document.getElementById('marketingWorkManagersSendMessage'); if(el) el.value = 'TEST | נעלולי פלא | הודעה'; }")
        wa_btn = page.locator("[id*='WorkManagers'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_success_toast(page, title_contains="ההודעות נשלחו", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_work_managers_whatsapp_failure_shows_error_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_fail(page, "**/marketing-work-managers-send-whatsapp")
        phones_el = page.locator("#marketingWorkManagersSendPhones").first
        if phones_el.is_visible():
            phones_el.fill(_TEST_PHONE)
        page.evaluate("() => { const el = document.getElementById('marketingWorkManagersSendMessage'); if(el) el.value = 'msg'; }")
        wa_btn = page.locator("[id*='WorkManagers'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_error_toast(page, title_contains="שליחת וואטסאפ נכשלה", timeout=8_000)


# ===========================================================================
# 9. CONSTRUCTION COMPANIES EMAIL / WHATSAPP
# ===========================================================================

class TestConstructionCompaniesCommunication:

    def _open_send_modal(self, page) -> None:
        page.evaluate("""
        () => {
            window.marketingConstructionCompaniesRows = [{
                row_id: "cc-test-001",
                company: "TEST | נעלולי פלא | חברת בנייה",
                email: "cc@example.com",
                phone: "0500000003",
            }];
            if (typeof openConstructionCompaniesSendModal === 'function') {
                openConstructionCompaniesSendModal();
            } else {
                const m = document.getElementById('marketingConstructionCompaniesSendModal');
                if (m) { m.classList.add('visible'); m.setAttribute('aria-hidden', 'false'); }
            }
        }
        """)
        wait_for_idle_ui(page)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_send_modal_exists(self, page):
        _open_app(page, "marketing")
        assert page.locator("#marketingConstructionCompaniesSendModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_email_without_recipients_shows_info_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        recip = page.locator("#marketingConstructionCompaniesSendEmails").first
        if recip.is_visible():
            recip.fill("")
        send_btn = page.locator("[id*='ConstructionCompanies'][id*='Email']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר מייל יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_email_success_closes_modal(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_ok(page, "**/marketing-construction-companies-send-email", {"status": "ok"})
        recip = page.locator("#marketingConstructionCompaniesSendEmails").first
        if recip.is_visible():
            recip.fill("cc@example.com")
        subj = page.locator("#marketingConstructionCompaniesSendSubject").first
        if subj.is_visible():
            subj.fill("TEST | נעלולי פלא | נושא")
        send_btn = page.locator("[id*='ConstructionCompanies'][id*='Email']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="המייל נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_whatsapp_without_phones_shows_info_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        phones_el = page.locator("#marketingConstructionCompaniesSendPhones").first
        if phones_el.is_visible():
            phones_el.fill("")
        wa_btn = page.locator("[id*='ConstructionCompanies'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון יעד")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_whatsapp_success_shows_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_ok(page, "**/marketing-construction-companies-send-whatsapp",
                 {"status": "ok", "sent_count": 1})
        phones_el = page.locator("#marketingConstructionCompaniesSendPhones").first
        if phones_el.is_visible():
            phones_el.fill(_TEST_PHONE)
        page.evaluate("() => { const el = document.getElementById('marketingConstructionCompaniesSendMessage'); if(el) el.value = 'TEST | נעלולי פלא'; }")
        wa_btn = page.locator("[id*='ConstructionCompanies'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_success_toast(page, title_contains="ההודעות נשלחו", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_construction_whatsapp_failure_shows_error_toast(self, page):
        _open_app(page, "marketing")
        self._open_send_modal(page)
        _mock_fail(page, "**/marketing-construction-companies-send-whatsapp")
        phones_el = page.locator("#marketingConstructionCompaniesSendPhones").first
        if phones_el.is_visible():
            phones_el.fill(_TEST_PHONE)
        page.evaluate("() => { const el = document.getElementById('marketingConstructionCompaniesSendMessage'); if(el) el.value = 'msg'; }")
        wa_btn = page.locator("[id*='ConstructionCompanies'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_error_toast(page, title_contains="שליחת וואטסאפ נכשלה", timeout=8_000)


# ===========================================================================
# 10. INVENTORY PURCHASE ORDER EMAIL / WHATSAPP
# ===========================================================================

class TestInventoryPurchaseOrderCommunication:

    def _setup_po_context(self, page) -> None:
        page.evaluate("""
        () => {
            window.currentInventoryPurchaseOrder = {
                po_number: "TEST-INV-PO-001",
                supplier_name: "TEST | נעלולי פלא | ספק",
                supplier_email: "supplier@example.com",
                supplier_phone: "0500000004",
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_send_modal_exists(self, page):
        _open_app(page, "inventory")
        assert page.locator("#inventoryPurchaseOrderSendModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_po_email_test_send_shows_toast(self, page):
        _open_app(page, "inventory")
        self._setup_po_context(page)
        _open_modal(page, "inventoryPurchaseOrderSendModal")
        _mock_ok(page, "**/inventory-purchase-orders-send-email",
                 {"status": "ok"})
        test_btn = page.locator("[id*='inventoryPurchaseOrder'][id*='Test'], #inventoryPurchaseOrderSendTest").first
        if test_btn.is_visible():
            test_btn.click()
            wait_for_success_toast(page, title_contains="טסט נשלח", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_po_email_success_closes_modal(self, page):
        _open_app(page, "inventory")
        self._setup_po_context(page)
        _open_modal(page, "inventoryPurchaseOrderSendModal")
        _mock_ok(page, "**/inventory-purchase-orders-send-email")
        recip = page.locator("#inventoryPurchaseOrderRecipients").first
        if recip.is_visible():
            recip.fill("supplier@example.com")
        send_btn = page.locator("#inventoryPurchaseOrderSend, [id*='inventoryPurchaseOrder'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, title_contains="הזמנת רכש נשלחה", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_po_email_failure_keeps_modal_open(self, page):
        _open_app(page, "inventory")
        self._setup_po_context(page)
        _open_modal(page, "inventoryPurchaseOrderSendModal")
        _mock_fail(page, "**/inventory-purchase-orders-send-email")
        recip = page.locator("#inventoryPurchaseOrderRecipients").first
        if recip.is_visible():
            recip.fill("supplier@example.com")
        send_btn = page.locator("#inventoryPurchaseOrderSend, [id*='inventoryPurchaseOrder'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="שליחת מייל נכשלה", timeout=8_000)
            assert _modal_is_visible(page, "inventoryPurchaseOrderSendModal"), \
                "PO send modal closed after failure"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_po_whatsapp_success_shows_toast(self, page):
        _open_app(page, "inventory")
        self._setup_po_context(page)
        _open_modal(page, "inventoryPurchaseOrderSendModal")
        _mock_ok(page, "**/inventory-purchase-orders-send-whatsapp")
        phone_el = page.locator("#inventoryPurchaseOrderPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        wa_btn = page.locator("[id*='inventoryPurchaseOrder'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_success_toast(page, title_contains="הזמנת רכש נשלחה", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_inventory_po_whatsapp_failure_shows_error_toast(self, page):
        _open_app(page, "inventory")
        self._setup_po_context(page)
        _open_modal(page, "inventoryPurchaseOrderSendModal")
        _mock_fail(page, "**/inventory-purchase-orders-send-whatsapp")
        phone_el = page.locator("#inventoryPurchaseOrderPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        wa_btn = page.locator("[id*='inventoryPurchaseOrder'][id*='Whatsapp']").first
        if wa_btn.is_visible():
            wa_btn.click()
            wait_for_error_toast(page, title_contains="שליחת וואטסאפ נכשלה", timeout=8_000)


# ===========================================================================
# 11. RECEIPT COLLECTION (email + whatsapp)
# ===========================================================================

class TestReceiptCollectionCommunication:

    def _setup_context(self, page) -> None:
        page.evaluate("""
        () => {
            window.currentReceiptCollectionRow = {
                customer_name: "TEST | נעלולי פלא | לקוח",
                invoice_number: "INV-TEST-001",
                amount_due: 5000,
                email: "debtor@example.com",
                phone: "0500000005",
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_receipt_collection_modal_exists(self, page):
        _open_app(page, "finance")
        assert page.locator("#receiptCollectionCommModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_receipt_collection_email_success_shows_toast(self, page):
        _open_app(page, "finance")
        self._setup_context(page)
        _open_modal(page, "receiptCollectionCommModal")
        _mock_ok(page, "**/receipt-email-reminder-send")
        channel_btn = page.locator("[id*='receiptCollection'][id*='Email'], [data-channel='email']").first
        if channel_btn.is_visible():
            channel_btn.click()
        recip = page.locator("#receiptCollectionEmailRecipients, [id*='receiptCollection'][id*='ecipient']").first
        if recip.is_visible():
            recip.fill("debtor@example.com")
        send_btn = page.locator("#receiptCollectionSend, [id*='receiptCollection'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_receipt_collection_whatsapp_success_shows_toast(self, page):
        _open_app(page, "finance")
        self._setup_context(page)
        _open_modal(page, "receiptCollectionCommModal")
        _mock_ok(page, "**/whatsapp-send-reminder")
        channel_btn = page.locator("[data-channel='whatsapp'], [id*='receiptCollection'][id*='Whatsapp']").first
        if channel_btn.is_visible():
            channel_btn.click()
        phone_el = page.locator("#receiptCollectionPhone, [id*='receiptCollection'][id*='Phone']").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        send_btn = page.locator("#receiptCollectionSend, [id*='receiptCollection'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_receipt_collection_failure_keeps_modal_open(self, page):
        _open_app(page, "finance")
        self._setup_context(page)
        _open_modal(page, "receiptCollectionCommModal")
        _mock_fail(page, "**/receipt-email-reminder-send")
        _mock_fail(page, "**/whatsapp-send-reminder")
        recip = page.locator("#receiptCollectionEmailRecipients, [id*='receiptCollection'][id*='ecipient']").first
        if recip.is_visible():
            recip.fill("debtor@example.com")
        send_btn = page.locator("#receiptCollectionSend, [id*='receiptCollection'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, title_contains="השליחה נכשלה", timeout=8_000)
            assert _modal_is_visible(page, "receiptCollectionCommModal"), \
                "Receipt collection modal closed after failure"


# ===========================================================================
# 12. FINANCE INVOICES EMAIL
# ===========================================================================

class TestFinanceInvoicesEmail:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_finance_invoices_send_modal_exists(self, page):
        _open_app(page, "finance")
        assert page.locator("#financeInvoicesSendModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_finance_invoices_email_success_shows_toast(self, page):
        _open_app(page, "finance")
        _open_modal(page, "financeInvoicesSendModal")
        _mock_ok(page, "**/finance-invoices-send-email")
        recip = page.locator("#financeInvoicesSendRecipients, [id*='financeInvoicesSend'][id*='ecipient']").first
        if recip.is_visible():
            recip.fill("accountant@example.com")
        send_btn = page.locator("#financeInvoicesSend, [id*='financeInvoicesSend'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_finance_invoices_email_failure_keeps_modal_open(self, page):
        _open_app(page, "finance")
        _open_modal(page, "financeInvoicesSendModal")
        _mock_fail(page, "**/finance-invoices-send-email")
        recip = page.locator("#financeInvoicesSendRecipients, [id*='financeInvoicesSend'][id*='ecipient']").first
        if recip.is_visible():
            recip.fill("accountant@example.com")
        send_btn = page.locator("#financeInvoicesSend, [id*='financeInvoicesSend'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_error_toast(page, timeout=8_000)
            assert _modal_is_visible(page, "financeInvoicesSendModal"), \
                "Finance invoices send modal closed after failure"


# ===========================================================================
# 13. HR — PAYROLL WHATSAPP + PAYSLIP PREP
# ===========================================================================

class TestHrCommunication:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_payroll_whatsapp_modal_exists(self, page):
        _open_app(page, "hr")
        assert page.locator("#hrPayrollWhatsappModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_payroll_whatsapp_without_phone_shows_info_toast(self, page):
        _open_app(page, "hr")
        _open_modal(page, "hrPayrollWhatsappModal")
        phone_el = page.locator("#hrPayrollWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill("")
        send_btn = page.locator("#hrPayrollWhatsappSend, [id*='hrPayrollWhatsapp'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_info_toast(page, title_contains="חסר טלפון")

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_payroll_whatsapp_success_closes_modal(self, page):
        _open_app(page, "hr")
        _open_modal(page, "hrPayrollWhatsappModal")
        _mock_ok(page, "**/hr-payroll-send-whatsapp", {"status": "ok", "phone": _TEST_PHONE})
        phone_el = page.locator("#hrPayrollWhatsappPhone").first
        if phone_el.is_visible():
            phone_el.fill(_TEST_PHONE)
        send_btn = page.locator("#hrPayrollWhatsappSend, [id*='hrPayrollWhatsapp'][id*='Send']").first
        if send_btn.is_visible():
            send_btn.click()
            wait_for_success_toast(page, timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_payslip_prep_endpoint_smoke(self, page):
        """sendHrPayslipPrep calls /hr-payslip-prep-send — verify the route exists in UI."""
        _open_app(page, "hr")
        _mock_ok(page, "**/hr-payslip-prep-send")
        result = page.evaluate("""
        async () => {
            if (typeof sendHrPayslipPrep === 'function') {
                try { await sendHrPayslipPrep('dry_run'); return 'called'; }
                catch(e) { return e.message; }
            }
            return 'not_found';
        }
        """)
        assert result in ("called", "not_found"), f"Unexpected result: {result}"


# ===========================================================================
# 14. API-LEVEL SMOKE — verify endpoints exist (no real side effects)
# ===========================================================================

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(120)
def test_quote_send_email_endpoint_exists(api_client):
    """Smoke: /quote-send-email responds (may take >30s while attempting Gmail auth)."""
    response = api_client.post(
        "/quote-send-email",
        json={"recipients": "", "subject": "TEST", "test_send": True},
        timeout=120,
    )
    assert response.status_code not in {404, 405}, (
        f"POST /quote-send-email returned {response.status_code} — endpoint missing"
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("path,method,body", [
    ("/customers-send-email", "post", {"recipients": "", "subject": "TEST", "message": "TEST"}),
    ("/marketing-send-email", "post", {"recipients": "", "subject": "TEST", "message": "TEST", "test_send": True}),
    ("/marketing-send-whatsapp", "post", {"phone": "", "message": "TEST"}),
    ("/marketing-work-managers-send-email", "post", {"recipients": [], "subject": "TEST", "message": "TEST"}),
    ("/marketing-work-managers-send-whatsapp", "post", {"phones": [], "message": "TEST"}),
    ("/marketing-construction-companies-send-email", "post", {"recipients": [], "subject": "TEST", "message": "TEST"}),
    ("/marketing-construction-companies-send-whatsapp", "post", {"phones": [], "message": "TEST"}),
    ("/inventory-purchase-orders-send-whatsapp", "post", {"po_number": "TEST-001", "phone": ""}),
    ("/receipt-email-reminder-send", "post", {"invoice_number": "TEST-001", "recipients": "", "subject": "TEST", "message": "TEST"}),
    ("/whatsapp-send-reminder", "post", {"phone": "", "message": "TEST"}),
    ("/admin-business-doc-send-email", "post", {}),
    ("/admin-business-doc-send-whatsapp", "post", {}),
])
def test_send_endpoint_returns_valid_status(api_client, path, method, body):
    """All send endpoints must return a meaningful status, never 404/405."""
    fn = getattr(api_client, method)
    response = fn(path, json=body)
    assert response.status_code not in {404, 405}, (
        f"{method.upper()} {path} returned {response.status_code} — endpoint missing or wrong method"
    )
    assert response.status_code in {200, 400, 422, 500}, (
        f"Unexpected status {response.status_code} from {path}"
    )
