from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payment_confirmation_preserves_open_row_edits_and_moves_row_to_paid_filter(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")

    result = page.evaluate(
        """
        async () => {
          const bridge = window.__paymentsTestBridge;
          const sampleRow = {
            invoice_date: "15/12/2025",
            customer_name: "אשקלון פולימרים",
            payment_terms_days: "120",
            payment_direction: "תשלום",
            amount: "₪1,773.75",
            po_number: "12/011957",
            delivery_number: "",
            proforma_invoice_number: "",
            tax_invoice_number: "",
            receipt_number: "",
            notes: "",
            due_date: "01/05/2026",
            paid: "FALSE",
            source_mode: "",
            _sheet_title: "תשלומים והעברות 2026",
            _sheet_row: 58,
          };

          bridge.resetEditing();
          bridge.renderState({
            all_rows: [sampleRow],
            current_sheet: "תשלומים והעברות 2026",
          });

          const rowKey = bridge.paymentRowKey(sampleRow);
          await bridge.beginRowEdit(sampleRow);
          bridge.patchEditedRow(rowKey, { notes: "3465", paid: true });

          bridge.installLocalUpdateMocks();

          bridge.setPendingPaidConfirm("payment", rowKey);
          await bridge.confirmPaidChange();

          bridge.setPaymentFilter("paid");
          bridge.renderState(bridge.getState());

          const paidRows = bridge.getFilteredRows("payment");
          return {
            paidRows,
            topSummary: document.getElementById("paymentsTransfer2026PaymentSummary")?.innerText || "",
            bottomSummary: document.getElementById("paymentsTransfer2026PaymentFilterSummary")?.innerText || "",
          };
        }
        """
    )

    assert len(result["paidRows"]) == 1
    assert result["paidRows"][0]["paid"] == "TRUE"
    assert result["paidRows"][0]["notes"] == "3465"
    assert "אשקלון פולימרים" in result["topSummary"] or "1" in result["topSummary"]
    assert "שולמו" in result["bottomSummary"]


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payment_top_summary_respects_active_payment_filter(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")

    result = page.evaluate(
        """
        () => {
          const bridge = window.__paymentsTestBridge;
          const rows = [
            {
              invoice_date: "01/05/2026",
              customer_name: "נעלולי פלא פתוח",
              payment_terms_days: "30",
              payment_direction: "תשלום",
              amount: "₪100.00",
              po_number: "PO-OPEN",
              delivery_number: "",
              proforma_invoice_number: "",
              tax_invoice_number: "",
              receipt_number: "",
              notes: "",
                  due_date: "25/07/2026",
              paid: "FALSE",
              source_mode: "",
              _sheet_title: "תשלומים והעברות 2026",
              _sheet_row: 1,
            },
            {
              invoice_date: "01/04/2026",
              customer_name: "נעלולי פלא חלף",
              payment_terms_days: "30",
              payment_direction: "תשלום",
              amount: "₪200.00",
              po_number: "PO-OVERDUE",
              delivery_number: "",
              proforma_invoice_number: "",
              tax_invoice_number: "",
              receipt_number: "",
              notes: "",
              due_date: "01/04/2026",
              paid: "FALSE",
              source_mode: "",
              _sheet_title: "תשלומים והעברות 2026",
              _sheet_row: 2,
            },
            {
              invoice_date: "01/05/2026",
              customer_name: "נעלולי פלא שולם",
              payment_terms_days: "30",
              payment_direction: "תשלום",
              amount: "₪300.00",
              po_number: "PO-PAID",
              delivery_number: "",
              proforma_invoice_number: "",
              tax_invoice_number: "",
              receipt_number: "",
              notes: "",
              due_date: "18/05/2026",
              paid: "TRUE",
              source_mode: "",
              _sheet_title: "תשלומים והעברות 2026",
              _sheet_row: 3,
            },
          ];

          bridge.setPaymentFilter("open");
          bridge.renderState({
            all_rows: rows,
            current_sheet: "תשלומים והעברות 2026",
          });

          return {
            topSummary: document.getElementById("paymentsTransfer2026PaymentSummary")?.innerText || "",
            bottomSummary: document.getElementById("paymentsTransfer2026PaymentFilterSummary")?.innerText || "",
            visibleRows: bridge.getFilteredRows("payment").length,
          };
        }
        """
    )

    assert result["visibleRows"] == 1
    assert "נמצאו 1 שורות" in result["topSummary"]
    assert "100.00" in result["topSummary"]
    assert "שטרם שולמו" in result["bottomSummary"]
