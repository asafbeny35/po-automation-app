"""הזמנת רכש של רם אדרת הנדסה אזרחית בע"מ (הזמנה PO26006887, 24.09.2026).

שתי מלכודות: היפוך תווים גורף שהופך גם ספרות (מגרש 309 → 903, מתחם 67863 →
36876, ר-130 → ר-031); ושורת פריט שמשלבת מידות בתוך התיאור ושברה את הרגקס
הנוקשה שהחזיר "פריט לא זוהה".
"""
from __future__ import annotations

import pytest

from services.parsers import ram_aderet


RAW = (
    'מ"עב תיחרזא הסדנה תרדא םר\n12 למע\nןיעה שאר ,קפא קראפ\n4809234 דוקימ ,11542 ד.ת\n'
    '03-9015177 :סקפ ,03-9017710 :ןופלט\n512947185 :פ.ח\n558118352 :מ"עמב קית רפסמ\n'
    'web site: www.ram-aderet.co.il 924287543 :םייוכינ קית .סמ\ne-mail: office@ram-aderet.co.il\n'
    '558118352 רפסמ םיקסוע דוחיאב מ"עמ יכרצל חוודמ\n24/09/26 :הנמזה ךיראת :חולשמל תבותכ :דובכל\n'
    '24/09/26 12:55 :הספדה ךיראת עוציב-67863 םחתמ–309 דול יבצ רינ ליטסקט תונורתפ בקעי ןב\n'
    'ןיפירצ ןוויכמ הסינכה 34 ןרוגה\n0 53- ינסרמג קחצי/0 54-4233470 קרדב אסא /054-7300990 (לצרה) םהרבא תילתע\n'
    '5516051 ףסא :ידיל\nיבצ רינ 054- :דיינ ןופלט ,054-7720142 :ןופלט\n7720142\n037017779 :השרומ קסוע .סמ\n'
    'שכר תנמזה :הנמזה גוס\nקפסל החלשנ - PO26006887 רפסמ שכר תנמזה\nריחמ הרתי .ת\n'
    'ריחמ כ"הס תומכ הרעה רצומ רואת ט"קמ הרוש\nהדיחיל הקפסאל הקפסא\n'
    '3,900.00 ח"ש 78.00 \'חי 50.00 \'חי 50.00 בחור 207 הבוג וטנ - תודימ 24/09/26 הקפסא- 220-ג 130-ר דע תלדל צ"וד הנגה יוסיכ 8983001259 1\n'
    '91 - דבלב\n3,900.00 ללוכ ריחמ\n75ש :םולשת יאנת\n702.00 (18.00%) מ"עמ\n'
    '309 שרגמ -דול ימואלניבה עבורה :טקיורפ\nח"ש 4,602.00 ריחמ כ"הס קפסה י"ע הלבוה :הלבוה תטיש\n'
    'PD26003449 :השירד רפסמ\ninvoices@ram-aderet.co.il :תבותכל ליימב חולשל שי סמ תינובשח\n'
    ',הכרבב\nידרו לאירא\nמ"עב תיחרזא הסדנה תרדא םר'
)


@pytest.fixture(scope="module")
def parsed():
    return ram_aderet.parse(RAW)


# ── זיהוי ────────────────────────────────────────────────────────────────────

def test_the_order_is_detected():
    assert ram_aderet.detect(RAW) is True


@pytest.mark.parametrize("marker", ["רם אדרת", "512947185", "ram-aderet.co.il"])
def test_each_anchor_alone_is_enough(marker):
    assert ram_aderet.detect(f"הזמנת רכש {marker}") is True


def test_an_unrelated_order_is_not_captured():
    assert ram_aderet.detect("הזמנת רכש של טובול 12345") is False


# ── כותרת ────────────────────────────────────────────────────────────────────

def test_customer_matches_greeninvoice(parsed):
    customer_name, _items, header = parsed
    assert customer_name == 'רם אדרת הנדסה אזרחית בע"מ'
    assert header["customer_id"] == "512947185"


def test_po_number_and_date(parsed):
    _c, _i, header = parsed
    assert header["po_number"] == "PO26006887"
    assert header["po_date"] == "24/09/2026"


def test_payment_terms(parsed):
    _c, _i, header = parsed
    assert header["payment_terms_days"] == 75
    assert header["payment_terms_label"] == "שוטף + 75"


def test_the_invoice_email_is_preferred_over_office(parsed):
    _c, _i, header = parsed
    assert header["customer_email"] == "invoices@ram-aderet.co.il"


def test_the_contact_is_read_from_the_order_not_from_greeninvoice(parsed):
    """איש הקשר מופיע כ"טלפון (שם)" — /054-7300990 (הרצל). קודם הופיע חמוטל,
    ששלף מכרטיס הלקוח ב-GreenInvoice כי הפרסר החזיר איש קשר ריק."""
    _c, _i, header = parsed
    assert header["contact_name"] == "הרצל"
    assert header["contact_phone"] == "054-7300990"


def test_our_own_phone_is_never_taken_as_the_contact(parsed):
    _c, _i, header = parsed
    assert header["contact_phone"].replace("-", "") != "0547720142"


# ── מספרים דבוקים לעברית לא מתהפכים ──────────────────────────────────────────

def test_project_keeps_its_plot_number(parsed):
    """מגרש 309 — לא 903."""
    _c, _i, header = parsed
    assert "מגרש 309" in header["project"]
    assert "903" not in header["project"]


def test_delivery_address_keeps_its_numbers(parsed):
    """מתחם 67863 ומגרש 309 — הפרסר הישן הפך אותם ל-36876 ו-903."""
    _c, _i, header = parsed
    assert "309" in header["delivery_address"]
    assert "67863" in header["delivery_address"]
    assert "36876" not in header["delivery_address"]
    assert "903" not in header["delivery_address"]


def test_the_glued_reversal_helper_preserves_digits():
    assert ram_aderet._reverse_hebrew_tokens("םחתמ–309") == "309–מתחם"
    assert ram_aderet._reverse_hebrew_tokens("220-ג") == "ג-220"
    assert ram_aderet._reverse_hebrew_tokens("24/09/26") == "24/09/26"


# ── פריט ──────────────────────────────────────────────────────────────────────

def test_a_single_item_is_recognised(parsed):
    _c, items, _h = parsed
    assert len(items) == 1
    assert items[0].description != "פריט לא זוהה"


def test_item_sku_quantity_price_and_total(parsed):
    _c, items, _h = parsed
    item = items[0]
    assert item.sku == "8983001259"
    assert item.quantity == 50.0
    assert item.unit == "יח'"
    assert item.unit_price == 78.0
    assert item.line_total == 3900.0


def test_item_description_keeps_door_dimensions(parsed):
    """ר-130 ג-220 — הפרסר הישן הפך אותם ל-ר-031 ג-022."""
    _c, items, _h = parsed
    desc = items[0].description
    assert "כיסוי הגנה" in desc
    assert "ר-130" in desc
    assert "ג-220" in desc
    assert "031" not in desc and "022" not in desc


# ── סכומים ───────────────────────────────────────────────────────────────────

def test_totals(parsed):
    _c, _i, header = parsed
    assert header["subtotal"] == 3900.0
    assert header["vat"] == 702.0
    assert header["total"] == 4602.0
