from pathlib import Path

file_path = Path("services/parsers/common.py")
content = file_path.read_text()

start = content.find("def normalize_amount")
end = content.find("def normalize_date")

if start == -1 or end == -1:
    print("❌ לא נמצא normalize_amount")
    exit()

new_func = '''
def normalize_amount(value):
    if value is None:
        return None

    value = str(value)

    # ניקוי טקסט
    value = value.replace("₪", "").replace('ש"ח', "").replace("שח", "").strip()

    # תיקון RTL (מספרים הפוכים)
    if "," in value and "." in value:
        parts = value.split(",")
        if len(parts) == 2:
            left = parts[0].replace(".", "")
            right = parts[1]
            if left.isdigit() and right.isdigit():
                value = right + left

    # ניקוי פסיקים
    value = value.replace(",", "")

    try:
        return float(value)
    except Exception:
        return None
'''

new_content = content[:start] + new_func + "\n\n" + content[end:]
file_path.write_text(new_content)

print("✅ normalize_amount patched safely")
