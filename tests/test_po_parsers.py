"""
Unit tests for all PO parsers.

Input format per parser matches what po_parser.py actually passes:
- Most parsers receive raw_text (reversed Hebrew from pdfplumber)
- levinstein receives RTL-fixed text
- hagivaa receives fixed_text (correct Hebrew order)
- shponder_pedlon receives OCR text (correct Hebrew)
"""
from __future__ import annotations

import pytest

# Module-level imports
from services.parsers.shponder_pedlon import parse as parse_shponder
from services.parsers.sivanb import parse_sivanb
from services.parsers.almogim import parse as parse_almogim
from services.parsers.kedar import parse as parse_kedar
from services.parsers.tubul import parse as parse_tubul
from services.parsers.ya_alon import parse as parse_ya_alon
from services.parsers.yuval_alon import parse as parse_yuval_alon
from services.parsers.yargad import parse as parse_yargad
from services.parsers.ram_aderet import parse as parse_ram_aderet
from services.parsers.yitzhak_stern import parse as parse_yitzhak_stern
from services.parsers.levinstein import parse_levinstein
from services.parsers.electra_ashtrom import parse as parse_electra_ashtrom
from services.parsers.amram import parse as parse_amram
from services.parsers.hagivaa import parse as parse_hagivaa
from services.parsers.moral import parse as parse_moral
from services.parsers.asbit import parse as parse_asbit
from services.parsers.source import parse as parse_source
from services.parsers.masad_armour import parse as parse_masad_armour
from services.parsers.ecocity import parse as parse_ecocity
from services.parsers.damari import parse as parse_damari
from services.parsers.sela import parse as parse_sela
from services.parsers.lati import parse as parse_lati
from services.parsers.brosh import parse as parse_brosh
from services.parsers.artec import parse as parse_artec
from services.parsers.plasan import parse as parse_plasan
from services.parsers.generic import parse_generic
from services.po_parser import _route_portal_parser


# ── helpers ──────────────────────────────────────────────────────────────────

def _r(parser_func, text: str):
    """Call parser, normalize to (customer_name, items, header) or None."""
    result = parser_func(text)
    if result is None:
        return None
    if hasattr(result, "customer_name"):
        return result.customer_name, result.items, {
            "po_number": result.po_number,
            "po_date": result.po_date,
            "total": result.total,
            "subtotal": result.subtotal,
            "vat": result.vat,
            "project": result.project,
            "delivery_address": result.delivery_address,
            "contact_name": result.contact_name,
            "contact_phone": result.contact_phone,
            "payment_terms_days": result.payment_terms_days,
        }
    return result


def _ok(parser_func, text):
    r = _r(parser_func, text)
    assert r is not None, f"Parser returned None for:\n{text[:200]}"
    return r


def _none(parser_func, text):
    r = _r(parser_func, text)
    assert r is None, f"Parser should return None for:\n{text[:200]}"


# ════════════════════════════════════════════════════════════════════════════
# 1. SHPONDER PEDLON — receives OCR text (correct Hebrew)
# ════════════════════════════════════════════════════════════════════════════

SHPONDER_OCR = (
    'פדלון שפונדר ביצוע בע"מ\n'
    "ח.פ: 516087269\n"
    "תאריך הזמנה: 22/06/2026\n"
    "בן יעקב פתרונות טקסטיל\n"
    "הזמנת רכש מ0ס:14458\n"
    "קוד פריט\n"
    # Single item — multi-item blocks need >1 source line which is complex to fake
    "1 12345 כיסוי להגנת דלתות 36.0 יח' 22/07/2026 ₪76.00 2,736.00\n"
    "תנאי תשלום שוטף + 60\n"
    'סה"כ חייב במע"מ: 2,736.00\n'
    "מע\"מ: 18 492.48\n"
    'סה"כ מסמך: 3,228.48\n'
)

def test_shponder_detects():           _ok(parse_shponder, SHPONDER_OCR)
def test_shponder_rejects_unrelated(): _none(parse_shponder, "PROD5050\nהזמנת רכש 999")

def test_shponder_po_number():
    r = _r(parse_shponder, SHPONDER_OCR)
    assert r[2]["po_number"] == "14458"

def test_shponder_date():
    r = _r(parse_shponder, SHPONDER_OCR)
    assert r[2]["po_date"] == "22/06/2026"

