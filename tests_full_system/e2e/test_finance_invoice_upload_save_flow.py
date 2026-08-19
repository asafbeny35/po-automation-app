"""E2E tests for the finance invoice upload → parse → modal → save flow.

This is the exact flow that exposed the real-world bug:
  1. User uploads a PDF/image to the finance tab drop zone
  2. POST /finance-invoices-upload is called → server parses and returns drafts
  3. #financeInvoiceParseModal opens with parsed fields (all disabled by default)
  4. User enables a field checkbox → field becomes editable → user edits it
  5. User clicks 'שמירה לטבלה' (#financeInvoiceParseSave)
  6. POST /finance-invoices-save is called with the (possibly edited) row
  7. On success: toast.success + row appears in table
  8. On failure: toast.error with the error message — NOT silence

None of the previous API-level or CRUD tests covered this end-to-end path.
They tested /finance-invoices-save in isolation, not the modal + save combination.
"""
from __future__ import annotations

import json

import pytest

from tests_full_system.helpers.toast import (
    wait_for_error_toast,
    wait_for_success_toast,
    wait_for_info_toast,
)
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell


# Minimal parsed draft that the upload endpoint would return
_MOCK_DRAFT = {
    "invoice_date": "25/06/2026",
    "supplier_name": "TEST | נעלולי פלא | ספק פרסור",
    "service_or_product": "TEST | נעלולי פלא | שירות",
    "subtotal": "1000.00",
    "vat": "170.00",
    "total": "1170.00",
    "source_file_name": "test_invoice.pdf",
    "create_payable_row": "",
}


def _open_finance_tab(page) -> None:
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)


def _mock_upload_endpoint(page, drafts: list | None = None) -> None:
    """Mock /finance-invoices-upload to return a deterministic parsed draft."""
    if drafts is None:
        drafts = [_MOCK_DRAFT.copy()]

    def handler(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "status": "ok",
                "message": "הקובץ פורסר ונפתח לבדיקה לפני שמירה.",
                "drafts": drafts,
            }),
        )

    page.route("**/finance-invoices-upload", handler)


def _mock_save_endpoint(page, *, fail: bool = False, error_message: str = "שגיאת שמירה מדומה") -> None:
    """Mock /finance-invoices-save to return success or failure."""
    def handler(route):
        if fail:
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": error_message}),
            )
        else:
            body = json.loads(route.request.post_data or "{}")
            row = body.get("row", {})
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "ok", "row": row}),
            )

    page.route("**/finance-invoices-save", handler)


def _trigger_upload_via_js(page) -> None:
    """Bypass the file picker by invoking the upload function directly with a mock file."""
    page.evaluate("""
    async () => {
        // Create a minimal fake File object
        const blob = new Blob(['%PDF-1.4 fake'], { type: 'application/pdf' });
        const file = new File([blob], 'test_invoice.pdf', { type: 'application/pdf' });
        const dt = new DataTransfer();
        dt.items.add(file);

        // Trigger the drop zone's file handler
        const dropZone = document.getElementById('financeInvoicesDropZone');
        if (!dropZone) return 'no dropzone';

        // Try to trigger the change event on the hidden file input if present
        const fileInput = document.getElementById('financeInvoicesFileInput')
            || document.querySelector('#financeInvoicesDropZone input[type=file]');
        if (fileInput) {
            Object.defineProperty(fileInput, 'files', { value: dt.files });
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            return 'triggered via input';
        }

        // Fallback: dispatch drop event on the zone
        const dropEvent = new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            dataTransfer: dt,
        });
        dropZone.dispatchEvent(dropEvent);
        return 'triggered via drop';
    }
    """)
    wait_for_idle_ui(page)


