"""בדיקות לפרסר של תדהר בניה בע"מ.

הטקסט כאן הוא בדיוק מה ש-pdfplumber מחלץ מהזמנה אמיתית: עברית הפוכה, מספרים
ותאריכים תקינים. שדות שנקראים לפי קואורדינטות (כתובת ואיש קשר) נבדקים מול ה-PDF
עצמו בבדיקה נפרדת שמדלגת אם הקובץ לא זמין.
"""

from pathlib import Path

import pytest

from services.parsers.tidhar import _detect, parse


RAW_TEXT = """מ"עב הינב רהדת
4366516 הננער
09-7766110 :סקפ ,09-7766111 :ןופלט
512043266 :השרומ קסוע
558427548 :מ"עמב קית רפסמ
918139999 :םייוכינ קית .סמ
558427548 רפסמ םיקסוע דוחיאב מ"עמ יכרצל חוודמ
web site: https://www.tidhar.co.il/
18/08/26 :הנמזה ךיראת :חולשמל תבותכ :דובכל
18/08/26 19:17 :הספדה ךיראת הידרווג הל - ביבא לת ליטסקט תונורתפ בקעי ןב
roman.d@tidhar.co.il :ינורטקלא ראוד ופי - ביבא לת בקעי ןב ףסא :ידיל
ביבא לת 24 ןולייא קמע 0547720142 :דיינ ןופלט ,054-7720142 :ןופלט
ןמרוד ןמור :ידיל 037017779 :השרומ קסוע .סמ
0547170551 :ןופלט
0547170551 :דיינ ןופלט
POB2636264 רפסמ שכר תנמזה
רובע שרדנ ריחמ כ"הס הדיחיל ריחמ תומכ הקפסא .ת רצומ רואת קפס ט"קמ ט"קמ הרוש
ןמרוד ןמור 3,300.00 ILS 110.000 ר"מ 30.000 16/08/26 לילגל ריחמ 'מ 2 ךרוא 'מ 1 בחור תרנצ דודיבל פייפטיאווק QTP55550 -101111161 1
3,300.00 ללוכ ריחמ
62ש :םולשת יאנת
594.00 (18.00%) מ"עמ PJ243555 :טקיורפ 'סמ
הידרווג הל - ביבא לת :טקיורפ רואת
ILS 3,894.00 ריחמ כ"הס
סיגמ רהט :ןיינק
.תינובשחה תרתוכב קפסה לש פ.ח ףיסוהל שי .פ.ח ללוכ הנמזהב ןיוצמה טקיורפה םש רובע תינובשח קיפהל שי"""

REAL_PDF = Path("/Users/asafbeny/Downloads/POB2636264.pdf")


def test_detects_tidhar_by_reversed_name_domain_and_ids():
    assert _detect(RAW_TEXT)
    assert _detect('מ"עב הינב רהדת')
    assert _detect("web site: https://www.tidhar.co.il/")
    assert _detect("512043266 :השרומ קסוע")
    assert _detect("558427548 :מ\"עמב קית רפסמ")
    assert not _detect('מ"עב סוביס הינד')


def test_header_fields():
    customer_name, _, header = parse(RAW_TEXT)
    assert customer_name == 'תדהר בניה בע"מ'
    assert header["po_number"] == "POB2636264"
    assert header["po_date"] == "18/08/2026"
    # תדהר מדווחת באיחוד עוסקים — החשבונית מוצאת למספר האיחוד, לא לעוסק המורשה
    # של החברה (512043266) ובוודאי לא שלנו (037017779).
    assert header["customer_id"] == "558427548"
    assert header["extra"]["vat_group_number"] == "558427548"
    assert header["extra"]["dealer_number"] == "512043266"
    assert header["customer_id"] != "037017779"
    assert header["customer_email"] == "roman.d@tidhar.co.il"


def test_totals_are_not_confused_with_the_vat_file_number():
    _, _, header = parse(RAW_TEXT)
    assert header["subtotal"] == 3300.0
    assert header["vat"] == 594.0
    assert header["total"] == 3894.0
    assert header["extra"]["vat_rate"] == 18.0
    # הרגרסיה שהפרסר הגנרי ייצר: מספר תיק המע"מ נכנס לשדה המע"מ
    assert header["vat"] != 845724855.0


def test_payment_terms_read_from_the_reversed_shorthand():
    _, _, header = parse(RAW_TEXT)
    assert header["payment_terms_days"] == 62
    assert header["payment_terms_label"] == "שוטף + 62"


def test_project_and_buyer():
    _, _, header = parse(RAW_TEXT)
    assert header["extra"]["project_number"] == "PJ243555"
    assert header["extra"]["project_name"] == "תל אביב - לה גוורדיה"
    assert "PJ243555" in header["project"]
    assert header["extra"]["buyer_name"] == "טהר מגיס"


def test_item_row_columns_and_unreversed_description():
    _, items, _ = parse(RAW_TEXT)
    assert len(items) == 1
    item = items[0]
    assert item.sku == "QTP55550"
    assert item.description == "קוואיטפייפ לבידוד צנרת רוחב 1 מ' אורך 2 מ' מחיר לגליל"
    assert item.quantity == 30.0
    assert item.unit_price == 110.0
    assert item.line_total == 3300.0
    assert item.unit == 'מ"ר'


def test_contact_falls_back_to_the_site_contact_not_ours_without_a_pdf():
    """בלי ה-PDF אין קואורדינטות — ועדיין אסור לקחת את 'לידי: אסף בן יעקב' שלנו."""
    _, _, header = parse(RAW_TEXT)
    assert header["contact_name"] == "רומן דורמן"
    assert header["contact_phone"] == "0547170551"
    assert header["contact_phone"] not in {"0547720142", "054-7720142"}


def test_items_survive_a_second_row():
    second = (
        "סיגמ רהט 1,200.00 ILS 200.000 'חי 6.000 20/08/26 םיחפס תכרעמ ABC123 -101111162 2"
    )
    _, items, _ = parse(RAW_TEXT + "\n" + second)
    assert len(items) == 2
    assert items[1].sku == "ABC123"
    assert items[1].quantity == 6.0
    assert items[1].unit_price == 200.0
    assert items[1].line_total == 1200.0


@pytest.mark.skipif(not REAL_PDF.exists(), reason="ה-PDF המקורי לא זמין בסביבה הזו")
def test_delivery_block_from_the_real_pdf_uses_the_shipping_column():
    from services.po_parser import parse_purchase_order

    po = parse_purchase_order(str(REAL_PDF))
    assert (po.extra or {}).get("parser_name") == "tidhar"
    # הכתובת מגיעה מעמודת "כתובת למשלוח" ולא מהעמודה שלנו, ולא גולשת לתחתית הדף
    assert "עמק איילון 24" in po.delivery_address
    assert "בפורטל" not in po.delivery_address
    assert "בן יעקב" not in po.delivery_address
    assert po.contact_name == "רומן דורמן"
    assert po.contact_phone == "0547170551"