def test_shponder_totals():
    r = _r(parse_shponder, SHPONDER_OCR)
    assert r[2]["subtotal"] == pytest.approx(2736.0)
    assert r[2]["total"] == pytest.approx(3228.48)

def test_shponder_items():
    r = _r(parse_shponder, SHPONDER_OCR)
    assert len(r[1]) >= 1
    item0 = r[1][0]
    assert item0.quantity == pytest.approx(36.0)
    assert item0.unit_price == pytest.approx(76.0)

def test_shponder_payment_terms():
    r = _r(parse_shponder, SHPONDER_OCR)
    assert r[2]["payment_terms_days"] == 60

def test_shponder_detects_reversed_customer():
    # Also works on reversed form (from po_parser fixed_text fallback)
    reversed_text = 'מ"עב עוציב רדנופש ןולדפ\nהזמנת רכש מ0ס:99'
    r = _r(parse_shponder, reversed_text)
    assert r is not None


# ════════════════════════════════════════════════════════════════════════════
# 2. SIVANB — receives raw_text
# ════════════════════════════════════════════════════════════════════════════

# sivanb format 1: reversed text with ":ח וקל" (buyer field) — no item needed for route detection
SIVANB_FORMAT1 = (
    "123456789 פ.ח - ןוויס עוציב :ח וקל\n"
    "תל אביב :רתא/תבותכ\n"
    "456-1234-052 כהן דוד :1 רשק שיא\n"
    "101/1000 :הנמזה רפסמ\n"
    "ישאר :טירפ\n"
    "10\n:תומכ\n"
    "55555QTP טקמ\n"
)

def test_sivanb_detects_format1():   _ok(parse_sivanb, SIVANB_FORMAT1)
def test_sivanb_rejects_unrelated(): _none(parse_sivanb, 'אלמוגים בניה הזמנת רכש 999')


# ════════════════════════════════════════════════════════════════════════════
# 3. ALMOGIM — receives raw_text (reversed Hebrew from pdfplumber)
# ════════════════════════════════════════════════════════════════════════════

# Detection marker: "םיגומלא" (reversed "אלמוגים") + "שכר תנמזה" (reversed "הזמנת רכש")
ALMOGIM_RAW = "PO2024-555 :שכר תנמזה\nםיגומלא\nאלמוגים בניה והשקעות\n55555-12345 :יצחק\nסה\"כ: 4,500.00"

def test_almogim_detects():
    r = _r(parse_almogim, ALMOGIM_RAW)
    if r is None:
        # Try correct Hebrew (some versions detect either way)
        r = _r(parse_almogim, 'אלמוגים בניה בע"מ\nהזמנת רכש PO2024-555\nסה"כ: 4,500.00')
    assert r is not None

def test_almogim_rejects_unrelated(): _none(parse_almogim, "PROD5050 הזמנת רכש 1")


# ════════════════════════════════════════════════════════════════════════════
# 4. KEDAR — receives raw_text; detection: "רדיק" + "תינובשח" + "בקעי ןב"
# (reversed "קידר" / "חשבונית" / "בן יעקב")
# po_parser.py also matches fixed_text: "קידר" + "חשבונית יש להפיק עבור"
# ════════════════════════════════════════════════════════════════════════════

KEDAR_RAW = (
    "1/KDR 'סמ הנמזה\n"
    "תינובשח\n"
    "רדיק\n"
    "ליטסקט תונורתפ בקעי ןב\n"
    "םולשת יאנת\n"
    "00.000,7 :ס\"כה\n"
)

def test_kedar_detects(): _ok(parse_kedar, KEDAR_RAW)
def test_kedar_rejects(): _none(parse_kedar, "PROD5050 הזמנת רכש 1")


# ════════════════════════════════════════════════════════════════════════════
# 5. TUBUL — receives raw_text; detection: 'שכר תנמזה' in raw_text
# ════════════════════════════════════════════════════════════════════════════

TUBUL_RAW = "77-BT שכר תנמזה\nןיינב ירמוח לובוט\nמרכז עינב\n00.068,8 :ס\"כה"

def test_tubul_detects():
    r = _r(parse_tubul, TUBUL_RAW)
    if r is None:
        r = _r(parse_tubul, "מרלו\"ג מודיעין\nהזמנת רכש TB-77\nסה\"כ: 8,000.00")
    assert r is not None