# ===========================================================================
# MODAL SURFACE — opens after upload
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_modal_opens_after_upload(page):
    """After upload triggers and server returns a draft, the parse modal must open."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_modal_shows_supplier_name(page):
    """The modal must render the supplier name from the parsed draft."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # The supplier_name field must appear in the modal
    supplier_input = page.locator('[data-finance-parse-input="supplier_name"]')
    supplier_input.wait_for(state="attached", timeout=5_000)
    value = supplier_input.input_value()
    assert "TEST | נעלולי פלא | ספק פרסור" in value, (
        f"supplier_name field not populated from draft. Got: '{value}'"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_modal_fields_disabled_by_default(page):
    """All parse modal fields must be disabled by default — editing requires checking the checkbox."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    fields = ["invoice_date", "supplier_name", "service_or_product", "subtotal", "vat", "total"]
    for field in fields:
        input_el = page.locator(f'[data-finance-parse-input="{field}"]')
        if input_el.count() > 0:
            assert input_el.is_disabled(), (
                f"Field '{field}' should be disabled by default in the parse modal. "
                "Users must explicitly enable editing via the checkbox."
            )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_modal_has_save_and_cancel_buttons(page):
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    wait_for_visible(page, "#financeInvoiceParseSave")
    wait_for_visible(page, "#financeInvoiceParseCancel")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_modal_cancel_closes_modal(page):
    """Clicking 'ביטול' must close the modal."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    page.locator("#financeInvoiceParseCancel").click()
    wait_for_idle_ui(page)

    modal = page.locator("#financeInvoiceParseModal")
    has_visible_class = "visible" in (modal.get_attribute("class") or "")
    assert not has_visible_class, "Parse modal still visible after clicking ביטול"


# ===========================================================================
# ENABLING MANUAL EDIT — checkbox toggles field
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_field_becomes_editable_after_checkbox(page):
    """Checking 'עריכה ידנית' for a field must enable that input."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # Enable manual edit for supplier_name
    toggle = page.locator('[data-finance-parse-toggle="supplier_name"]')
    toggle.wait_for(state="attached", timeout=5_000)
    toggle.check()
    wait_for_idle_ui(page)

    input_el = page.locator('[data-finance-parse-input="supplier_name"]')
    assert not input_el.is_disabled(), (
        "supplier_name field is still disabled after checking 'עריכה ידנית'"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_parse_field_edit_updates_value(page):
    """After enabling a field, typing in it updates its value."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    toggle = page.locator('[data-finance-parse-toggle="supplier_name"]')
    toggle.check()
    wait_for_idle_ui(page)

    input_el = page.locator('[data-finance-parse-input="supplier_name"]')
    input_el.fill("TEST | נעלולי פלא | ספק שונה ידנית")

    value = input_el.input_value()
    assert "ספק שונה ידנית" in value


# ===========================================================================
# THE CRITICAL FLOW: upload → modal → save (success path)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_parse_save_shows_success_toast(page):
    """THE KEY TEST: full flow upload → modal opens → click שמירה לטבלה → success toast.

    This is the test that would have caught the reported bug.
    If the save fails silently or shows no toast, this test fails.
    """
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=False)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # Click save without any edits — use the data as parsed
    page.locator("#financeInvoiceParseSave").click()

    wait_for_success_toast(page, title_contains="החשבונית נשמרה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_parse_save_closes_modal_on_success(page):
    """After successful save, the parse modal must close automatically."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=False)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)
    page.locator("#financeInvoiceParseSave").click()

    wait_for_success_toast(page, timeout=8_000)

    # Modal must close
    modal = page.locator("#financeInvoiceParseModal")
    modal.wait_for(state="hidden", timeout=5_000) if hasattr(modal, "wait_for") else wait_for_idle_ui(page)
    has_visible_class = "visible" in (modal.get_attribute("class") or "")
    assert not has_visible_class, "Parse modal still open after successful save"


# ===========================================================================
# THE CRITICAL FLOW: upload → modal → save (FAILURE path — the actual bug)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_save_failure_shows_error_toast_not_silence(page):
    """THE BUG TEST: when /finance-invoices-save returns 500, user must see error toast.

    This is exactly the scenario the user reported:
    - Modal opened fine
    - User made edits
    - Clicked שמירה לטבלה
    - It 'failed' — the question is: did the user see an error or nothing?

    This test mocks the save to fail and asserts the error toast appears.
    """
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=True, error_message="שגיאה בשמירה לגיליון")

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    page.locator("#financeInvoiceParseSave").click()

    wait_for_error_toast(page, title_contains="שמירת חשבונית נכשלה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_save_failure_keeps_modal_open(page):
    """When save fails, the modal must stay open so the user can try again."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=True, error_message="שגיאת רשת")

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    page.locator("#financeInvoiceParseSave").click()
    wait_for_error_toast(page, timeout=8_000)

    # Modal must STAY open after failure
    modal = page.locator("#financeInvoiceParseModal")
    has_visible_class = "visible" in (modal.get_attribute("class") or "")
    assert has_visible_class, (
        "Parse modal closed after save failure — user lost their edited data and cannot retry"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_save_error_message_shown_in_toast(page):
    """The error message from the server must appear in the toast, not a generic string."""
    specific_error = "הגיליון נעול — נסה שוב בעוד רגע"
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=True, error_message=specific_error)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    page.locator("#financeInvoiceParseSave").click()

    # The specific server error must reach the user
    page.locator(f".toast.error.visible").filter(has_text=specific_error).wait_for(
        state="visible", timeout=8_000
    )


# ===========================================================================
# FULL FLOW WITH MANUAL EDIT — the user's exact scenario
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_edit_field_then_save_success(page):
    """Full flow: upload → modal → enable edit → change supplier name → save → success toast.

    This simulates exactly what the user did:
    'הועלה חשבונית, נפתח מודאל, עדכנתי ידנית, לחצתי שמירה לטבלה'
    """
    _open_finance_tab(page)
    _mock_upload_endpoint(page)

    saved_rows = []

    def save_handler(route):
        body = json.loads(route.request.post_data or "{}")
        saved_rows.append(body.get("row", {}))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "ok", "row": body.get("row", {})}),
        )

    page.route("**/finance-invoices-save", save_handler)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # Enable manual edit for supplier_name and change it
    toggle = page.locator('[data-finance-parse-toggle="supplier_name"]')
    if toggle.count() > 0:
        toggle.check()
        wait_for_idle_ui(page)
        page.locator('[data-finance-parse-input="supplier_name"]').fill(
            "TEST | נעלולי פלא | ספק מעודכן ידנית"
        )

    page.locator("#financeInvoiceParseSave").click()
    wait_for_success_toast(page, title_contains="החשבונית נשמרה", timeout=8_000)

    # Verify the edited supplier name reached the server
    if saved_rows:
        supplier = saved_rows[0].get("supplier_name", "")
        assert "ספק מעודכן ידנית" in supplier, (
            f"Manually edited supplier name not sent to server. Got: '{supplier}'"
        )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_edit_field_then_save_failure_preserves_edit(page):
    """When save fails after editing, the edited values must still be in the modal fields."""
    _open_finance_tab(page)
    _mock_upload_endpoint(page)
    _mock_save_endpoint(page, fail=True, error_message="שגיאת שמירה")

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # Enable edit and change supplier name
    toggle = page.locator('[data-finance-parse-toggle="supplier_name"]')
    if toggle.count() > 0:
        toggle.check()
        wait_for_idle_ui(page)
        edited_name = "TEST | נעלולי פלא | ספק לאחר שגיאה"
        page.locator('[data-finance-parse-input="supplier_name"]').fill(edited_name)

    page.locator("#financeInvoiceParseSave").click()
    wait_for_error_toast(page, timeout=8_000)

    # The edited value must still be in the field (not wiped)
    if toggle.count() > 0:
        value = page.locator('[data-finance-parse-input="supplier_name"]').input_value()
        assert "TEST | נעלולי פלא | ספק לאחר שגיאה" in value, (
            f"Edited supplier name was wiped after save failure. Got: '{value}'"
        )


