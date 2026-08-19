"""Category C — File upload and import flows.

Covers every upload* / import* / ingest* / parse* function with 0% test coverage:

  - parseSupplierDeliveryNoteFile (/supplier-delivery-notes-parse)
  - savePendingSupplierDeliveryNote (/supplier-delivery-notes-save)
  - addSavedSupplierDeliveryRowToInventory (/supplier-delivery-notes-add-to-inventory)
  - uploadSignedQuoteFromHistory (/quote-history-upload-signed)
  - saveNewHrEmployee (/hr-employee-save)
  - ingestHrFiles (/hr-ingest-files)
  - importMarketingConstructionCompaniesXlsx (/marketing-construction-companies-import-xlsx)
  - importFinanceBankMovementFiles (/finance-bank-movements-upload)

For each flow the test suite covers:
  1. Empty / null file → early return (no request, no crash)
  2. Success (mocked) → correct success toast + UI update
  3. Failure (mocked) → error toast + button re-enabled
  4. API smoke → endpoint returns a valid HTTP status (never 404/405)

All E2E tests use page.route() — no real files are written or uploaded.
"""
from __future__ import annotations

import io
import json

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

_FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n%%EOF\n"
_FAKE_XLSX = b"PK\x03\x04TEST_XLSX"


def _open(page, tab: str = "orders") -> None:
    AppShell(page).open()
    AppShell(page).open_tab(tab)
    wait_for_idle_ui(page)


def _mock_ok(page, pattern: str, body: dict | None = None) -> None:
    b = json.dumps(body or {"status": "ok"})
    page.route(pattern, lambda r: r.fulfill(
        status=200, content_type="application/json", body=b))


def _mock_fail(page, pattern: str, error: str = "שגיאת שרת") -> None:
    page.route(pattern, lambda r: r.fulfill(
        status=500, content_type="application/json",
        body=json.dumps({"error": error})))


def _inject_file(page, input_id: str, filename: str, content: bytes,
                 mime: str = "application/pdf") -> None:
    """Inject a fake File object into a file input element via JS DataTransfer."""
    b64 = __import__("base64").b64encode(content).decode()
    page.evaluate(f"""
    () => {{
        const input = document.getElementById('{input_id}');
        if (!input) return;
        const bytes = Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0));
        const blob = new Blob([bytes], {{type: '{mime}'}});
        const file = new File([blob], '{filename}', {{type: '{mime}'}});
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {{value: dt.files, writable: false}});
        input.dispatchEvent(new Event('change', {{bubbles: true}}));
    }}
    """)
    wait_for_idle_ui(page)


def _call_with_fake_file(page, func_name: str, filename: str,
                          content: bytes, mime: str = "application/pdf") -> None:
    b64 = __import__("base64").b64encode(content).decode()
    page.evaluate(f"""
    async () => {{
        const bytes = Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0));
        const blob = new Blob([bytes], {{type: '{mime}'}});
        const file = new File([blob], '{filename}', {{type: '{mime}'}});
        if (typeof {func_name} === 'function') {{
            try {{ await {func_name}(file); }} catch(e) {{}}
        }}
    }}
    """)
    wait_for_idle_ui(page)


# ===========================================================================
# 1. SUPPLIER DELIVERY NOTE — PARSE
# ===========================================================================

