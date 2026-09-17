"""הזמנת רכש של פלסן רא"ם — מסמך חשבשבת ERP (HashDoc 56590 מ-16.09.2026).

שלוש שורות פריט זהות (משלוחים נפרדים) חייבות להישאר שלוש; המשך התיאור יושב
בשורה נפרדת אחרי ספרת ת.מאושר; והמידות בתיאור (1.5*64) אסור שיתהפכו.
"""
from __future__ import annotations

import pytest

from services.parsers import plasan_raam


RAW = """515057412 השרומ קסוע
קתעה 56590 : 'סמ שכר תנמזה
13:27
ליטסקט תונורתפ בקעי ןב :קפס
16/09/2026 : ךיראת
2 הדובעה :תבותכ
1 : ןסחמ
הפיח
131920 : ההזמ
office@ben-yacov.com : ל"אוד
תילתע 34 ןרוגה דרשמ 20/09/2026 :םולשת יאנת
רשואמ.ת ת. כ"הס החנה % עבטמ ריחמ תומכ רואית ט"קמ סמ
ףסונ ךיראת 20/09/2026 15,360.00 0 ח"ש 160.00 96.00 בכעמ ללוכ ררוחמ רופא גג דופיר 1000058 1
1 1.5*64 הריעב
ףסונ ךיראת 20/09/2026 15,360.00 0 ח"ש 160.00 96.00 בכעמ ללוכ ררוחמ רופא גג דופיר 1000058 2
1 1.5*64 הריעב
ףסונ ךיראת 20/09/2026 15,360.00 0 ח"ש 160.00 96.00 בכעמ ללוכ ררוחמ רופא גג דופיר 1000058 3
1 1.5*64 הריעב
ןותלד -תמר הישעת קראפ ,מ"עב ןגוממ יחרזא בכר-מ"אר ןסלפ
46,080.00 :כ"הס
0.00 :החנה % 0.00
46,080.00 :מ"עמ ינפל כ"הס
8,294.40 :מ"עמ % 18.00
54,374.40 ח"שב םולשתל ךס
ךזבא ברימ ןינק םש
:ןינק ןופלט
"""


@pytest.fixture(scope="module")
def parsed():
    return plasan_raam.parse(RAW)


# ── זיהוי ────────────────────────────────────────────────────────────────────

def test_the_order_is_detected():
    assert plasan_raam.detect(RAW) is True


def test_detection_requires_the_tax_id():
    """'פלסן' לבד לא מספיק — פלסן סאסא היא לקוח אחר עם פרסר אחר."""
    assert plasan_raam.detect(RAW.replace("515057412", "999999999")) is False


def test_a_sasa_order_is_not_captured():
    assert plasan_raam.detect("Square meter order 123456-01 פלסן סאסא") is False


# ── כותרת ────────────────────────────────────────────────────────────────────

def test_the_customer_matches_the_book(parsed):
    customer_name, _items, header = parsed
    assert customer_name == "פלסאן ראמ"
    assert header["customer_id"] == "515057412"


def test_po_number_and_date(parsed):
    _customer, _items, header = parsed
    assert header["po_number"] == "56590"
    assert header["po_date"] == "16/09/2026"


def test_the_buyer_is_the_contact(parsed):
    _customer, _items, header = parsed
    assert header["contact_name"] == "מירב אבזך"


def test_the_delivery_address_is_the_haifa_site(parsed):
    _customer, _items, header = parsed
    assert header["delivery_address"] == "העבודה 2, חיפה"


# ── פריטים ───────────────────────────────────────────────────────────────────

def test_three_identical_lines_stay_three(parsed):
    """שלושה משלוחים של אותו פריט — הדה-דופ מבחין לפי מס' השורה."""
    _customer, items, _header = parsed
    assert len(items) == 3
    assert all(item.sku == "1000058" for item in items)


def test_the_item_line_fields(parsed):
    _customer, items, _header = parsed
    item = items[0]
    assert item.quantity == 96.0
    assert item.unit_price == 160.0
    assert item.line_total == 15360.0


def test_the_description_includes_the_continuation_line(parsed):
    _customer, items, _header = parsed
    assert items[0].description == "ריפוד גג אפור מחורר כולל מעכב בעירה 1.5*64"


def test_dimensions_are_not_reversed():
    """ההיפוך הנאיבי היה הופך את 1.5*64 ל-46*5.1."""
    assert plasan_raam._reverse_hebrew_tokens("1 1.5*64 הריעב") == "בעירה 1.5*64 1"


# ── סכומים ───────────────────────────────────────────────────────────────────

def test_totals_come_from_the_summary_page(parsed):
    _customer, _items, header = parsed
    assert header["subtotal"] == 46080.0
    assert header["vat"] == 8294.4
    assert header["total"] == 54374.4


def test_lines_sum_to_the_subtotal(parsed):
    _customer, items, header = parsed
    assert round(sum(item.line_total for item in items), 2) == header["subtotal"]


def test_totals_are_derived_when_the_summary_page_is_missing():
    first_page_only = RAW.split('46,080.00 :כ"הס')[0]
    _customer, items, header = plasan_raam.parse(first_page_only)
    assert len(items) == 3
    assert header["subtotal"] == 46080.0
    assert header["vat"] == 8294.4
    assert header["total"] == 54374.4
