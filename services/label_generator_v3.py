from __future__ import annotations

import base64
from pathlib import Path

import fitz
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright
from .runtime_paths import PROJECT_ROOT, runtime_root


ASSETS_DIR = PROJECT_ROOT / "assets"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CACHE_DIR = runtime_root() / "output" / "_label_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_PDF = ASSETS_DIR / "label_template.pdf"
BACKGROUND_PNG = CACHE_DIR / "label_template_bg.png"


def _ensure_background_png() -> Path:
    if BACKGROUND_PNG.exists():
        return BACKGROUND_PNG

    doc = fitz.open(TEMPLATE_PDF)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    pix.save(str(BACKGROUND_PNG))
    doc.close()
    return BACKGROUND_PNG


def _to_data_uri(path: Path) -> str:
    mime = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _fit_class(text: str, limits=(30, 36, 44)):
    n = len((text or "").strip())
    if n <= limits[0]:
        return ""
    if n <= limits[1]:
        return "fit-1"
    if n <= limits[2]:
        return "fit-2"
    return "fit-3"


def generate_label_pdf(data, output="output/label_v3.pdf"):
    bg_png = _ensure_background_png()
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    tpl = env.get_template("labels/label.html")

    customer = str(data.get("customer", "")).strip()
    address = str(data.get("address", "")).strip()
    contact_name = str(data.get("contact_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    contact_line = f"{contact_name} {phone}".strip()

    po_number = str(data.get("po_number", "")).strip()

    product_lines = data.get("product_lines") or []
    item = " ".join(str(x).strip() for x in product_lines if str(x).strip())

    quantity = str(data.get("quantity", "")).strip()
    quantity_text = f"{quantity} יח׳" if quantity else ""

    sku = str(data.get("sku", "")).strip()
    sku_text = f"מק״ט {sku}" if sku else ""

    html = tpl.render(
        background_uri=_to_data_uri(bg_png),
        customer=customer,
        address=address,
        contact_line=contact_line,
        po_number=po_number,
        item=item,
        quantity_text=quantity_text,
        sku_text=sku_text,
        customer_class=_fit_class(customer, (28, 34, 40)),
        address_class=_fit_class(address, (24, 30, 36)),
        contact_class=_fit_class(contact_line, (24, 30, 38)),
        item_class=_fit_class(item, (24, 30, 38)),
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 768, "height": 1024}, device_scale_factor=1)
        page.set_content(html, wait_until="load")
        page.pdf(
            path=str(output_path),
            width="768px",
            height="1024px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()

    return str(output_path)
