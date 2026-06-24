import re
from pathlib import Path

from services.models import PurchaseOrderData
from services.parsers.almogim import parse as parse_almogim
from services.parsers.amram import parse as parse_amram
from services.parsers.artec import parse as parse_artec
from services.parsers.asbit import parse as parse_asbit
from services.parsers.brosh import parse as parse_brosh
from services.parsers.common import extract_text_pdfplumber, fix_hebrew_text, fix_hebrew_rtl_text, normalize_ws, ocr_pdf, to_purchase_order
from services.parsers.damari import parse as parse_damari
from services.parsers.generic import parse_generic, parse_prashkovsky
from services.parsers.hagivaa import parse as parse_hagivaa
from services.parsers.kedar import parse as parse_kedar
from services.parsers.lati import parse as parse_lati
from services.parsers.levinstein import parse_levinstein
from services.parsers.masad_armour import parse as parse_masad_armour
from services.parsers.moral import parse as parse_moral
from services.parsers.ram_aderet import parse as parse_ram_aderet
from services.parsers.sela import parse as parse_sela
from services.parsers.shponder_pedlon import parse as parse_shponder_pedlon
from services.parsers.sivanb import parse_sivanb
from services.parsers.source import parse as parse_source
from services.parsers.tubul import parse as parse_tubul
from services.parsers.electra_ashtrom import parse as parse_electra_ashtrom
from services.parsers.ecocity import parse as parse_ecocity
from services.parsers.yargad import parse as parse_yargad
from services.parsers.yitzhak_stern import parse as parse_yitzhak_stern
from services.parsers.ya_alon import parse as parse_ya_alon
from services.parsers.yuval_alon import parse as parse_yuval_alon
from services.parsers.danya_cebus import parse as parse_danya_cebus
from services.parsers.danya_cebus import _REVERSED_MARKER as _DANYA_MARKER, _EMAIL_DOMAIN as _DANYA_DOMAIN


def _build_purchase_order(result, raw_text: str, parser_name: str = "") -> PurchaseOrderData | None:
    if result is None:
        return None
    if isinstance(result, PurchaseOrderData):
        if parser_name:
            result.extra = dict(result.extra or {})
            result.extra["parser_name"] = parser_name
        return result
    customer_name, items, header = result
    purchase_order = to_purchase_order(customer_name, items, header, raw_text)
    if isinstance(header, dict) and isinstance(header.get("extra"), dict):
        purchase_order.extra = {**dict(purchase_order.extra or {}), **header["extra"]}
    if parser_name:
        purchase_order.extra = dict(purchase_order.extra or {})
        purchase_order.extra["parser_name"] = parser_name
    return purchase_order


def _route_portal_parser(fixed_text: str):
    if "ברוש ניר עבודות הנדסה" in fixed_text:
        return "brosh"
    if "לאטי יזום ובניה" in fixed_text or "לאטי יזום ובנייה" in fixed_text:
        return "lati"
    if "אלמוג" in fixed_text:
        return "almogim"
    if "סלע ביצוע" in fixed_text:
        return "sela"
    if "דמרי" in fixed_text:
        return "damari"
    if "ירגד פרויקטים" in fixed_text:
        return "yargad"
    if "רם אדרת" in fixed_text:
        return "ram_aderet"
    if "יצחק שטרן" in fixed_text:
        return "yitzhak_stern"
    return ""


