"""המרת מ"ר לגלילים בתעודת משלוח.

גליל קוואיטפייפ אחד הוא 2 מ"ר. חלק מהלקוחות מזמינים במ"ר וחלק בגלילים.
תעודת המשלוח מתארת מה יוצא פיזית מהמחסן ולכן היא בגלילים, והחשבונית נשארת
ביחידה המסחרית שהוזמנה — אחרת הסכום משתנה.

הזמנת טובול 1201245537 יצאה כתעודה על 60 יריעות במקום 30, פי שניים מהסחורה.
"""
from __future__ import annotations

import pytest

from services.greeninvoice import GreenInvoiceClient
from services.models import POItem, PurchaseOrderData


@pytest.fixture
def client():
    return GreenInvoiceClient.__new__(GreenInvoiceClient)


def _po(items):
    return PurchaseOrderData(po_number="TEST-1", customer_name="בדיקה", items=items)


def _sheet(qty, unit, description="יריעת אקוסטיפייפ משתיקה לצנרת", sku="103000580", price=52.0):
    return POItem(description=description, sku=sku, unit=unit,
                  quantity=qty, unit_price=price, line_total=qty * price)


# ── ההמרה עצמה ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sqm, rolls", [(60, 30), (2, 1), (200, 100), (52, 26)])
def test_square_meters_become_rolls(client, sqm, rolls):
    row = client._rows_for_delivery(_po([_sheet(sqm, "מר")]))[0]
    assert row["quantity"] == float(rolls)
    assert f"{rolls} גלילים" in row["description"]
    assert f'{sqm:g} מ"ר' in row["description"]


@pytest.mark.parametrize("unit", ["מר", 'מ"ר', "מ״ר", "מטר מרובע", "מטרים מרובעים"])
def test_every_spelling_of_square_meter_is_recognised(client, unit):
    row = client._rows_for_delivery(_po([_sheet(60, unit)]))[0]
    assert row["quantity"] == 30.0


# ── מתי אסור להמיר ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("unit", ["יח'", "יח׳", "יחידה", "גליל", "גלילים", ""])
def test_an_order_already_in_rolls_is_left_alone(client, unit):
    """לקוח שהזמין 60 גלילים מקבל 60, לא 30."""
    row = client._rows_for_delivery(_po([_sheet(60, unit)]))[0]
    assert row["quantity"] == 60.0
    assert "גלילים (" not in row["description"]


@pytest.mark.parametrize("sqm", [55, 61, 3, 0.5])
def test_a_quantity_that_is_not_whole_rolls_stays_in_square_meters(client, sqm):
    """עדיף להשאיר מ"ר מאשר להמציא חצי גליל בתעודת משלוח."""
    row = client._rows_for_delivery(_po([_sheet(sqm, "מר")]))[0]
    assert row["quantity"] == float(sqm)
    assert "גלילים" not in row["description"]


def test_other_products_in_square_meters_are_untouched(client):
    row = client._rows_for_delivery(_po([
        _sheet(60, "מר", description="סיילנטופ - יריעה אקוסטית לקירות גבס", sku="SLT-1")
    ]))[0]
    assert row["quantity"] == 60.0
    assert "גלילים" not in row["description"]


# ── החשבונית לא זזה ──────────────────────────────────────────────────────────

def test_the_invoice_keeps_the_ordered_unit_and_amount(client):
    """ההמרה היא תיאור פיזי בלבד. אם היא תיגע בחשבונית, הסכום יתחלק בשתיים."""
    po = _po([_sheet(60, "מר")])
    delivery = client._rows_for_delivery(po)[0]
    invoice = client._rows_for_invoice(po)[0]
    assert delivery["quantity"] == 30.0
    assert invoice["quantity"] == 60.0
    assert invoice["price"] == 52.0
    assert invoice["quantity"] * invoice["price"] == 3120.0


def test_multiple_lines_convert_independently(client):
    rows = client._rows_for_delivery(_po([
        _sheet(60, "מר"),
        _sheet(10, "יח׳"),
        _sheet(24, "מר"),
    ]))
    assert [r["quantity"] for r in rows] == [30.0, 10.0, 12.0]


def test_sku_is_preserved_through_the_conversion(client):
    row = client._rows_for_delivery(_po([_sheet(60, "מר")]))[0]
    assert row["sku"] == "103000580"
    assert row["price"] == 0
