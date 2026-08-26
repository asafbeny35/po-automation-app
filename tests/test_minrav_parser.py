"""מנרב בנייה — הזמנת רכש PO26005071, מהמסמך האמיתי.

הבדיקות רצות מול ה-PDF שב-tests/fixtures כדי שגם החיתוך לפי מיקום המילים ייבדק,
ולא רק הביטויים הרגולריים.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.parsers.common import extract_text_pdfplumber
from services.parsers.minrav import parse as parse_minrav
from services.po_parser import parse_purchase_order

FIXTURE = Path(__file__).parent / "fixtures" / "pdfs" / "minrav_PO26005071.pdf"


@pytest.fixture(scope="module")
def raw_text() -> str:
    return extract_text_pdfplumber(str(FIXTURE))


@pytest.fixture(scope="module")
def parsed(raw_text):
    result = parse_minrav(raw_text, str(FIXTURE))
    assert result is not None, "הפרסר סירב למסמך של מנרב"
    return result


# ── כותרת ────────────────────────────────────────────────────────────────────

def test_customer_matches_the_existing_catalog_record(parsed):
    """שם הקטלוג, כדי להתחבר לכרטיס הקיים ולא לפתוח לקוח כפול."""
    name, _, header = parsed
    assert name == "קבוצת מנרב"
    # השם המשפטי שהמסמך דורש לחשבונית נשמר לצד זה
    assert header["extra"]["legal_billing_name"] == 'קבוצת מנרב בע"מ - מנרב הנדסה ובנייה'


def test_billing_id_is_the_one_the_document_demands(parsed):
    """בעמוד ארבעה מספרים בני 9 ספרות. רק אחד מהם הוא ח.פ לחיוב."""
    _, _, header = parsed
    assert header["customer_id"] == "520034505"


@pytest.mark.parametrize("wrong_id, what", [
    ("557480977", "מספר תיק במע\"מ"),
    ("951025360", "מס. תיק ניכויים"),
    ("037017779", "העוסק המורשה של בן יעקב"),
])
def test_billing_id_is_not_one_of_the_decoys(parsed, wrong_id, what):
    _, _, header = parsed
    assert header["customer_id"] != wrong_id, f"נקלט {what}"


def test_order_number_and_date(parsed):
    _, _, header = parsed
    assert header["po_number"] == "PO26005071"
    assert header["po_date"] == "26/08/2026"


def test_payment_terms(parsed):
    _, _, header = parsed
    assert header["payment_terms_days"] == 60
    assert header["payment_terms_label"] == "שוטף + 60"


# ── כתובת ואנשי קשר: שלוש עמודות שנדחסות לשורה אחת ──────────────────────────

def test_delivery_address_is_the_site_not_our_own(parsed):
    _, _, header = parsed
    assert header["delivery_address"] == "מגדלי עמים טאוורס, דרך בית לחם 162, ירושלים"
    assert "בן יעקב" not in header["delivery_address"]
    assert "הגורן" not in header["delivery_address"]
    assert "קניין" not in header["delivery_address"]


def test_contact_is_theirs_not_ours(parsed):
    """באותה שורה יושבים 'לידי: אסף 0547720142' (שלנו) ו'הזמנות לידי: רון דרור'."""
    _, _, header = parsed
    assert header["contact_name"] == "רון דרור"
    assert header["contact_phone"] == "054-5081549"
    assert header["contact_phone"] not in ("054-7720142", "0547720142")


def test_project_and_company_phone(parsed):
    _, _, header = parsed
    assert header["project"] == "מגדלי עמים טאוורס"
    assert header["customer_phone"] == "08-8516262"


def test_invoice_email_is_the_one_invoices_must_go_to(parsed):
    _, _, header = parsed
    assert header["customer_email"] == "invoice@minrav.co.il"
    assert header["extra"]["buyer_email"] == "aviv.s@minrav.co.il"


def test_extra_reference_numbers(parsed):
    _, _, header = parsed
    assert header["extra"]["supplier_number"] == "36071462"
    assert header["extra"]["requisition_number"] == "PD26004650"
    assert header["extra"]["buyer_name"] == "אביב סבג"


# ── פריטים ───────────────────────────────────────────────────────────────────

def test_three_rows_kept_apart_by_their_size(parsed):
    """שלוש השורות חולקות מק"ט ותיאור. בלי המידה הן נראות זהות."""
    _, items, _ = parsed
    assert len(items) == 3
    assert [i.sku for i in items] == ["1151670141"] * 3
    assert [i.description for i in items] == [
        "הגנה לדלת לפי מידות 230/96",
        "הגנה לדלת לפי מידות 220/96",
        "הגנה לדלת לפי מידות 210/94",
    ]


def test_quantities_prices_and_units(parsed):
    _, items, _ = parsed
    assert [i.quantity for i in items] == [2.0, 229.0, 160.0]
    assert [i.unit_price for i in items] == [76.0, 76.0, 76.0]
    assert [i.line_total for i in items] == [152.0, 17404.0, 12160.0]
    assert {i.unit for i in items} == {"יח'"}


def test_totals_are_internally_consistent(parsed):
    _, items, header = parsed
    assert round(sum(i.line_total for i in items), 2) == header["subtotal"] == 29716.0
    assert header["vat"] == 5348.88 == round(header["subtotal"] * 0.18, 2)
    assert header["total"] == 35064.88 == round(header["subtotal"] + header["vat"], 2)
    for item in items:
        assert round(item.quantity * item.unit_price, 2) == item.line_total


# ── שילוב ותחימה ─────────────────────────────────────────────────────────────

def test_dispatcher_routes_to_minrav():
    po = parse_purchase_order(str(FIXTURE))
    assert (po.extra or {}).get("parser_name") == "minrav"
    assert po.customer_id == "520034505"
    assert po.total == 35064.88
    assert len(po.items) == 3


def test_text_only_fallback_matches_the_layout_result(raw_text):
    """בלי נתיב הקובץ אין קואורדינטות — הגיבוי הטקסטואלי חייב להסכים."""
    _, _, with_layout = parse_minrav(raw_text, str(FIXTURE))
    _, _, text_only = parse_minrav(raw_text)
    assert text_only["delivery_address"] == with_layout["delivery_address"]
    assert text_only["contact_phone"] == with_layout["contact_phone"]


@pytest.mark.parametrize("other", [
    'טובול ציוד וחומרי בניין\nהזמנת רכש 123\nסה"כ 100.00',
    'תדהר בניה\nהזמנת רכש TD-1\nסה"כ 100.00',
    "אשטרום בניה הזמנת רכש",
    "",
])
def test_rejects_documents_that_are_not_minrav(other):
    assert parse_minrav(other) is None