def parse_purchase_order(pdf_path: str | Path):
    raw_text = extract_text_pdfplumber(pdf_path)
    if len(normalize_ws(raw_text)) < 40:
        raw_text = ocr_pdf(pdf_path)

    # Danya Cebus must be detected on RAW text (before fix_hebrew_text reverses numbers/emails/dates)
    if _DANYA_MARKER in raw_text or _DANYA_DOMAIN in raw_text.lower():
        parsed = _build_purchase_order(parse_danya_cebus(raw_text, pdf_path=pdf_path), raw_text, "danya_cebus")
        if parsed:
            return parsed

    fixed_text = fix_hebrew_text(raw_text)

    if ("Square" in raw_text and "meter" in raw_text) and re.search(r"\d{6,}-\d{2}", raw_text):
        from services.parsers.plasan import parse as parse_plasan

        parsed = parse_plasan(raw_text)
        purchase_order = to_purchase_order(parsed.get("customer_name"), parsed.get("items"), parsed, raw_text)
        purchase_order.extra = dict(purchase_order.extra or {})
        purchase_order.extra["parser_name"] = "plasan"
        return purchase_order

    portal_template = _route_portal_parser(fixed_text)
    if portal_template == "brosh":
        return _build_purchase_order(parse_brosh(raw_text), raw_text, "brosh")
    if portal_template == "lati":
        return _build_purchase_order(parse_lati(raw_text), raw_text, "lati")
    if portal_template == "almogim":
        return _build_purchase_order(parse_almogim(raw_text), raw_text, "almogim")
    if portal_template == "sela":
        return _build_purchase_order(parse_sela(raw_text), raw_text, "sela")
    if portal_template == "damari":
        return _build_purchase_order(parse_damari(raw_text), raw_text, "damari")
    if portal_template == "yargad":
        return _build_purchase_order(parse_yargad(raw_text), raw_text, "yargad")
    if portal_template == "ram_aderet":
        return _build_purchase_order(parse_ram_aderet(raw_text), raw_text, "ram_aderet")
    if portal_template == "yitzhak_stern":
        return _build_purchase_order(parse_yitzhak_stern(raw_text), raw_text, "yitzhak_stern")

    if (
        "חשבונית יש להפיק עבור" in fixed_text
        and "קידר" in fixed_text
        and "בן יעקב פתרונות טקסטיל" in fixed_text
    ) or (
        "תינובשח" in raw_text
        and "רדיק" in raw_text
        and "ליטסקט תונורתפ בקעי ןב" in raw_text
    ):
        parsed = _build_purchase_order(parse_kedar(raw_text), raw_text, "kedar")
        if parsed:
            return parsed

    if "אקוסיטי" in fixed_text and "חשבונית יש להפיק עבור" in fixed_text:
        parsed = _build_purchase_order(parse_ecocity(raw_text), raw_text, "ecocity")
        if parsed:
            return parsed

    if (
        "פדלון שפונדר ביצוע" in fixed_text
        or 'מ"עב עוציב רדנופש ןולדפ' in raw_text
    ) and "הזמנת רכש" in fixed_text:
        shponder_text = ocr_pdf(pdf_path)
        rtl_fixed_text = fix_hebrew_rtl_text(raw_text)
        parsed = _build_purchase_order(
            parse_shponder_pedlon(shponder_text)
            or parse_shponder_pedlon(rtl_fixed_text)
            or parse_shponder_pedlon(fixed_text)
            or parse_shponder_pedlon(raw_text),
            raw_text,
            "shponder_pedlon",
        )
        if parsed:
            return parsed

    if any(
        marker in raw_text
        for marker in ("PROD5050", "QTP5555", "חשבונית יש להפיק עבור", "ZivPdf", "SivanB")
    ) or any(
        marker in fixed_text
        for marker in ("סיון ביצוע", "פרשקובסקי", "ינושבסקי", "חשבונית יש להפיק עבור")
    ):
        parsed = _build_purchase_order(parse_sivanb(raw_text), raw_text, "sivanb")
        if parsed:
            return parsed

    if "טובול חומרי בניין" in fixed_text or "מרלו\"ג מודיעין" in fixed_text or "מרכז עינב" in fixed_text:
        parsed = _build_purchase_order(parse_tubul(raw_text), raw_text, "tubul")
        if parsed:
            return parsed

    if "אסביט" in fixed_text and "פתח תקוה" in fixed_text and "הזמנת רכש" in fixed_text:
        parsed = _build_purchase_order(parse_asbit(raw_text), raw_text, "asbit")
        if parsed:
            return parsed

    if "ARTEK TECHNOLOGIES" in raw_text or "קטרא" in raw_text or "WWW.ARTEK-BAGS.COM" in raw_text:
        parsed = _build_purchase_order(parse_artec(raw_text), raw_text, "artec")
        if parsed:
            return parsed

    if "אשטרום" in fixed_text and "אלקטרה בניה" in fixed_text:
        parsed = _build_purchase_order(parse_electra_ashtrom(raw_text), raw_text, "electra_ashtrom")
        if parsed:
            return parsed

    if "מצדה ארמור" in fixed_text or "רומרא הדצמ" in raw_text:
        parsed = _build_purchase_order(parse_masad_armour(raw_text), raw_text, "masad_armour")
        if parsed:
            return parsed

    if "שורש טקטיקל גיר" in fixed_text or "POG" in fixed_text or "POG" in raw_text or "sourcetacticalgear" in raw_text.lower():
        parsed = _build_purchase_order(parse_source(raw_text), raw_text, "source")
        if parsed:
            return parsed

    if (
        ("י.א אלון" in fixed_text and "הזמנת רכש" in fixed_text)
        or ("הינב ןולא א.י" in raw_text and "שכר תנמזה" in raw_text)
    ):
        parsed = _build_purchase_order(parse_ya_alon(raw_text), raw_text, "ya_alon")
        if parsed:
            return parsed

    if (
        ("יובל אלון" in raw_text and "הזמנת רכש" in raw_text)
        or ("יובל אלון" in fixed_text and "הזמנת רכש" in fixed_text)
    ):
        parsed = _build_purchase_order(parse_yuval_alon(raw_text), raw_text, "yuval_alon")
        if parsed:
            return parsed

    if "לוינשטין נתיב" in fixed_text:
        return _build_purchase_order(parse_levinstein(fixed_text), raw_text, "levinstein")

    if "עמרם אברהם ביצועים" in fixed_text or "office@amramb.co.il" in fixed_text:
        return _build_purchase_order(parse_amram(raw_text), raw_text, "amram")

    if "הגבעה י.ח" in fixed_text:
        return _build_purchase_order(parse_hagivaa(fixed_text), raw_text, "hagivaa")

    if "מורל טכנולוגיות" in fixed_text:
        return _build_purchase_order(parse_moral(fixed_text), raw_text, "moral")

    if "פרשקובסקי" in fixed_text:
        return _build_purchase_order(parse_prashkovsky(fixed_text), raw_text, "prashkovsky")

    return _build_purchase_order(parse_generic(fixed_text), raw_text, "generic")
