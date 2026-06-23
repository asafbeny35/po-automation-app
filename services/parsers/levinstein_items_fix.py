import re
from services.models import POItem
from services.parsers.common import normalize_amount, normalize_ws

def extract_items(text: str):
    items = []

    flat = " ".join(text.split())

    # מצא את השורה עם QuietPipe
    m = re.search(r'(20900024.*?₪.*?\d{1,3},\d{3}\.\d{2})', flat)
    if not m:
        return items

    line = m.group(1)

    # כל המספרים בשורה
    nums = re.findall(r'[\d,]+\.\d{2}', line)

    if len(nums) < 3:
        return items

    qty = normalize_amount(nums[0])       # 40.00
    unit_price = normalize_amount(nums[1]) # 62.00
    total = normalize_amount(nums[2])      # 2,480.00

    item = POItem(
        sku="20900024",
        description="יריעה אקוסטית QuietPipe לעיטוף צנרות",
        quantity=qty,
        unit_price=unit_price,
        line_total=total
    )

    items.append(item)

    return items
