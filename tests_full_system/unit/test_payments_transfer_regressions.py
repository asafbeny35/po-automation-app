from __future__ import annotations

from services.google_sheets import _build_payment_transfer_state


def _row(
    *,
    invoice_date: str,
    customer_name: str,
    payment_direction: str,
    amount: str,
    due_date: str,
    paid: str,
    sheet_title: str,
    sheet_row: int,
    notes: str = "",
) -> dict:
    return {
        "invoice_date": invoice_date,
        "customer_name": customer_name,
        "payment_terms_days": "120",
        "payment_direction": payment_direction,
        "amount": amount,
        "po_number": "TEST-PO",
        "delivery_number": "",
        "proforma_invoice_number": "",
        "tax_invoice_number": "",
        "receipt_number": "",
        "notes": notes,
        "due_date": due_date,
        "paid": paid,
        "source_mode": "",
        "_sheet_title": sheet_title,
        "_sheet_row": sheet_row,
    }


def test_paid_payment_row_with_2025_invoice_and_2026_due_date_stays_visible_in_2026_payment_bucket():
    payload = _build_payment_transfer_state(
        [
            _row(
                invoice_date="15/12/2025",
                customer_name="אשקלון פולימרים",
                payment_direction="תשלום",
                amount="₪1,773.75",
                due_date="01/05/2026",
                paid="TRUE",
                sheet_title="תשלומים והעברות 2026",
                sheet_row=58,
                notes="3465",
            )
        ],
        sheet_names=["תשלומים והעברות 2026"],
        current_sheet="תשלומים והעברות 2026",
    )

    rows = payload["payments_2026_payment"]
    assert len(rows) == 1
    assert rows[0]["customer_name"] == "אשקלון פולימרים"
    assert rows[0]["amount"] == "₪1,773.75"
    assert rows[0]["paid"] == "TRUE"
    assert rows[0]["notes"] == "3465"


def test_payment_rows_are_bucketed_by_direction_from_all_rows_state():
    payload = _build_payment_transfer_state(
        [
            _row(
                invoice_date="01/05/2026",
                customer_name="נעלולי פלא 1",
                payment_direction="גביה",
                amount="₪100.00",
                due_date="10/05/2026",
                paid="FALSE",
                sheet_title="תשלומים והעברות 2026",
                sheet_row=10,
            ),
            _row(
                invoice_date="01/05/2026",
                customer_name="נעלולי פלא 2",
                payment_direction="תשלום",
                amount="₪200.00",
                due_date="12/05/2026",
                paid="FALSE",
                sheet_title="תשלומים והעברות 2026",
                sheet_row=11,
            ),
        ],
        sheet_names=["תשלומים והעברות 2026"],
        current_sheet="תשלומים והעברות 2026",
    )

    assert [row["customer_name"] for row in payload["payments_2026_collection"]] == ["נעלולי פלא 1"]
    assert [row["customer_name"] for row in payload["payments_2026_payment"]] == ["נעלולי פלא 2"]