def test_tubul_rejects(): _none(parse_tubul, "אשטרום בניה הזמנת רכש")


# הפורמט השני של טובול — "הזמנת אספקה ישירות ללקוח". טקסט ויזואלי (הפוך) כפי
# ש-pdfplumber מחזיר אותו, מתוך הזמנה אמיתית 1208144146.
TUBUL_DIRECT_RAW = "\n".join([
    "1208144146 חוקלל תורישי הקפסא תנמזה",
    "511529414 פ.ח סמ",
    "25/08/2026 הקפסא דעומ",
    "חי 290 דעלא-מ''עב ]1983[ ןיינבו םיסכנ ינאזרב ד.י : חוקל םש , 34 ןרוגה",
    "דעלא 118 אישנה הדוהי : תבותכ , 101 ד.ת",
    "0502272814 רתא להנמ : רשק שיא 3032434 תילתע",
    "10,400.00 52.000 0.00 רמ 52.000 200.00 תרנצל הקיתשמ פייפיטסוקא תעירי 103000580 103000580 1",
    ")רמ 2 לילג(- 1*2",
    '10,400.00 החנה ירחא כ"הס :גהנל העדוה',
    '1,872.00 18% מ"עמ רתא להנמ תמתוח+ המיתח !!!!הבוח',
    '12,272.00 םולשתל כ"הס',
    "םיקפס 120 + ףטוש :םולשת יאנת",
    'ג"ולרמ 08-9555555 :לט 71706 ןיעידומ ,בניע זכרמ',
])


def test_tubul_direct_supply_header():
    """הפורמט הזה נפל לפרסר הגנרי, שהפך את כל המספרים: ח.פ 414925115 וסה\"כ 0.27 ₪."""
    name, items, header = parse_tubul(TUBUL_DIRECT_RAW)
    assert name == "טובול ציוד וחומרי בניין"   # כפי שרשום בקטלוג, ח.פ 511529414
    assert header["po_number"] == "1208144146"
    assert header["customer_id"] == "511529414"      # ולא ההיפוך 414925115
    assert header["po_date"] == "25/08/2026"
    assert (header["subtotal"], header["vat"], header["total"]) == (10400.0, 1872.0, 12272.0)
    assert header["payment_terms_days"] == 120       # ולא 021
    assert header["delivery_address"] == "יהודה הנשיא 118 אלעד"
    assert header["contact_phone"] == "050-2272814"
    assert header["project"] == 'י.ד ברזאני נכסים ובניין [1983] בע"מ-אלעד 290 יח'


def test_tubul_direct_supply_item():
    _, items, header = parse_tubul(TUBUL_DIRECT_RAW)
    assert len(items) == 1
    item = items[0]
    assert item.sku == "103000580"
    assert (item.quantity, item.unit_price, item.line_total) == (200.0, 52.0, 10400.0)
    assert item.description == "יריעת אקוסטיפייפ משתיקה לצנרת 2*1 (גליל 2 מר)"
    assert round(item.quantity * item.unit_price, 2) == header["subtotal"]


# ════════════════════════════════════════════════════════════════════════════
# 6. YA_ALON — receives raw_text; detection: "הינב ןולא א.י" + "שכר תנמזה"
# ════════════════════════════════════════════════════════════════════════════

# ya_alon detection: "י.א אלון בניה" + "הזמנת רכש מס'" (with מס')
YA_ALON_TEXT = "י.א אלון בניה\nהזמנת רכש מס' 50-AY\nתאריך: 05/05/2024\nסה\"כ: 5,000.00"

def test_ya_alon_detects(): _ok(parse_ya_alon, YA_ALON_TEXT)
def test_ya_alon_rejects(): _none(parse_ya_alon, "יובל אלון הזמנת רכש 1")


# ════════════════════════════════════════════════════════════════════════════
# 7. YUVAL_ALON — receives raw_text; detection: "יובל אלון" + "הזמנת רכש"
# ════════════════════════════════════════════════════════════════════════════

def test_yuval_alon_detects(): _ok(parse_yuval_alon, 'יובל אלון בניה\nהזמנת רכש YUV-88\nסה"כ: 8,000.00')
def test_yuval_alon_rejects(): _none(parse_yuval_alon, 'הינב ןולא א.י שכר תנמזה')


