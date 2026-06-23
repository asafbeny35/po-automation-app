import sys
import json
from pathlib import Path
from datetime import datetime
import fitz
import base64
from jinja2 import Environment, BaseLoader
from playwright.sync_api import sync_playwright

print("🔥 NEW COC GENERATOR RUNNING")

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
HTML_PATH = BASE_DIR / "scripts" / "coc_html.txt"
TEMPLATE_PDF = ASSETS_DIR / "coc_template.pdf"


def to_data_uri(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def render_bg():
    doc = fitz.open(TEMPLATE_PDF)
    pix = doc[0].get_pixmap()
    path = BASE_DIR / "output/_coc_bg.png"
    pix.save(path)
    doc.close()
    return path


def main():
    data = json.loads(sys.argv[1])
    output = sys.argv[2]

    now = datetime.now()

    html_template = HTML_PATH.read_text()

    env = Environment(loader=BaseLoader())
    tpl = env.from_string(html_template)

    bg_path = render_bg()

    html = tpl.render(
        bg=to_data_uri(bg_path),
        po=data["po"],
        date=data.get("date") or now.strftime("%d/%m/%Y"),
        sku=data["sku"],
        expiry=f"{now.strftime('%m')}/{now.year + 8}",
        desc=data["desc"],
        qty=data["qty"],
        rolls=max(int(data.get("rolls") or 1), 1),
        batch=f"{now.strftime('%m')}{now.strftime('%m')}/{now.year}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        page.pdf(path=output, width="595px", height="842px", print_background=True)
        browser.close()


if __name__ == "__main__":
    main()
