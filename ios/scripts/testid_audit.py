#!/usr/bin/env python3
"""ביקורת קיום הפוכה — כל מזהה שטסטי ה-UI מחפשים חייב להתקיים באפליקציה.

טעות הקלדה במזהה בתוך טסט מתגלה רק בריצה (ולפעמים נבלעת ב-waitForExistence
עם fallback). כאן משווים בזמן בילד: כל מחרוזת שמופיעה ב-BenYacovManageUITests
בתוך element("X") / buttons["X"] / switches["X"] וכו' חייבת להיות מזהה שקיים
בקוד האפליקציה (מילולית, כפרמטר id:, או בתחילית דינמית מוכרת).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

IOS_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = IOS_ROOT / "BenYacovManage"
SHARE_DIR = IOS_ROOT / "BenYacovShare"
UITESTS_DIR = IOS_ROOT / "BenYacovManageUITests"

# תחיליות דינמיות: המזהה נבנה בקוד עם אינטרפולציה (row-\(domain) וכו').
DYNAMIC_PREFIXES = (
    "row-", "chip-", "hub-", "action-", "form-", "more-",
    "composer-field-", "invoice-field-", "quote-field-", "supplier-field-",
    "accountant-due-", "domain-list-", "visit-item-",
    "home-domain-", "method-", "user-",
    # שורות הפריטים בקומפוזרים ממוספרות: "\(idPrefix)-item-<field>-\(index)"
    "quote-item-", "order-item-",
)

# סיומות שנבנות מ-submitID בגיליונות השליחה: "\(submitID)-phone" וכו'.
DYNAMIC_SUFFIXES = ("-phone", "-message", "-field", "-test-toggle")

# פקדי מערכת שמחפשים לפי label סטנדרטי (לא מזהה שלנו).
SYSTEM_LABELS = {"Cancel", "Select All", "Done"}

# תוויות בעברית/מערכת שאינן מזהים (כפתורי תפריט לפי label וכו').
NOT_IDENTIFIERS = re.compile(r"[֐-׿ ]|^(Select All)$")


def referenced_ids() -> set[str]:
    ids: set[str] = set()
    patterns = [
        r'element\("([^"]+)"\)',
        r'\.buttons\["([^"]+)"\]',
        r'\.switches\["([^"]+)"\]',
        r'\.textFields\["([^"]+)"\]',
        r'\.staticTexts\["([^"]+)"\]',
        r'\.otherElements\["([^"]+)"\]',
        r'tapChip\("([^"]+)"\)',
        r'waitForRows\("([^"]+)"\)',
        r'openAndCloseFirstRecord\("([^"]+)"\)',
    ]
    for swift in UITESTS_DIR.rglob("*.swift"):
        text = swift.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = match.group(1)
                if "\\(" in value:
                    continue  # אינטרפולציה בתוך הטסט עצמו
                if NOT_IDENTIFIERS.search(value):
                    continue  # תווית עברית — חיפוש לפי label, לא מזהה
                # tapChip/waitForRows מקבלים rawValue של דומיין — הופכים למזהה המלא.
                if pattern.startswith(("r'tapChip", "r'waitForRows", "r'openAndClose")):
                    pass
                ids.add(value)
    return ids


def app_ids() -> set[str]:
    ids: set[str] = set()
    for root in (APP_DIR, SHARE_DIR):
        for swift in root.rglob("*.swift"):
            text = swift.read_text(encoding="utf-8")
            for match in re.finditer(r'accessibilityIdentifier\("([^"\\]+)"\)', text):
                ids.add(match.group(1))
            for match in re.finditer(r'\b(?:id|submitID):\s*"([^"]+)"', text):
                ids.add(match.group(1))
            # מזהים עם אינטרפולציה — התחילית הופכת ל-wildcard (customer-type-*).
            for match in re.finditer(r'accessibilityIdentifier\("([^"\\]+)\\\(', text):
                ids.add(match.group(1) + "*")
    return ids


def domain_raw_values() -> set[str]:
    text = (APP_DIR / "Core" / "Domain.swift").read_text(encoding="utf-8")
    return {m.group(1) for m in re.finditer(r'case \w+ = "([^"]+)"', text)}


def main() -> int:
    refs = referenced_ids()
    known = app_ids()
    domains = domain_raw_values()

    missing: list[str] = []
    for ref in sorted(refs):
        if ref in known:
            continue
        if ref in domains:
            continue  # rawValue של דומיין (tapChip/waitForRows בונים את המזהה)
        if any(ref.startswith(prefix) for prefix in DYNAMIC_PREFIXES):
            continue
        if any(candidate.endswith("*") and ref.startswith(candidate[:-1]) for candidate in known):
            continue
        if ref in SYSTEM_LABELS:
            continue
        # מזהה עם סיומת דינמית: הגזע (submitID) חייב להתקיים.
        stem_ok = False
        for suffix in DYNAMIC_SUFFIXES:
            if ref.endswith(suffix) and ref[: -len(suffix)] in known:
                stem_ok = True
                break
        if stem_ok:
            continue
        missing.append(ref)

    print(f"🔎 ביקורת מזהי טסטים: {len(refs)} מזהים בשימוש בטסטים, {len(known)} בקוד האפליקציה")
    if missing:
        print("\n❌ מזהים שהטסטים מחפשים ולא קיימים באפליקציה (טעות הקלדה?):")
        for ref in missing:
            print(f"  {ref}")
        return 1
    print("✅ כל מזהי הטסטים קיימים באפליקציה.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
