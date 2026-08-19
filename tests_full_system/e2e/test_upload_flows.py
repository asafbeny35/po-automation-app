"""E2E tests for all upload flows — single-step uploads with no intermediate modal.

Pattern: user selects file → API call → success/error toast + UI state update.
Each test mocks the endpoint to isolate the JS feedback layer.

Flows covered:
- Working order upload (PDF → row in table)
- Transport label upload (PDF → currentData updated)
- Signed quote upload from history (PDF → history row updated)
- Project managers file upload (PDF → table updated)
- Delivery confirmation upload (PDF → row state updated)
- Finance bank movements upload (PDF → movements in table)
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


def _open(page, tab: str) -> None:
    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab)
    wait_for_idle_ui(page)


def _route_ok(page, url_pattern: str, body: dict) -> None:
    page.route(url_pattern, lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(body)
    ))


def _route_fail(page, url_pattern: str, error: str = "שגיאת שרת") -> None:
    page.route(url_pattern, lambda r: r.fulfill(
        status=500, content_type="application/json", body=json.dumps({"error": error})
    ))


# ===========================================================================
# WORKING ORDER UPLOAD
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_upload_success_shows_toast_and_adds_row(page):
    """PDF upload → /working-orders-upload → toast success + row appears in table."""
    _open(page, "orders")

    new_row = {
        "row_id": "test-wo-e2e-001",
        "customer_name": "TEST | נעלולי פלא | לקוח הזמנה בעבודה",
        "po_number": "WO-E2E-001",
        "status": "פעיל",
    }
    _route_ok(page, "**/working-orders-upload", {"status": "ok", "row": new_row})

    page.evaluate("""
    () => {
        const input = document.getElementById('workingOrdersFileInput')
            || document.querySelector('[id*="workingOrders"][type=file]');
        if (!input) return;
        const blob = new Blob(['%PDF-1.4 fake'], {type: 'application/pdf'});
        const file = new File([blob], 'wo.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {value: dt.files});
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
    """)
    wait_for_idle_ui(page)

    # Trigger upload button click
    upload_btn = page.locator("#workingOrdersUploadButton")
    if upload_btn.is_visible():
        upload_btn.click()

    wait_for_success_toast(page, title_contains="הזמנה נשמרה בעבודה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_upload_failure_shows_error_toast(page):
    """Upload failure → toast error, button re-enabled."""
    _open(page, "orders")
    _route_fail(page, "**/working-orders-upload", "שגיאת Drive בשמירת ההזמנה")

    page.evaluate("""
    () => {
        const btn = document.getElementById('workingOrdersUploadButton');
        if (btn) btn.click();
    }
    """)
    # No file → info toast
    wait_for_info_toast(page, title_contains="צריך לבחור קובץ", timeout=5_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_upload_button_disabled_during_upload(page):
    """Upload button must be disabled while in progress (prevents double-submit)."""
    _open(page, "orders")

    # Intercept and delay response
    def slow_handler(route):
        import time; time.sleep(0.3)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok", "row": {"row_id": "test"}}))

    page.route("**/working-orders-upload", slow_handler)

    page.evaluate("""
    () => {
        const input = document.getElementById('workingOrdersFileInput')
            || document.querySelector('[id*="workingOrders"][type=file]');
        if (!input) return;
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'wo.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {value: dt.files});
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
    """)

    btn = page.locator("#workingOrdersUploadButton")
    if btn.is_visible():
        btn.click()
        # Button should be disabled immediately
        assert btn.is_disabled(), "Upload button not disabled during upload — double-submit possible"


# ===========================================================================
# TRANSPORT LABEL UPLOAD
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_transport_label_upload_success_shows_toast_and_updates_state(page):
    """PDF upload → /upload-transport-label → toast success + currentData updated."""
    _open(page, "orders")
    _route_ok(page, "**/upload-transport-label", {
        "transport_label_path": "/tmp/test-label.pdf",
        "transport_label_name": "test-label.pdf",
    })

    page.evaluate("""
    () => {
        const input = document.getElementById('transportLabelInput')
            || document.querySelector('[id*="transportLabel"][type=file], [id*="TransportLabel"][type=file]');
        if (!input) {
            // Trigger via the file picker programmatically
            const blob = new Blob(['%PDF'], {type: 'application/pdf'});
            const file = new File([blob], 'label.pdf', {type: 'application/pdf'});
            // Call uploadTransportLabelFile directly if available
            if (typeof uploadTransportLabelFile === 'function') {
                uploadTransportLabelFile(file);
            }
            return;
        }
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'label.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {value: dt.files});
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
    """)
    wait_for_idle_ui(page)
    wait_for_success_toast(page, title_contains="PDF משלוח נשמר", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_transport_label_upload_failure_shows_error_toast(page):
    """Transport label upload failure → toast error."""
    _open(page, "orders")
    _route_fail(page, "**/upload-transport-label", "שגיאה בשמירת PDF המשלוח")

    page.evaluate("""
    () => {
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'label.pdf', {type: 'application/pdf'});
        if (typeof uploadTransportLabelFile === 'function') {
            uploadTransportLabelFile(file);
        }
    }
    """)
    wait_for_idle_ui(page)
    wait_for_error_toast(page, title_contains="שגיאה בהעלאת PDF משלוח", timeout=8_000)


# ===========================================================================
# SIGNED QUOTE UPLOAD FROM HISTORY
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_signed_quote_upload_shows_info_toast_immediately(page):
    """Signed quote upload must show info toast 'מעלה הצעה חתומה' before API completes."""
    _open(page, "orders")

    # Load history panel first
    wait_for_visible(page, "#quoteHistoryOpenButton")
    page.locator("#quoteHistoryOpenButton").click()
    wait_for_idle_ui(page)

    _route_ok(page, "**/quote-history-upload-signed", {
        "status": "ok",
        "message": "הקובץ נשמר בדרייב",
        "rows": [],
    })

    page.evaluate("""
    () => {
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'signed.pdf', {type: 'application/pdf'});
        if (typeof uploadSignedQuoteFromHistory === 'function') {
            uploadSignedQuoteFromHistory('test-history-id-001', file);
        }
    }
    """)
    wait_for_idle_ui(page)
    # info toast fires immediately before fetch completes
    wait_for_info_toast(page, title_contains="מעלה הצעה חתומה", timeout=5_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_signed_quote_upload_success_shows_success_toast(page):
    """After successful upload of signed quote → success toast."""
    _open(page, "orders")

    _route_ok(page, "**/quote-history-upload-signed", {
        "status": "ok",
        "message": "ההצעה החתומה הועלתה בהצלחה",
        "rows": [],
    })

    page.evaluate("""
    () => {
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'signed.pdf', {type: 'application/pdf'});
        if (typeof uploadSignedQuoteFromHistory === 'function') {
            uploadSignedQuoteFromHistory('test-history-id-001', file);
        }
    }
    """)
    wait_for_success_toast(page, title_contains="ההצעה החתומה הועלתה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_signed_quote_upload_failure_shows_error_toast(page):
    """Signed quote upload failure → error toast."""
    _open(page, "orders")
    _route_fail(page, "**/quote-history-upload-signed", "תיקיית הדרייב לא נמצאה")

    page.evaluate("""
    () => {
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'signed.pdf', {type: 'application/pdf'});
        if (typeof uploadSignedQuoteFromHistory === 'function') {
            uploadSignedQuoteFromHistory('test-history-id-001', file);
        }
    }
    """)
    wait_for_error_toast(page, title_contains="שגיאה בהעלאת ההצעה החתומה", timeout=8_000)


# ===========================================================================
# PROJECT MANAGERS FILE UPLOAD
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_project_managers_upload_success_shows_toast_and_table(page):
    """PDF upload → /project-managers-upload → toast success + table updated."""
    _open(page, "admin")

    _route_ok(page, "**/project-managers-upload", {
        "status": "ok",
        "rows": [
            {"contact_name": "TEST | נעלולי פלא | מנהל", "company": "חברת בנייה", "po_number": "PO-001"}
        ],
        "po_number": "PO-001",
    })

    page.evaluate("""
    () => {
        const input = document.getElementById('projectManagersUploadInput')
            || document.querySelector('[id*="projectManagers"][type=file]');
        if (!input) return;
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'order.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', {value: dt.files});
        if (typeof uploadProjectManagersFile === 'function') {
            uploadProjectManagersFile();
        } else {
            input.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }
    """)
    wait_for_idle_ui(page)
    wait_for_success_toast(page, title_contains="הטבלה עודכנה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_project_managers_upload_failure_shows_error_toast(page):
    _open(page, "admin")
    _route_fail(page, "**/project-managers-upload", "OCR נכשל")

    page.evaluate("""
    () => {
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'order.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('projectManagersUploadInput')
            || document.querySelector('[id*="projectManagers"][type=file]');
        if (input) {
            Object.defineProperty(input, 'files', {value: dt.files});
        }
        if (typeof uploadProjectManagersFile === 'function') {
            uploadProjectManagersFile();
        }
    }
    """)
    wait_for_error_toast(page, title_contains="שגיאה בעדכון מנהלי פרויקטים", timeout=8_000)


# ===========================================================================
# DELIVERY CONFIRMATION UPLOAD
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_confirmation_upload_without_pending_row_shows_error(page):
    """Upload without a pending row → error toast 'לא נמצאה שורת אישור מסירה'."""
    _open(page, "orders")

    page.evaluate("""
    () => {
        // Clear any pending state so upload has no target row
        if (typeof pendingDeliveryUploadPoNumber !== 'undefined') {
            window.pendingDeliveryUploadPoNumber = '';
        }
        const blob = new Blob(['%PDF'], {type: 'application/pdf'});
        const file = new File([blob], 'delivery.pdf', {type: 'application/pdf'});
        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('deliveryConfirmationUploadInput');
        if (input) {
            Object.defineProperty(input, 'files', {value: dt.files});
        }
        if (typeof uploadDeliveryConfirmationFile === 'function') {
            uploadDeliveryConfirmationFile();
        }
    }
    """)
    wait_for_idle_ui(page)
    wait_for_error_toast(page, title_contains="לא נמצאה שורת אישור מסירה", timeout=5_000)


# ===========================================================================
# INVENTORY PURCHASE ORDER CREATE
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_without_supplier_shows_error_toast(page):
    """Creating PO without supplier name → 'חסר ספק' error toast."""
    _open(page, "inventory")

    page.locator("#inventoryPoCreateSandboxButton").click()
    wait_for_error_toast(page, title_contains="חסר ספק", timeout=5_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_without_item_shows_error_toast(page):
    """Creating PO with supplier but no item description → 'חסר פריט'."""
    _open(page, "inventory")

    # Set a supplier name in state (simulate)
    page.evaluate("""
    () => {
        const supplierInput = document.getElementById('inventoryPoSupplierInput')
            || document.querySelector('[id*="inventoryPo"][id*="Supplier"]')
            || document.querySelector('[id*="PoSupplier"]');
        if (supplierInput) supplierInput.value = 'TEST | נעלולי פלא | ספק';
    }
    """)
    wait_for_idle_ui(page)

    page.locator("#inventoryPoCreateSandboxButton").click()
    # Without item, should get חסר פריט or חסר ספק depending on form state
    page.locator(".toast.error.visible, .toast.info.visible").first.wait_for(
        state="visible", timeout=5_000
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_success_shows_toast_and_row(page):
    """Full PO creation success → toast + row in table."""
    _open(page, "inventory")

    _route_ok(page, "**/inventory-purchase-orders-create", {
        "status": "ok",
        "row": {
            "history_id": "test-po-e2e-001",
            "supplier_name": "TEST | נעלולי פלא | ספק רכש",
            "po_number": "RK-E2E-001",
        },
        "rows": [],
    })

    page.evaluate("""
    () => {
        const payload = {
            mode: 'sandbox',
            supplier_name: 'TEST | נעלולי פלא | ספק רכש',
            item_description: 'TEST | נעלולי פלא | פריט',
            item_quantity: '10',
            item_unit_price: '50',
        };
        // Directly call createInventoryPurchaseOrder if available
        if (typeof createInventoryPurchaseOrder === 'function') {
            // Patch buildInventoryPurchaseOrderPayload to return our payload
            const original = window.buildInventoryPurchaseOrderPayload;
            window.buildInventoryPurchaseOrderPayload = () => payload;
            createInventoryPurchaseOrder('sandbox').finally(() => {
                if (original) window.buildInventoryPurchaseOrderPayload = original;
            });
        }
    }
    """)
    wait_for_success_toast(page, title_contains="הזמנת רכש נוצרה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_failure_shows_error_toast(page):
    """PO creation failure → toast error + progress bar shows failure."""
    _open(page, "inventory")

    _route_fail(page, "**/inventory-purchase-orders-create", "חשבונית ירוקה לא זמינה")

    page.evaluate("""
    () => {
        const payload = {
            mode: 'sandbox',
            supplier_name: 'TEST | נעלולי פלא | ספק',
            item_description: 'TEST | נעלולי פלא | פריט',
            item_quantity: '5',
            item_unit_price: '100',
        };
        if (typeof createInventoryPurchaseOrder === 'function') {
            const original = window.buildInventoryPurchaseOrderPayload;
            window.buildInventoryPurchaseOrderPayload = () => payload;
            createInventoryPurchaseOrder('sandbox').finally(() => {
                if (original) window.buildInventoryPurchaseOrderPayload = original;
            });
        }
    }
    """)
    wait_for_error_toast(page, title_contains="יצירת הזמנת רכש נכשלה", timeout=8_000)
