from pathlib import Path
from unittest.mock import patch

import pytest

from services.parsers.mister_fix import parse


OCR_TEXT = '''Page 1 of 1
כרמית מיסטר פיקס בע"מ ת.ד 3530 קיסריה
קיסריה 3079579 טלפון: 04-6178906 עוסק מורשה: 511493306
מספר תיק במע"מ: 557586161 מס. תיק ניכויים: 917097834
מדווח לצרכי מע"מ באיחוד עוסקים מספר 557586161
הדפסת הזמנת רכש
מיסטר פיקס' MF
web site: www.carmit-mrfix.co.il
e-mail: marketing@mrfix.co.il
לכבוד:
בן יעקב אסף
מס. עוסק מורשה: 037017779
תאריך הזמנה: 31/08/26 תאריך הדפסה: 15:24 31/08/26
הזמנת רכש מספר PO26001915 - מחכה לאישור
שורה מקייט
תאור מוצר
1 | 26066| פס איטום 50 מ"מ - 25 מטר אורך ללא
דבק
2|26067| פס איטום 70 מ"מ - 25 מטר אורך ללא
דבק
ברקוד מספר תעודה: *PO26001915* תנאי תשלום: ש60
מס' ספק: 400266
מהדורה נוכחית: 1
ת. אספקה
כמות
מחיר ליחידה
סה"כ מחיר
5,940.00 ILS 11.000 n' 540.00 31/08/26
3,276.00 ILS 13.000 'n' 252.00 31/08/26
מחיר כולל
מע"מ (18.00%)
סהייכ מחיר
9,216.00
1,658.88
ILS 10,874.88
הופק באמצעות Priority @ - פריוריטי סופטוור בע"מ'''


def test_mister_fix_parser_extracts_complete_purchase_order():
    result = parse(OCR_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == 'כרמית מיסטר פיקס בע"מ'
    assert header["customer_id"] == "511493306"
    assert header["customer_phone"] == "04-6178906"
    assert header["customer_email"] == "marketing@mrfix.co.il"
    assert header["po_number"] == "PO26001915"
    assert header["po_date"] == "31/08/2026"
    assert header["delivery_address"] == ""
    assert header["contact_name"] == ""
    assert header["payment_terms_days"] == 60
    assert header["payment_terms_label"] == "שוטף + 60"
    assert header["subtotal"] == 9216.0
    assert header["vat"] == 1658.88
    assert header["total"] == 10874.88

    assert len(items) == 2
    assert [item.sku for item in items] == ["26066", "26067"]
    assert [item.description for item in items] == [
        'פס איטום 50 מ"מ - 25 מטר אורך ללא דבק',
        'פס איטום 70 מ"מ - 25 מטר אורך ללא דבק',
    ]
    assert [item.quantity for item in items] == [540.0, 252.0]
    assert [item.unit_price for item in items] == [11.0, 13.0]
    assert [item.line_total for item in items] == [5940.0, 3276.0]
    assert all(item.unit == "יח'" for item in items)

    extra = header["extra"]
    assert extra["customer_address"] == "ת.ד 3530 קיסריה, קיסריה 3079579"
    assert extra["vat_group_id"] == "557586161"
    assert extra["withholding_file_number"] == "917097834"
    assert extra["supplier_customer_number"] == "400266"
    assert extra["recipient_business_id"] == "037017779"
    assert extra["document_barcode"] == "PO26001915"
    assert extra["document_status"] == "מחכה לאישור"
    assert extra["current_revision"] == "1"
    assert extra["requested_delivery_date"] == "31/08/2026"
    assert extra["item_delivery_dates"] == [
        {"sku": "26066", "date": "31/08/2026"},
        {"sku": "26067", "date": "31/08/2026"},
    ]


def test_mister_fix_parser_supports_visual_order_numeric_rows():
    visual_order_text = OCR_TEXT.replace(
        "5,940.00 ILS 11.000 n' 540.00 31/08/26",
        "31/08/26 540.00 יח' 11.000 ILS 5,940.00",
    ).replace(
        "3,276.00 ILS 13.000 'n' 252.00 31/08/26",
        "31/08/26 252.00 יח' 13.000 ILS 3,276.00",
    )

    result = parse(visual_order_text)
    assert result is not None
    assert [item.line_total for item in result[1]] == [5940.0, 3276.0]


def test_mister_fix_parser_rejects_unrelated_or_inconsistent_documents():
    assert parse('חברה אחרת בע"מ\nהזמנת רכש PO123\nסה"כ 100') is None
    inconsistent = OCR_TEXT.replace("5,940.00 ILS 11.000", "5,900.00 ILS 11.000")
    assert parse(inconsistent) is None
    conflicting_barcode = OCR_TEXT.replace("*PO26001915*", "*PO26001916*")
    assert parse(conflicting_barcode) is None


def test_mister_fix_parser_is_used_by_purchase_order_pipeline():
    from services.po_parser import parse_purchase_order

    with (
        patch("services.po_parser.extract_text_pdfplumber", return_value=""),
        patch("services.po_parser.ocr_pdf", return_value=OCR_TEXT),
    ):
        purchase_order = parse_purchase_order(Path("/fake/mister-fix-PO26001915.pdf"))

    assert purchase_order is not None
    assert purchase_order.extra["parser_name"] == "mister_fix"
    assert purchase_order.po_number == "PO26001915"
    assert purchase_order.customer_id == "511493306"
    assert len(purchase_order.items) == 2


@pytest.mark.asyncio
async def test_mister_fix_payment_terms_from_po_survive_customer_enrichment(monkeypatch):
    import app

    class FakeGreenInvoiceClient:
        def __init__(self, **kwargs):
            pass

        async def get_existing_customer_details(self, customer_id):
            return {"name": "מיסטר פיקס", "paymentTerms": 30}

        def _resolve_payment_days_for_customer(self, **kwargs):
            return 30

        def _merge_customer_data_into_po(self, po, customer_data):
            po.payment_terms_days = 30
            po.payment_terms_label = "שוטף + 30"
            return po

    monkeypatch.setattr(app, "GreenInvoiceClient", FakeGreenInvoiceClient)
    po = app.PurchaseOrderData(
        customer_name='כרמית מיסטר פיקס בע"מ',
        customer_id="511493306",
        payment_terms_days=60,
        payment_terms_label="שוטף + 60",
        extra={"parser_name": "mister_fix"},
    )

    enriched = await app._enrich_po_for_process(
        po,
        {"base_url": "https://example.test", "api_key": "key", "api_secret": "secret"},
    )

    assert enriched.payment_terms_days == 60
    assert enriched.payment_terms_label == "שוטף + 60"