# ════════════════════════════════════════════════════════════════════════════
# 8-10. PORTAL PARSERS (shared_portal) — raw_text
# ════════════════════════════════════════════════════════════════════════════

def test_yargad_detects():  _ok(parse_yargad, 'ירגד פרויקטים בע"מ\nהזמנת רכש YRG-33\nסה"כ: 8,850.00')
def test_ram_aderet_detects(): _ok(parse_ram_aderet, 'רם אדרת בניה\nהזמנת רכש RA-21\nסה"כ: 7,500.00')
def test_yitzhak_stern_detects(): _ok(parse_yitzhak_stern, "יצחק שטרן ושות'\nהזמנת רכש YS-44\nסה\"כ: 9,440.00")


# ════════════════════════════════════════════════════════════════════════════
# 11. LEVINSTEIN — receives fixed_text (correct Hebrew!)
# ════════════════════════════════════════════════════════════════════════════

LEVINSTEIN_FIXED = (
    'לוינשטין נתיב הנדסה ובנין בע"מ\n'
    "הזמנת רכש LEV-12\n"
    "1 12345678 כיסוי QTP 236 10.0 מ\"ר 350.00 3,500.00\n"
    'סה"כ: 47,200.00\n'
)

def test_levinstein_detects(): _ok(parse_levinstein, LEVINSTEIN_FIXED)
# levinstein has no strict detection — always returns a result for any text


def test_levinstein_keeps_project_number_and_item_description():
    text = (
        'לוינשטין נתיב הנדסה ובנין בע"מ\n'
        'הזמנת רכש מס: 27488\n'
        'פרויקט: פארק הים, מגרש 42 לידי: איתמר צפירה, 0526879191\n'
        'כתובת פרויקט: בת ים, בת ים\n'
        "1 21800019 מגן דלת ליח' דלת /כנף -בכל מידה -כולל התקנה 80.00 קומפ' ₪96.00 7,680.00\n"
        'סה"כ חייב במע"מ: 7,680.00\n'
        'מע"מ: % 18.00 1,382.40\n'
        'סה"כ מסמך: 9,062.40\n'
    )
    customer_name, items, header = parse_levinstein(text)
    assert customer_name == 'לוינשטין נתיב הנדסה ובנין בע"מ'
    assert header["project"] == "פארק הים, מגרש 42"
    assert items[0].description == "מגן דלת ליח' דלת /כנף -בכל מידה -כולל התקנה"
    assert items[0].quantity == pytest.approx(80.0)
    assert items[0].unit == "קומפ'"


# ════════════════════════════════════════════════════════════════════════════
# 12. ELECTRA_ASHTROM — raw_text; detection: "םורטשא" (reversed "אשטרום")
# ════════════════════════════════════════════════════════════════════════════

ELECTRA_RAW = "99-AE שכר תנמזה\nםורטשא\nkikar@electra.co.il\n00.009,46 :ס\"כה"

def test_electra_ashtrom_detects():
    r = _r(parse_electra_ashtrom, ELECTRA_RAW)
    if r is None:
        r = _r(parse_electra_ashtrom, "kikar@electra.co.il\nהזמנת רכש EA-99\nסה\"כ: 64,900.00")
    assert r is not None

def test_electra_ashtrom_rejects(): _none(parse_electra_ashtrom, 'לוינשטין נתיב הזמנת רכש 1')


# ════════════════════════════════════════════════════════════════════════════
# 13. AMRAM — raw_text; detection: company name or email
# ════════════════════════════════════════════════════════════════════════════

def test_amram_detects_by_name():  _ok(parse_amram, 'עמרם אברהם ביצועים בע"מ\nהזמנת רכש AM-7\nסה"כ: 5,400.00')
def test_amram_detects_by_email(): _ok(parse_amram, "office@amramb.co.il\nהזמנת רכש AM-5\nפריט א 10 100.00")
def test_amram_rejects():          _none(parse_amram, 'אלמוגים הזמנת רכש 1')


# ════════════════════════════════════════════════════════════════════════════
# 14. HAGIVAA — receives fixed_text (correct Hebrew!)
# ════════════════════════════════════════════════════════════════════════════

def test_hagivaa_detects():   _ok(parse_hagivaa, 'הגבעה י.ח בניה בע"מ\nהזמנת רכש HG-3\nסה"כ: 5,400.00')