# ===========================================================================
# UPLOAD FAILURE — error toast before modal even opens
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_failure_shows_error_toast(page):
    """If the upload itself fails (server error), error toast must appear before modal."""
    _open_finance_tab(page)

    page.route(
        "**/finance-invoices-upload",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "שגיאת שרת בהעלאת קובץ"}),
        ),
    )

    _trigger_upload_via_js(page)
    wait_for_error_toast(page, title_contains="העלאת קבצים נכשלה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_failure_modal_does_not_open(page):
    """If upload fails, the parse modal must NOT open (nothing to parse)."""
    _open_finance_tab(page)

    page.route(
        "**/finance-invoices-upload",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "שגיאה"}),
        ),
    )

    _trigger_upload_via_js(page)
    wait_for_error_toast(page, timeout=8_000)

    wait_for_idle_ui(page)
    modal = page.locator("#financeInvoiceParseModal")
    has_visible_class = "visible" in (modal.get_attribute("class") or "")
    assert not has_visible_class, (
        "Parse modal opened even though the upload failed — user sees empty/broken modal"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_upload_empty_drafts_shows_error_toast(page):
    """If upload returns 200 but empty drafts array, error toast must appear."""
    _open_finance_tab(page)

    page.route(
        "**/finance-invoices-upload",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "ok", "drafts": []}),
        ),
    )

    _trigger_upload_via_js(page)
    # According to the JS: "הקבצים נשמרו, אבל לא הצלחתי לפרסר מהם נתונים להצגה."
    wait_for_error_toast(page, timeout=8_000)


# ===========================================================================
# MULTI-DRAFT QUEUE — multiple files
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_multiple_drafts_open_sequentially(page):
    """When 2 files are uploaded, saving the first must open the modal for the second."""
    draft2 = {**_MOCK_DRAFT, "supplier_name": "TEST | נעלולי פלא | ספק שני"}
    _open_finance_tab(page)
    _mock_upload_endpoint(page, drafts=[_MOCK_DRAFT.copy(), draft2])
    _mock_save_endpoint(page, fail=False)

    _trigger_upload_via_js(page)
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=8_000)

    # Save first → modal should reopen for second draft
    page.locator("#financeInvoiceParseSave").click()
    wait_for_success_toast(page, timeout=8_000)

    # Second modal must open
    wait_for_visible(page, "#financeInvoiceParseModal.visible", timeout=5_000)

    # Supplier name must be from the second draft
    supplier_input = page.locator('[data-finance-parse-input="supplier_name"]')
    value = supplier_input.input_value()
    assert "ספק שני" in value, (
        f"Second draft not loaded after first was saved. supplier_name: '{value}'"
    )
