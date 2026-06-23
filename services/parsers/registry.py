from services.parsers.generic import parse_generic
from services.parsers.sivanb import parse_sivanb
from services.parsers.yuval_alon import parse_yuval_alon


def detect_and_parse(text: str):
    if any(marker in text for marker in ("PROD5050", "QTP5555", "חשבונית יש להפיק עבור", "סיון ביצוע", "פרשקובסקי")):
        result = parse_sivanb(text)
        if result:
            return result

    for parser in (parse_yuval_alon, parse_generic):
        result = parser(text)
        if result:
            return result

    return None
