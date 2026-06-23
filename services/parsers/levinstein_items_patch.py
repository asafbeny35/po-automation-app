import re
from services.models import POItem
from services.parsers.common import normalize_amount, normalize_ws

def extract_items(text: str):
    items = []

    lines = text.split("\n")

    for line in lines:
        # שורת פריט תמיד מכילה:
        # מק"ט + מ"ר + ₪
        if "מ\"ר" in line and "₪" in line:

            parts = line.split()

            # חיפוש מק״ט (8 ספרות)
            sku = ""
            for p in parts:
                if re.fullmatch(r"\d{8}", p):
                    sku = p

            # כמות (לפני מ"ר)
            qty = 0
            for i, p in enumerate(parts):
                if "מ" in p:
                    try:
                        qty = normalize_amount(parts[i-1])
                    except:
                        pass

            # מחיר יחידה (אחרי ₪)
            unit_price = 0
            for i, p in enumerate(parts):
                if "₪" in p:
                    val = p.replace("₪", "")
                    if val:
                        unit_price = normalize_amount(val)
                    else:
                        unit_price = normalize_amount(parts[i+1])

            # סכום שורה = המספר האחרון
            line_total = 0
            nums = [normalize_amount(x) for x in parts if re.match(r"[\d,]+\.\d+", x)]
            if nums:
                line_total = nums[-1]

            # תיאור = כל מה שבין מק״ט לכמות
            desc = ""
            if sku:
                try:
                    sku_index = parts.index(sku)
                    # נמצא את האינדקס של הכמות
                    qty_index = None
                    for i, p in enumerate(parts):
                        if "מ" in p:
                            qty_index = i - 1
                            break

                    if qty_index:
                        desc = " ".join(parts[sku_index+1:qty_index])
                except:
                    pass

            items.append(
                POItem(
                    sku=sku,
                    description=normalize_ws(desc),
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total
                )
            )

    return items