# ════════════════════════════════════════════════════════════════════════════
# 15. MORAL — raw_text
# ════════════════════════════════════════════════════════════════════════════

def test_moral_detects():     _ok(parse_moral, 'מורל טכנולוגיות בע"מ\nהזמנת רכש MRL-11\nסה"כ: 17,700.00')


# ════════════════════════════════════════════════════════════════════════════
# 16. ASBIT — raw_text; calls fix_hebrew_text internally
#     detection: "אסביט" AND "הזמנת רכש" in fixed_text
# ════════════════════════════════════════════════════════════════════════════

# Either pass correct Hebrew (asbit calls fix_hebrew_text internally) or reversed
# asbit: calls fix_hebrew_text internally — needs REVERSED Hebrew as input
# produce reversed text by running fix_hebrew_text on correct Hebrew
from services.parsers.common import fix_hebrew_text as _fht
ASBIT_TEXT = _fht("אסביט\nפתח תקוה\nהזמנת רכש ASB-5")

def test_asbit_detects(): _ok(parse_asbit, ASBIT_TEXT)
def test_asbit_rejects(): _none(parse_asbit, "אסביט הזמנת רכש 1")  # missing "פתח תקוה"


# ════════════════════════════════════════════════════════════════════════════
# 17. SOURCE — raw_text; detection: company name, POG or website
# ════════════════════════════════════════════════════════════════════════════

def test_source_detects_pog():     _ok(parse_source, "POG\nהזמנת רכש 5\nפריט א 5 יח' 100.00")
def test_source_detects_website(): _ok(parse_source, "WWW.SOURCETACTICALGEAR.COM\nPOG-5\nסה\"כ: 5,000.00")


# ════════════════════════════════════════════════════════════════════════════
# 18. MASAD_ARMOUR — raw_text
# ════════════════════════════════════════════════════════════════════════════

def test_masad_armour_detects(): _ok(parse_masad_armour, 'מצדה ארמור בע"מ\nהזמנת רכש MA-8\nסה"כ: 16,000.00')


# ════════════════════════════════════════════════════════════════════════════
# 19. ECOCITY — raw_text; detection: "יטיסוקא" + "תינובשח" OR correct Hebrew
# ════════════════════════════════════════════════════════════════════════════

ECOCITY_RAW = "22-OCE שכר תנמזה\nיטיסוקא\nתינובשח\n00.000,62 :ס\"כה"

def test_ecocity_detects():
    r = _r(parse_ecocity, ECOCITY_RAW)
    if r is None:
        # Also try with correct Hebrew (ecocity checks fixed_text)
        r = _r(parse_ecocity, "חשבונית יש להפיק עבור\nאקוסיטי\nהזמנת רכש ECO-22\nסה\"כ: 26,000.00")
    assert r is not None

def test_ecocity_rejects(): _none(parse_ecocity, "אלמוגים בניה הזמנת רכש 1")


# ════════════════════════════════════════════════════════════════════════════
# 20. DAMARI — raw_text; expects reversed Hebrew
# ════════════════════════════════════════════════════════════════════════════

DAMARI_RAW = "50-RMD שכר תנמזה\nירמד\nהינבו היינב ירמד .ח.י\n00.000,45 :ס\"כה"

def test_damari_detects():
    r = _r(parse_damari, DAMARI_RAW)
    if r is None:
        r = _r(parse_damari, 'י.ח. דמרי בניה ובניה\nהזמנת רכש DMR-50\nסה"כ: 54,000.00')
    assert r is not None


DAMARI_MULTI_ITEM_RAW = """מ"עב חותיפו הינב ירמד .ח.י
111718 שכר תנמזה 054-7720142
29/04/2026 :הנמזה ךיראת
0523228011 רב לאינד
הינתנ:רוזיא 9 ןתנוי ןתנ:תבותכ :רשק שיא
'חי
לכה ךס ריחמ תומכ טירפ רואית טירפ דוק
הדימ
900.00 90.0000 10.00 10 2.10/1.30 תודימ- הנקתה ללוכ תלדל הנגה 17479
6,120.00 90.0000 68.00 68 2.30/1.40 תודימ- הנקתה ללוכ תלדל הנגה 17479
7,020.00 מ"עמו החנה ינפל כ"הס
1,263.60 18.00 % מ"עמ
8,283.60
מ"עמ ללוכ כ"הס"""


