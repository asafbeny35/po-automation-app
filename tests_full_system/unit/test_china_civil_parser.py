from pathlib import Path
from unittest.mock import patch

from services.parsers.china_civil import parse


RAW_TEXT = '''1 10/08/26 11:14:00
רוקמ - 1009/7091 'סמ הנמזה - Rishon - ןויצל ןושאר טקיורפ
רתא יטרפ דובכל
Rishon - ןויצל ןושאר ליטסקט תונורתפ בקעי ןב
2 םריח עצבמ
ןויצל ןושאר
052-734-3004 יניפ,050-755-1303 יפא :לט
תורעה שרדנ תולע ריחמ תומכ טירפ
ךיראתל מ"י רואת QRLabelד1ו2ק
7,252.00 74.000 98 'חי אלל רוד ורפ - תלד ןגמ - רוד ורפ -PROD5050
הנקתה
מ"עמ ללוכ אל 7,252.00:הנמזה כ"הס 15+ףטוש :םולשת יאנת
560024093 פ.ח -גנירינ'גניא ליביס הניי'צ :רובע קיפהל שי תינובשח ***
.תמתוחו המיתחב ומעטמ ךמסומ גיצנ/טקיורפ להנמ םיתחהל דיפקהל שי .1
.חולשמה תדועתל הנמזהה קתוע תא ףרצלשי .2
.תינובשחל המותחה חולשמה תדועת קתוע תא ףרצל שי .3
קפסל רזחות ,ליעלש םיללכה יפ לע אל שגותש תינובשח .4
Eyal malaiev :י"ע הקפוה וז הנמזה'''


def test_china_civil_parser_extracts_complete_purchase_order():
    purchase_order = parse(RAW_TEXT)
    assert purchase_order is not None

    assert purchase_order.customer_name == "צ'יינה סיביל אינג'נירינג"
    assert purchase_order.customer_id == "560024093"
    assert purchase_order.po_number == "1009/7091"
    assert purchase_order.po_date == "10/08/2026"
    assert purchase_order.project == "ראשון לציון - Rishon"
    assert purchase_order.delivery_address == "מבצע חירם 2, ראשון לציון"
    assert purchase_order.contact_name == "אפי"
    assert purchase_order.contact_phone == "050-755-1303"
    assert purchase_order.secondary_contact_name == "פיני"
    assert purchase_order.secondary_contact_phone == "052-734-3004"
    assert purchase_order.payment_terms_days == 15
    assert purchase_order.payment_terms_label == "שוטף + 15"
    assert purchase_order.subtotal == 7252.0
    assert purchase_order.vat == 1305.36
    assert purchase_order.total == 8557.36
    assert purchase_order.extra["site_name"] == "ראשון לציון - Rishon"
    assert purchase_order.extra["prices_exclude_vat"] is True
    assert purchase_order.extra["source_template"] == "ZivPdf"
    assert purchase_order.extra["order_author"] == "Eyal malaiev"

    assert len(purchase_order.items) == 1
    item = purchase_order.items[0]
    assert item.sku == "PROD5050"
    assert item.description == "פרו דור - מגן דלת - פרו דור ללא התקנה"
    assert item.unit == "יח'"
    assert item.quantity == 98.0
    assert item.unit_price == 74.0
    assert item.line_total == 7252.0


def test_china_civil_parser_rejects_other_zivpdf_customer():
    unrelated = RAW_TEXT.replace("560024093", "512345678").replace("הניי'צ", "הרבח")
    assert parse(unrelated) is None


def test_china_civil_parser_is_used_by_purchase_order_pipeline():
    from services.po_parser import parse_purchase_order

    with (
        patch("services.po_parser.extract_text_pdfplumber", return_value=RAW_TEXT),
        patch("services.po_parser.ocr_pdf", return_value=RAW_TEXT),
    ):
        purchase_order = parse_purchase_order(Path("/fake/china-civil-1009-7091.pdf"))

    assert purchase_order is not None
    assert purchase_order.extra["parser_name"] == "china_civil"
    assert purchase_order.customer_id == "560024093"
    assert purchase_order.items[0].description.endswith("ללא התקנה")
