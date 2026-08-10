from pathlib import Path
from unittest.mock import patch

import pytest

from services.parsers.haikon import parse


OCR_TEXT = '''516193430 (א. ק.) בע"מ ח.פ.
רחוב שדות 1 א. ת. מישור אדומים 9851106 טל': 02-6207170 פקס: 02-6207171
הזמנת רכש מס': 8293
פרוייקט: אלוני ים
זמנת: הגנה על דלתות שעה : 12:13
תאריך : 06/08/2026
מזהה : 20363
ע.מ. 37017779
מפתח פריט | שם פריט כמות מחיר מטבע % הנחה סה"כ
יח' מגן 1700-PRODO5 דלת / כנף 1270/2600 15.00 195.00 ש"ח | 0.00 2,925.00
0500
יח' מגן דלת / כנף -+1300/2600 28.00 195.00 ש"ח | 0.00 5,460.00
0500
1700-PRODO5 יח' מגן דלת / כנף 2120/1005 35.00 75.00 ש"ח 0.00 2,625.00
0500
סה"כ: 11,010.00
מקום אספקה: רחוב אלן טיורינג 3 הרצליה סה"כ לפני מע"מ: 11,010.00
מע"מ: 18.00 % | 1,981.80
סה"כ לתשלום: 12,991.80
תנאי תשלום: שוטף 90
לספק לרחוב אלן טיורינג 3 הרצליה /// עמית 054-8047504
הופק ע"י חשבשבת ERP'''


DRIVE_OCR_TEXT = '''היי, (א. ק. ) בע"מ
516193430 .9.n
רחוב שדות 1 א. ת. מישור אדומים 9851106 טל': 02-6207170 פקס: 02-6207171
לכבוד :
בן יעקב אסף
הזמנת רכש מס' :
פרוייקט: אלוני ים
הזמנת: הגנה על דלתות
8293
מפתח פריט שם פריט
כמות
מחיר
0500
0500
0500
PROD05-1700 יח' מגן דלת / כנף 1270/2600 PROD05-1700 יח' מגן דלת / כנף -+1300/2600
PROD05-1700 יח' מגן דלת / כנף 2120/1005
195.00
15.00
195.00
28.00
75.00
35.00
מקום אספקה: רחוב אלן טיורינג 3 הרצליה
תאריך אספקה: תנאי תשלום: שוטף 90
שעה
תאריך
12:13:
06/08/2026:
מטבע % הנחה
סהייכ
שייח
שייח
שייח
2,925.00
0.00
5,460.00
0.00
2,625.00
0.00
סה"כ: 11,010.00
הנחה: 0.00
סה"כ לפני מע"מ: 11,010.00
18.00 %
מע"מ: 1,981.80
סה"כ לתשלום: 12,991.80
לספק לרחוב אלן טיורינג 3 הרצליה /// עמית 054-8047504
הופק ע"י חשבשבת ERP'''


def test_haikon_parser_extracts_all_three_product_rows():
    result = parse(OCR_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == 'הייקון (א.ק.) בע"מ'
    assert header["customer_id"] == "516193430"
    assert header["customer_phone"] == "02-6207170"
    assert header["po_number"] == "8293"
    assert header["po_date"] == "06/08/2026"
    assert header["project"] == "אלוני ים"
    assert header["delivery_address"] == "רחוב אלן טיורינג 3 הרצליה"
    assert header["contact_name"] == "עמית"
    assert header["contact_phone"] == "054-8047504"
    assert header["payment_terms_days"] == 90
    assert header["payment_terms_label"] == "שוטף 90"
    assert header["subtotal"] == 11010.0
    assert header["vat"] == 1981.8
    assert header["total"] == 12991.8
    assert header["extra"]["supplier_id"] == "37017779"
    assert len(items) == 3

    assert [item.description for item in items] == [
        "יח' מגן דלת / כנף 1270/2600",
        "יח' מגן דלת / כנף +-1300/2600",
        "יח' מגן דלת / כנף 2120/1005",
    ]
    assert [item.quantity for item in items] == [15.0, 28.0, 35.0]
    assert [item.unit_price for item in items] == [195.0, 195.0, 75.0]
    assert [item.line_total for item in items] == [2925.0, 5460.0, 2625.0]
    assert all(item.sku == "1700-PROD050500" for item in items)
    assert all(item.unit == "יח'" for item in items)


def test_haikon_parser_rejects_unrelated_purchase_order():
    assert parse('חברה אחרת בע"מ\nהזמנת רכש מס: 8293') is None


def test_haikon_parser_reassembles_drive_ocr_column_blocks():
    result = parse(DRIVE_OCR_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == 'הייקון (א.ק.) בע"מ'
    assert header["po_number"] == "8293"
    assert header["po_date"] == "06/08/2026"
    assert header["delivery_address"] == "רחוב אלן טיורינג 3 הרצליה"
    assert header["total"] == 12991.8
    assert [item.quantity for item in items] == [15.0, 28.0, 35.0]
    assert [item.unit_price for item in items] == [195.0, 195.0, 75.0]
    assert [item.line_total for item in items] == [2925.0, 5460.0, 2625.0]
    assert all(item.sku == "1700-PROD050500" for item in items)


def test_haikon_parser_is_used_by_purchase_order_pipeline():
    from services.po_parser import parse_purchase_order

    with (
        patch("services.po_parser.extract_text_pdfplumber", return_value=OCR_TEXT),
        patch("services.po_parser.ocr_pdf", return_value=OCR_TEXT),
    ):
        purchase_order = parse_purchase_order(Path("/fake/haikon-8293.pdf"))

    assert purchase_order is not None
    assert purchase_order.extra["parser_name"] == "haikon"
    assert purchase_order.po_number == "8293"
    assert len(purchase_order.items) == 3


@pytest.mark.asyncio
async def test_haikon_payment_terms_from_po_survive_customer_enrichment(monkeypatch):
    import app

    class FakeGreenInvoiceClient:
        def __init__(self, **kwargs):
            pass

        async def get_existing_customer_details(self, customer_id):
            return {"name": 'הייקון (א.ק) בע"מ', "paymentTerms": 60}

        def _resolve_payment_days_for_customer(self, **kwargs):
            return 60

        def _merge_customer_data_into_po(self, po, customer_data):
            po.payment_terms_days = 60
            po.payment_terms_label = "שוטף + 60"
            return po

    monkeypatch.setattr(app, "GreenInvoiceClient", FakeGreenInvoiceClient)
    po = app.PurchaseOrderData(
        customer_name='הייקון (א.ק.) בע"מ',
        customer_id="516193430",
        payment_terms_days=90,
        payment_terms_label="שוטף 90",
        extra={"parser_name": "haikon"},
    )

    enriched = await app._enrich_po_for_process(
        po,
        {"base_url": "https://example.test", "api_key": "key", "api_secret": "secret"},
    )

    assert enriched.payment_terms_days == 90
    assert enriched.payment_terms_label == "שוטף 90"
