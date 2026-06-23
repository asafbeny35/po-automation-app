from __future__ import annotations

import base64
from pathlib import Path
from datetime import datetime

import fitz
from jinja2 import Environment, BaseLoader
from playwright.sync_api import sync_playwright
from .runtime_paths import PROJECT_ROOT, runtime_root

ASSETS_DIR = PROJECT_ROOT / "assets"
CACHE_DIR = runtime_root() / "output" / "_coc_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_PDF = ASSETS_DIR / "coc_template.pdf"
BACKGROUND_PNG = CACHE_DIR / "coc_bg.png"


def ensure_background_png() -> Path:
    if BACKGROUND_PNG.exists():
        return BACKGROUND_PNG

    doc = fitz.open(TEMPLATE_PDF)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    pix.save(str(BACKGROUND_PNG))
    doc.close()
    return BACKGROUND_PNG


def to_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


HTML = r"""
<!doctype html>
<html lang="he">
<head>
<meta charset="utf-8" />
<style>
  @page { size: 595px 842px; margin: 0; }
  body {
    margin: 0;
    width: 595px;
    height: 842px;
    font-family: Arial, "Noto Sans Hebrew", sans-serif;
  }

  .page {
    position: relative;
    width: 595px;
    height: 842px;
  }

  .bg {
    position: absolute;
    inset: 0;
    width: 595px;
    height: 842px;
  }

  .field {
    position: absolute;
    direction: rtl;
    text-align: right;
    color: #000;
  }

  .ltr {
    direction: ltr;
    text-align: left;
  }

  /* positions (נכוון בהמשך אם צריך) */

  #po       { top: 90px; right: 40px; font-size: 20px; }
  #date     { top: 130px; right: 40px; }
  #sku      { top: 170px; right: 40px; }
  #expiry   { top: 210px; right: 40px; }

  #desc     { top: 270px; left: 40px; right: 40px; text-align: center; }

  #qty      { top: 370px; right: 40px; }

  #batch    { bottom: 40px; right: 40px; }

</style>
</head>

<body>
<div class="page">

  <img class="bg" src="{{ bg_uri }}" />

  <div id="po" class="field ltr">C.O.C עבור הזמנה מספר: {{ po }}</div>
  <div id="date" class="field">תאריך: {{ date }}</div>
  <div id="sku" class="field">מק״ט פריט: {{ sku }}</div>
  <div id="expiry" class="field">תוקף: {{ expiry }}</div>

  <div id="desc">{{ desc }}</div>

  <div id="qty" class="field">כמות: {{ qty }} מ״ר | אספקה ב {{ rolls }} גלילים</div>

  <div id="batch" class="field">מס׳ מנה: {{ batch }}</div>

</div>
</body>
</html>
"""


def generate_coc_pdf(po, output):
    bg_path = ensure_background_png()

    now = datetime.now()
    date = po.po_date if getattr(po, "po_date", "") else now.strftime("%d/%m/%Y")
    expiry = f"{now.strftime('%m')}/{now.year + 8}"
    batch = f"{now.strftime('%m')}{now.strftime('%m')}/{now.year}"

    item = po.items[0]

    env = Environment(loader=BaseLoader())
    tpl = env.from_string(HTML)

    html = tpl.render(
        bg_uri=to_data_uri(bg_path),
        po=po.po_number,
        date=date,
        sku=item.sku,
        expiry=expiry,
        desc=item.description,
        qty=item.quantity,
        rolls=max(int(getattr(po, "rolls", 1) or 1), 1),
        batch=batch,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 595, "height": 842})
        page.set_content(html)
        page.pdf(
            path=str(output_path),
            width="595px",
            height="842px",
            print_background=True,
        )
        browser.close()

    return str(output_path)
