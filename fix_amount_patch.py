import re
from pathlib import Path

file_path = Path("services/parsers/common.py")
content = file_path.read_text()

new_func = '''
def normalize_amount(value):
    if value is None:
        return None

    value = str(value)

    # ניקוי טקסט
    value = value.replace("₪", "").replace('ש"ח', "").replace("שח", "").strip()

    # אם יש פסיק אחרי הנקודה → כנראה RTL
    if re.match(r"^0*\\.\\d+,\\d+$", value):
        parts = value.split(",")
        left = parts[0].replace(".", "")
        right = parts[1]
        value = right + left  # הופכים

    # אם יש מבנה כמו 00.556,2
    if re.match(r"^\\d+\\.\\d+,\\d+$", value):
        parts = value.split(",")
        left = parts[0].replace(".", "")
        right = parts[1]
        value = right + left

    # ניקוי פסיקים
    value = value.replace(",", "")

    try:
        return float(value)
    except Exception:
        return None
'''

# החלפה בפועל
content = re.sub(
    r"def normalize_amount\\(.*?\\n\\s*return None",
    new_func.strip(),
    content,
    flags=re.DOTALL
)

file_path.write_text(content)
print("✅ normalize_amount patched")
