"""הזמנת רכש של אלמוג ב.ז — שורת הפריט, היחידה, והמרת הגלילים.

הפרסר נעל את שורת הפריט בתבנית אחת שדרשה ש-QUIETPIPE יהיה מוקף ברווחים.
כשהספק הוסיף לתיאור את מידות הגליל — (2*1 מ') — הסדר החזותי הפך ל-('מQUIETPIPE,
ההתאמה נכשלה, וכל הזמנה חזרה עם "פריט לא זוהה".
"""
from __future__ import annotations

import re

import pytest

from services.greeninvoice import GreenInvoiceClient
from services.models import POItem, PurchaseOrderData
from services.parsers import almogim


# ── שחזור הסדר הלוגי מתוך המיקומים בעמוד ─────────────────────────────────────

def _visual(*words):
    """מקבל (x0, x1, טקסט) בסדר ימין→שמאל כפי שהם בעמוד."""
    return almogim._logical_text_from_visual(list(words))


def test_an_embedded_latin_run_is_restored_to_its_order():
    assert _visual(
        (481.3, 497.4, "יריעה"), (453.5, 479.2, "אקוסטית"), (448.9, 451.4, "-"),
        (433.2, 446.8, "(2*1"), (391.6, 431.3, "QUIETPIPE"),
        (387.1, 391.6, "מ"), (383.5, 387.3, "('"),
    ) == "יריעה אקוסטית - QUIETPIPE (2*1 מ')"


def test_plain_hebrew_keeps_its_order():
    assert _visual((100.0, 140.0, "יריעה"), (60.0, 95.0, "אקוסטית")) == "יריעה אקוסטית"


def test_brackets_are_mirrored_back():
    """בפריסה RTL הסוגריים מוצגים משוקפים — צריך להחזירם."""
    # התיבות רחוקות זו מזו ולכן נשמר ביניהן רווח; מה שנבדק הוא השיקוף עצמו
    assert _visual((50.0, 54.0, "("), (20.0, 24.0, ")")) == ") ("


def test_adjacent_boxes_are_joined_without_a_space():
    joined = _visual((387.1, 391.6, "מ"), (383.5, 387.3, "('"))
    assert joined == "מ')"
    assert " " not in joined


# ── שורת הפריט ───────────────────────────────────────────────────────────────

RAW_ITEM_LINE = (
    "3,960.00 ח\"ש 66.00 ר'מ 60.00 ר'מ 60.00 10/09/26 "
    "('מQUIETPIPE (2*1 - תיטסוקא העירי 356640153 1"
)


def test_the_text_fallback_no_longer_needs_spaces_around_quietpipe():
    items = almogim._extract_items([RAW_ITEM_LINE])
    assert len(items) == 1
    item = items[0]
    assert item.description != "פריט לא זוהה"
    assert item.sku == "356640153"
    assert item.quantity == 60.0
    assert item.unit_price == 66.0
    assert item.line_total == 3960.0


def test_the_fallback_unit_is_square_meters():
    assert almogim._extract_items([RAW_ITEM_LINE])[0].unit == "מ'ר"


def test_a_header_line_is_not_mistaken_for_an_item():
    header = "ריחמ כ\"הס הדיחיל ריחמ הקפסאל הרתי תומכ הקפסא .ת רצומ רואת ט\"קמ הרוש"
    assert almogim._extract_items([header])[0].description == "פריט לא זוהה"


# ── איש הקשר ─────────────────────────────────────────────────────────────────

def test_a_space_separated_contact_is_read():
    """ההזמנה כותבת "עיאד 0547957596" בלי מקף מפריד."""
    lines = [
        "14/09/26 11:05 :הספדה ךיראת השמ תירק תובוחר ליטסקט תונורתפ- ףסא בקעי ןב",
        "םירופיכה םוי בוחר דיל 34 ןרוגה",
        "0547957596 דאיע 303431 תילתע",
    ]
    address, name, phone = almogim._extract_delivery_and_contact(lines, "04-8577080")
    assert address.startswith("רחובות קרית משה")
    assert name == "עיאד"
    assert phone == "0547957596"


# ── שם הלקוח ─────────────────────────────────────────────────────────────────

def test_the_customer_name_matches_the_one_in_greeninvoice():
    """הערך הקודם היה חברה שלא קיימת במאגר; ההזמנות הקודמות כולן תחת השם הזה."""
    assert almogim.CUSTOMER_NAME == "אלמוג ב.ז בנייה והשקעות בעמ"


# ── המרת הגלילים ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return GreenInvoiceClient.__new__(GreenInvoiceClient)


def _quietpipe_po(description):
    return PurchaseOrderData(
        po_number="PO26004068",
        customer_name=almogim.CUSTOMER_NAME,
        items=[POItem(description=description, sku="356640153", unit="מ'ר",
                      quantity=60.0, unit_price=66.0, line_total=3960.0)],
    )


@pytest.mark.parametrize("description", [
    "יריעה אקוסטית - QUIETPIPE (2*1 מ')",
    "יריעה אקוסטית - Quietpipe",
    "QUIET PIPE sheet",
    "יריעת אקוסטיפייפ משתיקה לצנרת",
])
def test_every_spelling_is_recognised_as_a_quietpipe_sheet(client, description):
    """אלמוג מזמינה בשם הלועזי — בלי זה 60 מ\"ר יוצאים כ-60 יריעות."""
    assert client._rows_for_delivery(_quietpipe_po(description))[0]["quantity"] == 30.0


def test_the_invoice_still_bills_the_ordered_square_meters(client):
    po = _quietpipe_po("יריעה אקוסטית - QUIETPIPE (2*1 מ')")
    invoice_row = client._rows_for_invoice(po)[0]
    assert invoice_row["quantity"] == 60.0
    assert invoice_row["quantity"] * invoice_row["price"] == 3960.0


def test_an_unrelated_product_is_not_converted(client):
    po = _quietpipe_po("סיילנטופ - יריעה אקוסטית לקירות גבס")
    po.items[0].sku = "SLT-1"
    assert client._rows_for_delivery(po)[0]["quantity"] == 60.0
