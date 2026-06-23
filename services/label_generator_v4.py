from __future__ import annotations

import base64
from pathlib import Path

import fitz
from jinja2 import Environment, BaseLoader
from playwright.sync_api import sync_playwright
from .runtime_paths import PROJECT_ROOT, runtime_root

ASSETS_DIR = PROJECT_ROOT / "assets"
CACHE_DIR = runtime_root() / "output" / "_label_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_PDF = ASSETS_DIR / "label_template.pdf"
BACKGROUND_PNG = CACHE_DIR / "label_template_bg_595x842.png"


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
  html, body {
    margin: 0;
    padding: 0;
    width: 595px;
    height: 842px;
    overflow: hidden;
    background: white;
    font-family: Arial, "Arial Hebrew", "Noto Sans Hebrew", sans-serif;
  }

  .page {
    position: relative;
    width: 595px;
    height: 842px;
    overflow: hidden;
  }

  .bg {
    position: absolute;
    inset: 0;
    width: 595px;
    height: 842px;
  }

  .box {
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #111;
    box-sizing: border-box;
    overflow: hidden;
    white-space: nowrap;
  }

  .box.multiline {
    white-space: normal;
  }

  .rtl {
    direction: rtl;
    unicode-bidi: plaintext;
  }

  .ltr {
    direction: ltr;
    unicode-bidi: plaintext;
  }

  .mix {
    direction: rtl;
    unicode-bidi: plaintext;
  }

  .fit {
    display: inline-block;
    line-height: 1;
    transform-origin: center center;
  }

  /* exact boxes from your marked PNG */
  #customer { left: 50px; top: 29px; width: 418px; height: 25px; }
  #address  { left: 49px; top: 68px; width: 418px; height: 25px; }
  #contact  { left: 49px; top: 106px; width: 396px; height: 25px; }

  #po       { left: 49px; top: 208px; width: 364px; height: 24px; }
  #item     { left: 49px; top: 238px; width: 364px; height: 56px; }
  #qty      { left: 49px; top: 291px; width: 364px; height: 25px; }

  /* note: your pink box for SKU is ONLY the numeric value, because "מק״ט" is already printed on template */
  #sku      { left: 50px; top: 358px; width: 329px; height: 25px; }

  #customer .fit { font-size: 22px; font-weight: 400; }
  #address  .fit { font-size: 22px; font-weight: 400; }
  #contact  .fit { font-size: 20px; font-weight: 400; }

  #po       .fit { font-size: 24px; font-weight: 400; }
  #item     .fit { font-size: 18px; font-weight: 400; line-height: 1.15; white-space: pre-line; }
  #qty      .fit { font-size: 24px; font-weight: 400; }
  #sku      .fit { font-size: 24px; font-weight: 700; }

  .contact-wrap {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    direction: rtl;
  }

  .debug {
    outline: 1px solid rgba(255,0,0,0.45);
  }
</style>
</head>
<body>
<div class="page">
  <img class="bg" src="{{ bg_uri }}" alt="">

  <div id="customer" class="box {% if debug %}debug{% endif %}">
    <span class="fit rtl">{{ customer }}</span>
  </div>

  <div id="address" class="box {% if debug %}debug{% endif %}">
    <span class="fit rtl">{{ address }}</span>
  </div>

  <div id="contact" class="box {% if debug %}debug{% endif %}">
    <span class="fit contact-wrap">
      <span class="rtl">{{ contact_name }}</span>
      <span class="ltr">{{ phone }}</span>
    </span>
  </div>

  <div id="po" class="box {% if debug %}debug{% endif %}">
    <span class="fit ltr">{{ po_number }}</span>
  </div>

  <div id="item" class="box multiline {% if debug %}debug{% endif %}">
    <span class="fit rtl">{{ item }}</span>
  </div>

  <div id="qty" class="box {% if debug %}debug{% endif %}">
    <span class="fit contact-wrap">
      <span class="ltr">{{ quantity }}</span>
      <span class="rtl">{{ unit }}</span>
    </span>
  </div>

  <div id="sku" class="box {% if debug %}debug{% endif %}">
    <span class="fit ltr">{{ sku }}</span>
  </div>
</div>

<script>
function fitOne(el, minPx) {
  const span = el.querySelector('.fit');
  if (!span) return;

  let size = parseFloat(getComputedStyle(span).fontSize);
  while ((span.scrollWidth > el.clientWidth || span.scrollHeight > el.clientHeight) && size > minPx) {
    size -= 0.5;
    span.style.fontSize = size + 'px';
  }
}

for (const id of ['customer','address','contact','po','item','qty','sku']) {
  fitOne(document.getElementById(id), 10);
}
</script>
</body>
</html>
"""


def generate_label_pdf(data, output="output/label_v4.pdf", debug=False):
    bg_path = ensure_background_png()
    env = Environment(loader=BaseLoader(), autoescape=True)
    tpl = env.from_string(HTML)

    html = tpl.render(
        bg_uri=to_data_uri(bg_path),
        customer=str(data.get("customer", "") or "").strip(),
        address=str(data.get("address", "") or "").strip(),
        contact_name=str(data.get("contact_name", "") or "").strip(),
        phone=str(data.get("phone", "") or "").strip(),
        po_number=str(data.get("po_number", "") or "").strip(),
        item="\n".join(str(x).strip() for x in (data.get("product_lines") or []) if str(x).strip()),
        quantity=str(data.get("quantity", "") or "").strip(),
        sku=str(data.get("sku", "") or "").strip(),
        unit=str(data.get("unit", "") or "יח׳").strip() or "יח׳",
        debug=debug,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 595, "height": 842}, device_scale_factor=1)
        page.set_content(html, wait_until="load")
        page.pdf(
            path=str(output_path),
            width="595px",
            height="842px",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            print_background=True,
        )
        browser.close()

    return str(output_path)