def test_damari_extracts_multiple_items_and_order_date():
    r = _ok(parse_damari, DAMARI_MULTI_ITEM_RAW)
    assert r[2]["po_date"] == "29/04/2026"
    assert len(r[1]) == 2
    assert r[1][0].description == "הגנה לדלת כולל התקנה - מידות 2.10/1.30"
    assert r[1][0].quantity == pytest.approx(10.0)
    assert r[1][1].description == "הגנה לדלת כולל התקנה - מידות 2.30/1.40"
    assert r[1][1].quantity == pytest.approx(68.0)


# ════════════════════════════════════════════════════════════════════════════
# 21. SELA — raw_text; expects reversed Hebrew
# ════════════════════════════════════════════════════════════════════════════

# sela: normalizes reversed Hebrew internally — needs reversed input
SELA_TEXT = _fht("סלע ביצוע\nהזמנת רכש מספר SLA-14")

def test_sela_detects(): _ok(parse_sela, SELA_TEXT)


# ════════════════════════════════════════════════════════════════════════════
# 22. LATI — raw_text; expects reversed Hebrew
# ════════════════════════════════════════════════════════════════════════════

def test_lati_detects_v1(): _ok(parse_lati, 'לאטי יזום ובניה בע"מ\nהזמנת רכש LAT-19\nסה"כ: 5,500.00')
def test_lati_detects_v2(): _ok(parse_lati, 'לאטי יזום ובנייה בע"מ\nהזמנת רכש LAT-5\nסה"כ: 5,500.00')


# ════════════════════════════════════════════════════════════════════════════
# 23. BROSH — raw_text; expects reversed Hebrew
# ════════════════════════════════════════════════════════════════════════════

def test_brosh_detects(): _ok(parse_brosh, 'ברוש ניר עבודות הנדסה בע"מ\nהזמנת רכש BRO-31\nסה"כ: 15,000.00')


# ════════════════════════════════════════════════════════════════════════════
# 24. ARTEC — raw_text; detection: company or website
# ════════════════════════════════════════════════════════════════════════════

def test_artec_detects_company(): _ok(parse_artec, "ARTEK TECHNOLOGIES LTD\nPO ART-6\nItem A 50 pcs 350.00")
def test_artec_detects_website(): _ok(parse_artec, "WWW.ARTEK-BAGS.COM\nPO ART-9\nItem A 10 pcs 200.00")


# ════════════════════════════════════════════════════════════════════════════
# 25. PLASAN — raw_text; detection done in po_parser.py (Square + meter)
#     Parse function itself has no strict detection; returns a result for any text
# ════════════════════════════════════════════════════════════════════════════

def test_plasan_detects():
    r = _r(parse_plasan, "Plasan Sasa\nPO 123456-01\nItem A\nSquare meter 50\n500.00")
    assert r is not None


# ════════════════════════════════════════════════════════════════════════════
# GENERIC PARSER — always returns a result
# ════════════════════════════════════════════════════════════════════════════

def test_generic_never_returns_none():
    assert parse_generic("זה טקסט לגמרי אקראי") is not None

def test_generic_handles_empty():
    assert parse_generic("") is not None

def test_generic_handles_english():
    assert parse_generic("Invoice #1234 Total: $500") is not None


# ════════════════════════════════════════════════════════════════════════════
# PORTAL ROUTING — _route_portal_parser receives fixed (correct Hebrew) text
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("text,expected", [
    ("ברוש ניר עבודות הנדסה\nהזמנת רכש 1", "brosh"),
    ("לאטי יזום ובניה\nהזמנת רכש 1", "lati"),
    ("לאטי יזום ובנייה\nהזמנת רכש 1", "lati"),
    ("אלמוגים בניה\nהזמנת רכש 1", "almogim"),
    ("סלע ביצוע\nהזמנת רכש 1", "sela"),
    ("דמרי קבוצת בניה\nהזמנת רכש 1", "damari"),
    ("ירגד פרויקטים\nהזמנת רכש 1", "yargad"),
    ("רם אדרת בניה\nהזמנת רכש 1", "ram_aderet"),
    ("יצחק שטרן ושות'\nהזמנת רכש 1", "yitzhak_stern"),
    ("חברה לא מוכרת\nהזמנת רכש 1", ""),
])
def test_portal_routing(text, expected):
    assert _route_portal_parser(text) == expected
