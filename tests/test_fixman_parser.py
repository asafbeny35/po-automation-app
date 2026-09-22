"""הזמנת רכש של פיקסמן בנייה (הזמנה 186/4492 מ-22.09.2026).

שלוש המלכודות של המסמך: האות נ' מחולצת כ-(cid:170); המק"ט נשבר לשתי שורות או
נדבק למילה העברית האחרונה; ואיש הקשר המודפס הוא הטלפון שלנו עצמנו.
"""
from __future__ import annotations

import pytest

from services.parsers import fixman


RAW = """1 22/09/26 11:50:00
רוקמ - 186/4492 'סמ ה(cid:170)מזה - םיאבול 3 שירפ לאי(cid:170)ד טקיורפ
רתא יטרפ דובכל
םיאבול 3 שירפ לאי(cid:170)ד בקעי ןב :רשק שיא ליטסקט תו(cid:170)ורתפ בקעי ןב
3 שירפ לאי(cid:170)ד 34 ןרוגה
ביבא לת 054-7720142 :דיי(cid:170) תילתע
054-7720142 :לט
תורעה שרד(cid:170) תולע ריחמ תומכ טירפ
ךיראתל מ"י רואת QRLabel ד1ו2ק
500.00 500.000 1 'חי הקירפ אלל הלבוה --070410
013
1,323.00 21.000 63 'חי 90 בחור תובכש 2 ורפ פטס הגרדמ ןגמ-STEPRO050
880.00 110.000 8 'חי 2.5*1.5 םיטסדופ -STEPSPE
050
מ"עמ ללוכ אל 2,703.00 :ה(cid:170)מזה כ"הס 30+ףטוש :םולשת יא(cid:170)ת
(514946664 .פ.ח) מ"עב הי(cid:170)ב ןמסקיפ :רובע קיפהל שי תי(cid:170)ובשח ***
ןכדעל א(cid:170) םירסוח שיו הדימב
שכרה ת(cid:170)מזה רפסמ תא תוי(cid:170)ובשחה לע םושרל שי
המותח חולשמ תדועת תוי(cid:170)ובשחל ףרצל שי
billing@fixman-ltd.co.il ליימל חולשל שי תוי(cid:170)ובשח
יתפצ ידע :י"ע הקפוה וז ה(cid:170)מזה
"""


@pytest.fixture(scope="module")
def parsed():
    return fixman.parse(RAW)


# ── הגליף השבור ──────────────────────────────────────────────────────────────

def test_the_broken_nun_glyph_is_restored():
    assert fixman._normalize_cids("ה(cid:170)מזה") == "הנמזה"


def test_an_unknown_cid_stays_visible():
    """עדיף (cid:184) גלוי בתיאור שאסף ידווח עליו מאשר אות שנעלמת בשקט."""
    assert fixman._normalize_cids("א(cid:184)ב") == "א(cid:184)ב"


# ── זיהוי ────────────────────────────────────────────────────────────────────

def test_the_order_is_detected_despite_the_broken_glyphs():
    assert fixman.detect(RAW) is True


@pytest.mark.parametrize("marker", ["514946664", "billing@fixman-ltd.co.il"])
def test_each_anchor_alone_is_enough(marker):
    assert fixman.detect(f"הזמנת רכש {marker}") is True


def test_an_unrelated_order_is_not_captured():
    assert fixman.detect("הזמנת רכש של טובול 12345") is False


# ── כותרת ────────────────────────────────────────────────────────────────────

def test_the_customer_matches_greeninvoice(parsed):
    customer_name, _items, header = parsed
    assert customer_name == "פיקסמן בנייה"
    assert header["customer_id"] == "514946664"


def test_po_number_with_slash(parsed):
    _c, _i, header = parsed
    assert header["po_number"] == "186/4492"


def test_po_date(parsed):
    _c, _i, header = parsed
    assert header["po_date"] == "22/09/2026"


def test_project_and_site_address(parsed):
    _c, _i, header = parsed
    assert header["project"] == "דניאל פריש 3 לובאים"
    assert header["delivery_address"] == "דניאל פריש 3 לובאים, תל אביב"


def test_payment_terms(parsed):
    _c, _i, header = parsed
    assert header["payment_terms_days"] == 30
    assert header["payment_terms_label"] == "שוטף + 30"


def test_the_billing_email_is_captured(parsed):
    _c, _i, header = parsed
    assert header["customer_email"] == "billing@fixman-ltd.co.il"


def test_the_contact_is_the_orderer_not_ourselves(parsed):
    """"איש קשר: בן יעקב 054-7720142" במסמך הוא אנחנו — המזמינה האמיתית
    חתומה בתחתית."""
    _c, _i, header = parsed
    assert header["contact_name"] == "עדי צפתי"
    assert header["contact_phone"] == ""


# ── פריטים ───────────────────────────────────────────────────────────────────

def test_three_items(parsed):
    _c, items, _h = parsed
    assert len(items) == 3


def test_descriptions_are_readable(parsed):
    _c, items, _h = parsed
    assert [item.description for item in items] == [
        "הובלה ללא פריקה",
        "מגן מדרגה סטפ פרו 2 שכבות רוחב 90",
        "פודסטים 1.5*2.5",
    ]


def test_a_two_line_numeric_sku_is_joined_with_a_dash(parsed):
    _c, items, _h = parsed
    assert items[0].sku == "070410-013"


def test_a_sku_glued_to_the_hebrew_description_is_split(parsed):
    _c, items, _h = parsed
    assert items[1].sku == "STEPRO050"
    assert "STEPRO" not in items[1].description


def test_a_two_line_alpha_sku_is_joined_without_a_dash(parsed):
    """STEPSPE + 050 = STEPSPE050, כמו אחיו STEPRO050 בשורה שמעליו."""
    _c, items, _h = parsed
    assert items[2].sku == "STEPSPE050"


def test_quantities_prices_and_lines(parsed):
    _c, items, _h = parsed
    assert [(i.quantity, i.unit_price, i.line_total) for i in items] == [
        (1.0, 500.0, 500.0),
        (63.0, 21.0, 1323.0),
        (8.0, 110.0, 880.0),
    ]
    assert all(item.unit == "יח'" for item in items)


def test_dimensions_keep_their_printed_order(parsed):
    """pdfplumber הופך את ריצת המידות — המקור הוא 1.5*2.5, לא 2.5*1.5."""
    _c, items, _h = parsed
    assert "1.5*2.5" in items[2].description


# ── סכומים ───────────────────────────────────────────────────────────────────

def test_totals_and_derived_vat(parsed):
    """"סה"כ הזמנה 2,703.00 לא כולל מע"מ" — המע"מ תמיד נגזר ב-18%."""
    _c, items, header = parsed
    assert header["subtotal"] == 2703.0
    assert header["vat"] == 486.54
    assert header["total"] == 3189.54
    assert round(sum(i.line_total for i in items), 2) == header["subtotal"]
