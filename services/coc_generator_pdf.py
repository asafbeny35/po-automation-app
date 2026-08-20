"""מחולל תעודת C.O.C בלי Playwright — הגרסה שרצה גם על Vercel.

`scripts/generate_coc.py` מרנדר HTML דרך Chromium, ו-Playwright אינו מותקן על
Vercel (מוצהר בראש requirements-vercel.txt). לכן הזמנת פלסן שנוצרה מהענן יצאה
בלי תעודת ה-C.O.C שלה, בשקט. כאן אותה פריסה בדיוק, מוטבעת על תבנית ה-PDF עם
PyMuPDF שכן זמין שם.

הקואורדינטות נלקחו כלשונן מ-`scripts/coc_html.txt`: הדף שם הוא 595x842 פיקסלים,
שזה בדיוק גודל A4 בנקודות, ולכן ערכי ה-CSS משמשים ישירות.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import fitz

from .runtime_paths import PROJECT_ROOT

TEMPLATE_PDF = PROJECT_ROOT / "assets" / "coc_template.pdf"
HEBREW_FONT = PROJECT_ROOT / "assets" / "NotoSansHebrew-Regular.ttf"

PAGE_WIDTH = 595.0

HEADER_TOP, HEADER_RIGHT, HEADER_SIZE = 70, 40, 16
TITLE_TOP, TITLE_RIGHT, TITLE_SIZE = 120, 120, 20
META_RIGHT, META_SIZE = 100, 14
META_ROWS = (("date", 170), ("sku", 200), ("expiry", 230), ("batch", 260))
DESC_TOP, DESC_SIDE, DESC_SIZE = 320, 120, 13
QTY_TOP, QTY_RIGHT, QTY_SIZE = 470, 100, 14
STATEMENTS_TOP, STATEMENTS_SIDE, STATEMENTS_SIZE = 520, 60, 13
FOOTER_BOTTOM, FOOTER_RIGHT, FOOTER_SIZE = 90, 60, 14

STATEMENTS = (
    "1. אנו מאשרים בזאת שהפריטים המפורטים לעיל המסופקים לכם עומדים בכל הדרישות המופיעות במפרט המתואר בהזמנה.",
    "2. הפריטים שסופקו לכם נבדקו על ידי היצרן ועומדים בכל הדרישות הרלוונטיות.",
)


def _visual(text: str) -> str:
    """היפוך לוגי→ויזואלי: PyMuPDF כותב שמאל-לימין, ובלי זה העברית יוצאת הפוכה."""
    try:
        from bidi.algorithm import get_display

        return get_display(str(text or ""))
    except Exception:
        return str(text or "")


class _Renderer:
    def __init__(self, page, font):
        self.page = page
        self.font = font

    def rtl(self, text: str, *, top: float, right: float, size: float) -> None:
        """הקצה הימני של הטקסט נעוץ במרחק `right` משפת הדף הימנית."""
        shaped = _visual(text)
        width = self.font.text_length(shaped, fontsize=size)
        self.page.insert_text(
            (PAGE_WIDTH - right - width, top + size),
            shaped, fontname="heb", fontsize=size, fill=(0, 0, 0),
        )

    def centered(self, text: str, *, top: float, size: float) -> None:
        width = self.font.text_length(text, fontsize=size)
        self.page.insert_text(
            ((PAGE_WIDTH - width) / 2, top + size),
            text, fontname="heb", fontsize=size, fill=(0, 0, 0),
        )

    def wrap(self, text: str, *, max_width: float, size: float) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in str(text or "").split():
            candidate = f"{current} {word}".strip()
            if self.font.text_length(candidate, fontsize=size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines


def generate_coc_pdf(data: dict, output: str) -> str:
    """`data`: po, sku, desc, qty, date, rolls — אותו חוזה כמו scripts/generate_coc.py."""
    now = datetime.now()
    po = str(data.get("po") or "").strip()
    sku = str(data.get("sku") or "").strip()
    desc = str(data.get("desc") or "").strip()
    raw_qty = data.get("qty")
    qty = f"{float(raw_qty):g}" if isinstance(raw_qty, (int, float)) else str(raw_qty or "")
    rolls = max(int(float(data.get("rolls") or 1)), 1)
    date_text = str(data.get("date") or "").strip() or now.strftime("%d/%m/%Y")
    expiry = f"{now.strftime('%m')}/{now.year + 8}"
    batch = f"{now.strftime('%m')}{now.strftime('%m')}/{now.year}"

    doc = fitz.open(TEMPLATE_PDF)
    page = doc[0]
    page.insert_font(fontname="heb", fontfile=str(HEBREW_FONT))
    render = _Renderer(page, fitz.Font(fontfile=str(HEBREW_FONT)))

    render.rtl("לכבוד: פלסן סאסא בע״מ", top=HEADER_TOP, right=HEADER_RIGHT, size=HEADER_SIZE)
    render.rtl(f"C.O.C עבור הזמנה מספר: {po}", top=TITLE_TOP, right=TITLE_RIGHT, size=TITLE_SIZE)

    meta = {
        "date": f"תאריך: {date_text}",
        "sku": f"מק״ט פריט: {sku}",
        "expiry": f"תוקף: {expiry}",
        "batch": f"מס׳ מנה: {batch}",
    }
    for key, top in META_ROWS:
        render.rtl(meta[key], top=top, right=META_RIGHT, size=META_SIZE)

    # התיאור באנגלית, ממורכז בתוך תיבה ברוחב קבוע
    for index, line in enumerate(render.wrap(desc, max_width=PAGE_WIDTH - 2 * DESC_SIDE, size=DESC_SIZE)):
        render.centered(line, top=DESC_TOP + index * DESC_SIZE * 1.4, size=DESC_SIZE)

    render.rtl(f"כמות: {qty} מ״ר | אספקה ב {rolls} גלילים", top=QTY_TOP, right=QTY_RIGHT, size=QTY_SIZE)

    # שני הסעיפים, כל אחד נשבר לרוחב התיבה
    line_top = STATEMENTS_TOP
    for statement in STATEMENTS:
        for line in render.wrap(statement, max_width=PAGE_WIDTH - 2 * STATEMENTS_SIDE, size=STATEMENTS_SIZE):
            render.rtl(line, top=line_top, right=STATEMENTS_SIDE, size=STATEMENTS_SIZE)
            line_top += STATEMENTS_SIZE * 1.6
        line_top += STATEMENTS_SIZE * 1.6  # הרווח הכפול שבין הסעיפים בתבנית

    render.rtl(
        "שם הספק: בן יעקב פתרונות טקסטיל",
        top=page.rect.height - FOOTER_BOTTOM - FOOTER_SIZE,
        right=FOOTER_RIGHT,
        size=FOOTER_SIZE,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return str(output_path)