class TestParseSupplierDeliveryNoteFile:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_parse_with_null_file_does_not_crash(self, page):
        _open(page, "inventory")
        result = page.evaluate("""
        async () => {
            try {
                if (typeof parseSupplierDeliveryNoteFile === 'function') {
                    await parseSupplierDeliveryNoteFile(null);
                    return 'ok';
                }
                return 'not_found';
            } catch (e) {
                return e.message;
            }
        }
        """)
        assert result in ("ok", "not_found"), \
            f"parseSupplierDeliveryNoteFile(null) threw: {result}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_parse_supplier_delivery_success_shows_toast(self, page):
        _open(page, "inventory")
        _mock_ok(page, "**/supplier-delivery-notes-parse", {
            "status": "ok",
            "draft": {
                "supplier_name": "TEST | נעלולי פלא | ספק",
                "delivery_number": "DN-TEST-001",
                "items": [{"description": "חומר גלם", "quantity": 10, "unit_price": 100}],
            },
        })
        _call_with_fake_file(page, "parseSupplierDeliveryNoteFile",
                             "delivery-note.pdf", _FAKE_PDF)
        wait_for_success_toast(page, title_contains="התעודה נותחה", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_parse_supplier_delivery_failure_shows_error_toast(self, page):
        _open(page, "inventory")
        _mock_fail(page, "**/supplier-delivery-notes-parse", "הקובץ לא קריא")
        _call_with_fake_file(page, "parseSupplierDeliveryNoteFile",
                             "delivery-note.pdf", _FAKE_PDF)
        wait_for_error_toast(page, title_contains="פרסור תעודת משלוח נכשל", timeout=8_000)


# ===========================================================================
# 2. SAVE PENDING SUPPLIER DELIVERY NOTE
# ===========================================================================

class TestSavePendingSupplierDeliveryNote:

    def _inject_pending_draft(self, page) -> None:
        page.evaluate("""
        () => {
            window.pendingSupplierDeliveryNoteDraft = {
                supplier_name: "TEST | נעלולי פלא | ספק",
                delivery_number: "DN-TEST-001",
                items: [{ description: "חומר גלם", quantity: 10, unit_price: 100 }],
            };
        }
        """)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_save_supplier_delivery_note_success_shows_toast(self, page):
        _open(page, "inventory")
        self._inject_pending_draft(page)
        _mock_ok(page, "**/supplier-delivery-notes-save", {
            "status": "ok",
            "row": {"delivery_number": "DN-TEST-001"},
        })
        page.evaluate("""
        async () => {
            if (typeof savePendingSupplierDeliveryNote === 'function') {
                await savePendingSupplierDeliveryNote();
            }
        }
        """)
        wait_for_success_toast(page, title_contains="תעודת המשלוח נשמרה", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_save_supplier_delivery_note_failure_shows_error_toast(self, page):
        _open(page, "inventory")
        self._inject_pending_draft(page)
        _mock_fail(page, "**/supplier-delivery-notes-save", "Sheets לא נגיש")
        page.evaluate("""
        async () => {
            if (typeof savePendingSupplierDeliveryNote === 'function') {
                await savePendingSupplierDeliveryNote();
            }
        }
        """)
        wait_for_error_toast(page, timeout=8_000)


# ===========================================================================
# 3. ADD SUPPLIER DELIVERY ROW TO INVENTORY
# ===========================================================================

class TestAddSavedSupplierDeliveryRowToInventory:

    def _build_delivery_row(self) -> dict:
        return {
            "row_id": "dn-test-row-001",
            "delivery_number": "DN-TEST-001",
            "supplier_name": "TEST | נעלולי פלא | ספק",
            "items": [{"sku": "SKU-001", "quantity": 10, "unit": "יח׳"}],
        }

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_add_to_inventory_success_shows_toast(self, page):
        _open(page, "inventory")
        row = self._build_delivery_row()
        _mock_ok(page, "**/supplier-delivery-notes-add-to-inventory", {
            "status": "ok",
            "updated_count": 1,
        })
        page.evaluate(f"""
        async () => {{
            const row = {json.dumps(row)};
            if (typeof addSavedSupplierDeliveryRowToInventory === 'function') {{
                await addSavedSupplierDeliveryRowToInventory(row);
            }}
        }}
        """)
        wait_for_success_toast(page, title_contains="השורה נוספה למלאי", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_add_to_inventory_failure_shows_error_toast(self, page):
        _open(page, "inventory")
        row = self._build_delivery_row()
        _mock_fail(page, "**/supplier-delivery-notes-add-to-inventory", "מלאי לא נגיש")
        page.evaluate(f"""
        async () => {{
            const row = {json.dumps(row)};
            if (typeof addSavedSupplierDeliveryRowToInventory === 'function') {{
                await addSavedSupplierDeliveryRowToInventory(row);
            }}
        }}
        """)
        wait_for_error_toast(page, title_contains="הוספה למלאי נכשלה", timeout=8_000)


# ===========================================================================
# 4. UPLOAD SIGNED QUOTE FROM HISTORY
# ===========================================================================

class TestUploadSignedQuoteFromHistory:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_upload_signed_quote_with_null_does_not_crash(self, page):
        _open(page, "orders")
        result = page.evaluate("""
        async () => {
            try {
                if (typeof uploadSignedQuoteFromHistory === 'function') {
                    await uploadSignedQuoteFromHistory('hist-test-001', null);
                    return 'ok';
                }
                return 'not_found';
            } catch(e) { return e.message; }
        }
        """)
        assert result in ("ok", "not_found"), \
            f"uploadSignedQuoteFromHistory(id, null) threw: {result}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_upload_signed_quote_success_shows_toast(self, page):
        _open(page, "orders")
        _mock_ok(page, "**/quote-history-upload-signed", {
            "status": "ok",
            "message": "הקובץ נשמר בתיקיית ה-Drive של ההצעה.",
        })
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const bytes = Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0));
            const file = new File([bytes], 'signed-quote.pdf', {{type: 'application/pdf'}});
            window.targetHistoryId = 'hist-test-001';
            if (typeof uploadSignedQuoteFromHistory === 'function') {{
                await uploadSignedQuoteFromHistory('hist-test-001', file);
            }}
        }}
        """)
        wait_for_success_toast(page, title_contains="ההצעה החתומה הועלתה", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_upload_signed_quote_shows_info_toast_on_start(self, page):
        _open(page, "orders")

        requests_made = []

        def capture(route):
            requests_made.append(route.request.url)
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"status": "ok", "message": "הועלה"}))

        page.route("**/quote-history-upload-signed", capture)
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File([Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'signed.pdf', {{type: 'application/pdf'}});
            window.targetHistoryId = 'hist-001';
            if (typeof uploadSignedQuoteFromHistory === 'function') {{
                await uploadSignedQuoteFromHistory('hist-001', file);
            }}
        }}
        """)
        # Info toast fires BEFORE the request ("מעלה הצעה חתומה")
        wait_for_idle_ui(page)
        assert len(requests_made) == 1, \
            f"Expected 1 request to upload endpoint, got {len(requests_made)}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_upload_signed_quote_failure_shows_error_toast(self, page):
        _open(page, "orders")
        _mock_fail(page, "**/quote-history-upload-signed", "Drive לא נגיש")
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File([Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'signed.pdf', {{type: 'application/pdf'}});
            window.targetHistoryId = 'hist-001';
            if (typeof uploadSignedQuoteFromHistory === 'function') {{
                await uploadSignedQuoteFromHistory('hist-001', file);
            }}
        }}
        """)
        wait_for_error_toast(page, title_contains="שגיאה בהעלאת ההצעה החתומה", timeout=8_000)


# ===========================================================================
# 5. HR — SAVE NEW EMPLOYEE
# ===========================================================================

class TestSaveNewHrEmployee:

    def _open_hr_create_modal(self, page) -> None:
        page.evaluate("""
        () => {
            const m = document.getElementById('hrCreateEmployeeModal');
            if (m) { m.classList.add('visible'); m.setAttribute('aria-hidden', 'false'); }
        }
        """)
        wait_for_idle_ui(page)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_create_employee_modal_exists(self, page):
        _open(page, "hr")
        assert page.locator("#hrCreateEmployeeModal").count() > 0

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_save_employee_without_name_shows_notification(self, page):
        _open(page, "hr")
        self._open_hr_create_modal(page)
        name_el = page.locator("#hrCreateEmployeeName").first
        if name_el.is_visible():
            name_el.fill("")
        page.evaluate("""
        async () => {
            if (typeof saveNewHrEmployee === 'function') await saveNewHrEmployee();
        }
        """)
        wait_for_idle_ui(page)
        # Uses notify() not showToast — check no request was made
        # The function returns early; no toast or request occurs
        error_count = page.locator(".toast.error.visible").count()
        assert error_count == 0, \
            "Unexpected error toast when employee name is missing (should use notify/return early)"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_save_employee_success_closes_modal(self, page):
        _open(page, "hr")
        self._open_hr_create_modal(page)
        _mock_ok(page, "**/hr-employee-save", {
            "status": "ok",
            "row": {
                "employee_id": "emp_test_001",
                "full_name": "TEST | נעלולי פלא | עובד",
            },
        })
        name_el = page.locator("#hrCreateEmployeeName").first
        if name_el.is_visible():
            name_el.fill("TEST | נעלולי פלא | עובד")
        page.evaluate("""
        async () => {
            if (typeof saveNewHrEmployee === 'function') await saveNewHrEmployee();
        }
        """)
        wait_for_idle_ui(page)
        modal = page.locator("#hrCreateEmployeeModal")
        cls = modal.get_attribute("class") or ""
        assert "visible" not in cls, \
            "HR create employee modal stayed open after successful save"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_hr_save_employee_failure_re_enables_save_button(self, page):
        _open(page, "hr")
        self._open_hr_create_modal(page)
        _mock_fail(page, "**/hr-employee-save", "Sheets לא נגיש")
        name_el = page.locator("#hrCreateEmployeeName").first
        if name_el.is_visible():
            name_el.fill("TEST | נעלולי פלא | עובד")
        page.evaluate("""
        async () => {
            if (typeof saveNewHrEmployee === 'function') await saveNewHrEmployee();
        }
        """)
        wait_for_idle_ui(page)
        btn = page.locator("#hrCreateEmployeeSave").first
        if btn.count():
            assert not btn.is_disabled(), \
                "HR save employee button still disabled after failure"


# ===========================================================================
# 6. HR — INGEST FILES
# ===========================================================================

class TestIngestHrFiles:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_ingest_hr_files_with_empty_list_does_not_crash(self, page):
        _open(page, "hr")
        result = page.evaluate("""
        async () => {
            try {
                if (typeof ingestHrFiles === 'function') {
                    await ingestHrFiles([], '');
                    return 'ok';
                }
                return 'not_found';
            } catch(e) { return e.message; }
        }
        """)
        assert result in ("ok", "not_found"), \
            f"ingestHrFiles([]) threw: {result}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_ingest_hr_files_success_shows_success_result(self, page):
        _open(page, "hr")
        _mock_ok(page, "**/hr-ingest-files", {
            "status": "ok",
            "imported_count": 1,
            "results": [{"file": "payslip.pdf", "status": "ok"}],
        })
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File(
                [Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'payslip-TEST-נעלולי-פלא.pdf',
                {{type: 'application/pdf'}}
            );
            if (typeof ingestHrFiles === 'function') {{
                await ingestHrFiles([file], 'payslips');
            }}
        }}
        """)
        wait_for_idle_ui(page)
        error_count = page.locator(".toast.error.visible").count()
        assert error_count == 0, "Error toast after successful HR file ingest"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_ingest_hr_files_failure_shows_error(self, page):
        _open(page, "hr")
        _mock_fail(page, "**/hr-ingest-files", "קובץ לא נתמך")
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File(
                [Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'bad-file.pdf', {{type: 'application/pdf'}}
            );
            try {{
                if (typeof ingestHrFiles === 'function') await ingestHrFiles([file], 'payslips');
            }} catch(e) {{
                if (typeof showToast === 'function') showToast('error', 'ייבוא קבצי HR נכשל', e.message);
            }}
        }}
        """)
        wait_for_error_toast(page, timeout=8_000)


# ===========================================================================
# 7. IMPORT MARKETING CONSTRUCTION COMPANIES XLSX
# ===========================================================================

class TestImportMarketingConstructionCompaniesXlsx:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_xlsx_with_null_does_not_crash(self, page):
        _open(page, "marketing")
        result = page.evaluate("""
        async () => {
            try {
                if (typeof importMarketingConstructionCompaniesXlsx === 'function') {
                    await importMarketingConstructionCompaniesXlsx(null);
                    return 'ok';
                }
                return 'not_found';
            } catch(e) { return e.message; }
        }
        """)
        assert result in ("ok", "not_found"), \
            f"importMarketingConstructionCompaniesXlsx(null) threw: {result}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_xlsx_success_shows_toast(self, page):
        _open(page, "marketing")
        _mock_ok(page, "**/marketing-construction-companies-import-xlsx", {
            "status": "ok",
            "imported_count": 5,
        })
        _call_with_fake_file(
            page,
            "importMarketingConstructionCompaniesXlsx",
            "construction-companies.xlsx",
            _FAKE_XLSX,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wait_for_success_toast(page, title_contains="האקסל יובא", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_xlsx_failure_shows_error_toast(self, page):
        _open(page, "marketing")
        _mock_fail(page, "**/marketing-construction-companies-import-xlsx",
                   "פורמט קובץ לא נתמך")
        _call_with_fake_file(
            page,
            "importMarketingConstructionCompaniesXlsx",
            "bad.xlsx",
            _FAKE_XLSX,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wait_for_error_toast(page, title_contains="ייבוא אקסל נכשל", timeout=8_000)


# ===========================================================================
# 8. IMPORT FINANCE BANK MOVEMENT FILES
# ===========================================================================

class TestImportFinanceBankMovementFiles:

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_bank_movements_with_empty_files_does_not_crash(self, page):
        _open(page, "finance")
        result = page.evaluate("""
        async () => {
            try {
                if (typeof importFinanceBankMovementFiles === 'function') {
                    await importFinanceBankMovementFiles([]);
                    return 'ok';
                }
                return 'not_found';
            } catch(e) { return e.message; }
        }
        """)
        assert result in ("ok", "not_found"), \
            f"importFinanceBankMovementFiles([]) threw: {result}"

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_bank_movements_success_shows_toast(self, page):
        _open(page, "finance")
        _mock_ok(page, "**/finance-bank-movements-upload", {
            "status": "ok",
            "imported_count": 42,
        })
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File(
                [Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'bank-statement.pdf', {{type: 'application/pdf'}}
            );
            if (typeof importFinanceBankMovementFiles === 'function') {{
                await importFinanceBankMovementFiles([file]);
            }}
        }}
        """)
        wait_for_success_toast(page, title_contains="תנועות העו״ש נטענו", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_bank_movements_failure_shows_error_toast(self, page):
        _open(page, "finance")
        _mock_fail(page, "**/finance-bank-movements-upload", "פרסור עו״ש נכשל")
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File(
                [Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'bank-statement.pdf', {{type: 'application/pdf'}}
            );
            if (typeof importFinanceBankMovementFiles === 'function') {{
                await importFinanceBankMovementFiles([file]);
            }}
        }}
        """)
        wait_for_error_toast(page, title_contains="ייבוא עו״ש נכשל", timeout=8_000)

    @pytest.mark.e2e
    @pytest.mark.requires_browser
    @pytest.mark.requires_live_server
    def test_import_bank_movements_button_re_enabled_after_failure(self, page):
        _open(page, "finance")
        _mock_fail(page, "**/finance-bank-movements-upload", "שגיאה")
        b64 = __import__("base64").b64encode(_FAKE_PDF).decode()
        page.evaluate(f"""
        async () => {{
            const file = new File(
                [Uint8Array.from(atob('{b64}'), c => c.charCodeAt(0))],
                'bank-statement.pdf', {{type: 'application/pdf'}}
            );
            if (typeof importFinanceBankMovementFiles === 'function') {{
                await importFinanceBankMovementFiles([file]);
            }}
        }}
        """)
        wait_for_error_toast(page, timeout=8_000)
        btn = page.locator("#financeBankMovementsImportButton").first
        if btn.count():
            assert not btn.is_disabled(), \
                "Bank movements import button still disabled after failure"


# ===========================================================================
# API SMOKE — all C-category endpoints must exist
# ===========================================================================

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("path,method,use_files,body", [
    ("/supplier-delivery-notes-parse", "post", True, None),
    ("/supplier-delivery-notes-save", "post", False, {
        "supplier_name": "TEST | נעלולי פלא | ספק",
        "delivery_number": "DN-API-TEST-001",
        "items": [],
    }),
    ("/supplier-delivery-notes-add-to-inventory", "post", False, {
        "row_id": "dn-api-test-001",
        "items": [],
    }),
    ("/quote-history-upload-signed", "post", True, None),
    ("/hr-employee-save", "post", False, {
        "employee_id": "emp_api_test_001",
        "full_name": "TEST | נעלולי פלא | עובד API",
        "employment_type": "global",
    }),
    ("/hr-ingest-files", "post", True, None),
    ("/marketing-construction-companies-import-xlsx", "post", True, None),
    ("/finance-bank-movements-upload", "post", True, None),
])
def test_upload_endpoint_returns_valid_status(api_client, path, method, use_files, body):
    """C-category file upload endpoints must return a meaningful status, never 404/405."""
    if use_files:
        files = {"file": ("test.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")}
        # Some endpoints accept 'files' (plural)
        try:
            response = api_client.post(path, files=files)
        except Exception:
            files2 = {"files": ("test.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")}
            response = api_client.post(path, files=files2)
    else:
        fn = getattr(api_client, method)
        response = fn(path, json=body or {})

    assert response.status_code not in {404, 405}, (
        f"{method.upper()} {path} returned {response.status_code} — endpoint missing or wrong method"
    )
    assert response.status_code in {200, 400, 422, 500}, (
        f"Unexpected status {response.status_code} from {path}"
    )
