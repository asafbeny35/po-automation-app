"""Plasan parser must not invent a delivery contact and must set unit / project."""
from services.parsers.plasan import parse

RAW = """4148678 רפסמ שכר תנמזה 2 ךותמ 1 דומע
Argov, Amir : ןיינק ליטסקט תונורתפ בקעי ןב :קפס
054-3133702 :דיינ
AMIR.ARGOV@plasan.com :ל"אוד
1111095 :טקייורפ 'סמ
7,500.00 125.000 Polymers - Polyester; Perforated 01 5430000037-00 1
Upholstery; W: 1400 mm; Thick.: 1 mm;
60 Square meter 01-DEC-2026 1
7,500.00 :(ILS) כ"הס
"""


def test_contact_is_empty_not_invented():
    d = parse(RAW)
    assert d["contact_name"] == ""
    assert d["contact_phone"] == ""
    assert "Hazan" not in d["extra"]["footer_text"]
    assert "052-6991246" not in d["extra"]["footer_text"]


def test_buyer_kept_separately():
    d = parse(RAW)
    assert d["extra"]["buyer_name"] == "Argov, Amir"
    assert d["extra"]["buyer_phone"] == "054-3133702"


def test_unit_project_and_amounts():
    d = parse(RAW)
    assert d["items"][0].unit == 'מ"ר'
    assert d["project"] == "1111095"
    assert (d["subtotal"], d["vat"], d["total"]) == (7500.0, 1350.0, 8850.0)
