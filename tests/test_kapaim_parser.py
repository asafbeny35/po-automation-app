"""הזמנת רכש של כפיים בנייה (פריהד סגל פיתוח נדל"ן, הזמנה PO26001915 מ-24.09.2026).

אותו פורטל של רם אדרת, עם המלכודות המוכרות: סדר חזותי הפוך שספרות דבוקות
לעברית מתהפכות בו (181.5*33 → 33*181.5), הטלפון שלנו מודפס כ"איש הקשר אסף",
ו"מנהל פרויקט" נפרד מאיש הקשר שבבלוק הכתובת אבל זה אותו אדם.
"""
from __future__ import annotations

import pytest

from services.parsers import kapaim


RAW = (
    'מ"עב ן"לדנ חותיפ לגס דהירפ\n10 היעמש\nופי ביבא לת\n03-681-0497 :ןופלט\n'
    '514547918 :השרומ קסוע\n514547918 :מ"עמב קית רפסמ\n935988030 :םייוכינ קית .סמ\n'
    'web site: www.kpym.co.il\n'
    '24/09/26 :הנמזה ךיראת :חולשמל תבותכ :דובכל\n'
    '27/09/26 10:26 :הספדה ךיראת רגדא יבול ליטסקט תונורתפ בקעי ןב\n'
    'הווקת חתפ 35 לעפא 34 ןרוגה\n'
    '050-9033833 -דוד :ןופלט בקעי ןב ףסא :ידיל\n'
    '054-7720142 :דיינ ןופלט ,054-7720142 - ףסא :ןופלט\n'
    '037017779 :השרומ קסוע .סמ\n'
    'תרשואמ - PO26001915 רפסמ שכר תנמזה\n'
    'ריחמ כ"הס הדיחיל ריחמ תומכ הרעה רצומ רואת ט"קמ הרוש\n'
    "290.00 ILS 290.00 'חי 1.00 דחא ןוויכ - הלבוה 0-000001 1\n"
    "836.00 ILS 38.00 'חי 22.00 33*181.5 יפל תוגרדמ ןגמ 99-000181 2\n"
    '1,126.00 ללוכ ריחמ\n'
    '*PO26001915* :הדועת רפסמ דוקרב\n'
    '202.68 (18.00%) מ"עמ 60ש :םולשת יאנת\n'
    '89722 :םיטרפ\n'
    'ILS 1,328.68 ריחמ כ"הס\n'
    'רגדא יבול :טקיורפ\n'
    "קו'צרדנוב דוד :טקיורפ להנמ\n"
    '301046 :קפס \'סמ\n'
    'finance@kpym.co.il : ליימה תבותכל הרוחסה לבקמ לש המותח חולשמ תדועת ףורצב רוקמ תינובשח שיגהל שי *\n'
    'םולש ןדרי\nמ"עב ן"לדנ חותיפ לגס דהירפ'
)


@pytest.fixture(scope="module")
def parsed():
    return kapaim.parse(RAW)


# ── זיהוי ────────────────────────────────────────────────────────────────────

def test_the_order_is_detected():
    assert kapaim.detect(RAW) is True


@pytest.mark.parametrize("marker", ["514547918", "kpym.co.il", "לגס דהירפ"])
def test_each_anchor_alone_is_enough(marker):
    assert kapaim.detect(f"הזמנת רכש {marker}") is True


def test_an_unrelated_order_is_not_captured():
    assert kapaim.detect("הזמנת רכש של טובול 12345") is False


def test_a_ram_aderet_order_is_not_captured():
    """אותו פורטל — אסור שכפיים תחטוף הזמנה של רם אדרת."""
    assert kapaim.detect("תרדא םר 512947185 :פ.ח PO26006887") is False


# ── כותרת ────────────────────────────────────────────────────────────────────

def test_customer_matches_greeninvoice(parsed):
    customer_name, _items, header = parsed
    assert customer_name == "כפיים בנייה"
    assert header["customer_id"] == "514547918"


def test_po_number_and_date(parsed):
    _c, _i, header = parsed
    assert header["po_number"] == "PO26001915"
    assert header["po_date"] == "24/09/2026"


def test_payment_terms(parsed):
    _c, _i, header = parsed
    assert header["payment_terms_days"] == 60
    assert header["payment_terms_label"] == "שוטף + 60"


def test_the_finance_email_is_captured(parsed):
    _c, _i, header = parsed
    assert header["customer_email"] == "finance@kpym.co.il"


def test_the_office_phone_is_deliberately_dropped(parsed):
    """הטלפון הרלוונטי להזמנה הוא של דוד באתר (על איש הקשר); טלפון המשרד
    03-681-0497 לא ממולא — וגם אסור להעתיק את טלפון האתר ל-customer_phone,
    כי הסניטציה הגלובלית מוחקת איש קשר שהטלפון שלו זהה לטלפון הלקוח."""
    _c, _i, header = parsed
    assert header["customer_phone"] == ""


def test_project_and_delivery_address(parsed):
    _c, _i, header = parsed
    assert header["project"] == "לובי אדגר"
    assert header["delivery_address"] == "לובי אדגר, אפעל 35 פתח תקווה"


# ── איש קשר ──────────────────────────────────────────────────────────────────

def test_the_contact_is_david_with_the_pm_full_name(parsed):
    """"טלפון: דוד- 050-9033833" בבלוק הכתובת + "מנהל פרויקט: דוד בונדרצ'וק"
    — אותו אדם, השם המלא עדיף."""
    _c, _i, header = parsed
    assert header["contact_name"] == "דוד בונדרצ'וק"
    assert header["contact_phone"] == "050-9033833"


def test_our_own_phone_is_never_taken_as_the_contact(parsed):
    """"אסף - 054-7720142" במסמך הוא אנחנו."""
    _c, _i, header = parsed
    assert header["contact_phone"].replace("-", "") != "0547720142"


# ── פריטים ───────────────────────────────────────────────────────────────────

def test_two_items(parsed):
    _c, items, _h = parsed
    assert len(items) == 2


def test_descriptions_are_readable(parsed):
    _c, items, _h = parsed
    assert items[0].description == "הובלה - כיוון אחד"
    assert "מגן מדרגות לפי" in items[1].description


def test_dimensions_keep_their_printed_order(parsed):
    """181.5*33 — היפוך גורף היה הופך ל-33*181.5."""
    _c, items, _h = parsed
    assert "181.5*33" in items[1].description


def test_skus_quantities_prices_and_totals(parsed):
    _c, items, _h = parsed
    assert [(i.sku, i.quantity, i.unit_price, i.line_total) for i in items] == [
        ("0-000001", 1.0, 290.0, 290.0),
        ("99-000181", 22.0, 38.0, 836.0),
    ]
    assert all(item.unit == "יח'" for item in items)


# ── סכומים ───────────────────────────────────────────────────────────────────

def test_totals(parsed):
    _c, items, header = parsed
    assert header["subtotal"] == 1126.0
    assert header["vat"] == 202.68
    assert header["total"] == 1328.68
    assert round(sum(i.line_total for i in items), 2) == header["subtotal"]
