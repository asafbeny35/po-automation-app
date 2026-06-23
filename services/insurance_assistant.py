from __future__ import annotations

import json

import httpx

from .config import settings


INSURANCE_CONTEXT = {
    "insured_name": "אסף בן יעקב",
    "mortgage_life": [
        {
            "company": "ליברה",
            "policy_number": "1227683972923",
            "type": "ביטוח חיים למשכנתא",
            "property_address": "רוטשילד 8א, חיפה",
            "bank": "בנק מזרחי טפחות - 20",
            "branch": "421",
            "valid_from": "04/10/2023",
            "valid_until": "30/09/2039",
            "monthly_premium_nis": 24,
            "insured_sum_nis": 415400,
            "essence": "במקרה מוות משולמת יתרת ההלוואה לבנק המוטב, ואם סכום הביטוח גבוה מיתרת ההלוואה - ההפרש עובר למוטבים או ליורשים.",
        },
        {
            "company": "ליברה",
            "policy_number": "1227684229323",
            "type": "ביטוח חיים למשכנתא",
            "property_address": "הגורן 34, עתלית",
            "bank": "בנק דיסקונט - 11",
            "branch": "131",
            "valid_from": "04/10/2023",
            "valid_until": "31/01/2039",
            "monthly_premium_nis": 42,
            "insured_sum_nis": 740000,
            "essence": "במקרה מוות משולמת יתרת ההלוואה לבנק המוטב, ואם סכום הביטוח גבוה מיתרת ההלוואה - ההפרש עובר למוטבים או ליורשים.",
        },
    ],
    "home_insurance": [
        {
            "company": "מגדל",
            "policy_number": "1800600336/25",
            "type": "ביטוח דירה",
            "property_address": "הירשנברג 16/8, תל אביב - יפו",
            "valid_from": "01/08/2025",
            "valid_until": "31/07/2026",
            "annual_premium_nis": 483,
            "agent": "עלמני דליה",
            "essence": "ביטוח דירה ותכולה עם כיסוי רעידת אדמה, אחריות צד שלישי וחבות מעבידים לעובדי משק בית.",
            "coverage_highlights": [
                "תכולה בסך 158,119 ש\"ח",
                "כיסוי רעידת אדמה לתכולה",
                "אחריות צד שלישי עד 1,000,000 ש\"ח למקרה ועד 2,000,000 ש\"ח לתקופה",
                "חבות מעבידים לעובדי משק בית עד 7,500,000 ש\"ח",
            ],
        }
    ],
    "business_insurance": [
        {
            "company": "הפניקס",
            "policy_number": "26/148/632/1001590",
            "type": "ביטוח EXTRA לבתי מלאכה",
            "property_address": "שד ההסתדרות 228, חיפה",
            "insured_address": "הגורן 34, עתלית",
            "valid_from": "01/01/2026",
            "valid_until": "31/12/2026",
            "annual_premium_nis": 6576,
            "agent": "עלמני דליה",
            "essence": "ביטוח מפעל הכולל תכולת עסק, נזקי טבע, רעידת אדמה וחבות מעבידים לבית מלאכה לעיבוד מתכות.",
            "coverage_highlights": [
                "ריהוט, מכונות וקבועות: 1,024,207 ש\"ח",
                "מלאי בבית המלאכה: 116,388 ש\"ח",
                "נזקי טבע ורעידת אדמה: 1,140,595 ש\"ח",
                "חבות מעבידים: עובדי משרד ומכירות עד 1, עובדי כפיים עד 2",
                "שכר עבודה מבוטח: 20,000 ש\"ח",
            ],
            "official_site": "https://www.fnx.co.il",
        }
    ],
    "health_insurance": [
        {
            "company": "הפניקס",
            "policy_number": "2298523081",
            "type": "ביטוח בריאות",
            "valid_until": "01/06/2026",
            "monthly_premium_nis": 168.13,
            "essence": "כיסויי בריאות משלימים הכוללים מחלות קשות, אבחנה מהירה, ניתוחים והשתלות בחו\"ל ותרופות מורחבות.",
            "coverage_highlights": [
                "מרפא 2020 - פיצוי בגין מחלות קשות",
                "אבחנה מהירה",
                "הוצאות לניתוחים ומחליפי ניתוח בחו\"ל",
                "השתלות וטיפולים מיוחדים בחו\"ל",
                "תרופות אקסטרה 2021",
                "סל הזהב - תרופות שלא בסל",
            ],
            "contact": "03-7332222 / *3455",
            "official_site": "https://www.fnx.co.il",
        },
        {
            "company": "מגדל",
            "policy_number": "אוסף נספחי בריאות 2026",
            "type": "ביטוח בריאות",
            "valid_until": "לפי נספחים",
            "agent": "עלמני דליה",
            "essence": "מעטפת בריאות הכוללת ניתוחים בישראל, שירות אמבולטורי, רפואה משלימה ורכיבי סיעוד.",
            "coverage_highlights": [
                "נספח ניתוחים בישראל מורחב",
                "שירות אמבולטורי",
                "כתב שירות רפואה משלימה",
                "פוליסת סיעוד",
            ],
            "contact": "073-2049160",
            "official_site": "https://www.migdal.co.il",
        },
    ],
    "pension": [
        {
            "company": "הפניקס",
            "policy_number": "9078204014",
            "type": "פנסיה מקיפה",
            "join_date": "01/12/2009",
            "agent": "דבש יונאל",
            "investment_tracks": [
                "הפניקס פנסיה מקיפה אשראי ואג\"ח",
                "הפניקס פנסיה מקיפה עוקב מדד S&P 500",
            ],
            "fees": {
                "deposits_percent": 1.30,
                "balance_percent": 0.15,
            },
            "risk_profile": "משלב מסלול אג\"ח/אשראי לצד מסלול מנייתי עוקב מדד S&P 500, ולכן רמת הסיכון תלויה במסלול שנבחר בפועל.",
            "yield_note": "נתוני תשואה רשמיים יש לבדוק דרך הקישורים הרשמיים של רשות שוק ההון והפניקס.",
            "official_links": [
                "https://my.fnx.co.il",
                "https://www.fnx.co.il/calculators/year/",
                "https://insurancedata.cma.gov.il/Pages/Entry.aspx",
            ],
        },
        {
            "company": "הפניקס",
            "policy_number": "7151887010",
            "type": "פנסיה משלימה",
            "join_date": "01/02/2020",
            "agent": "דבש יונאל",
            "investment_tracks": [
                "הפניקס פנסיה משלימה לבני 50 ומטה - תלוי גיל",
            ],
            "fees": {
                "deposits_percent": 4.00,
                "balance_percent": 1.05,
            },
            "risk_profile": "מסלול תלוי גיל עם רכיב מנייתי מותאם לגיל, ולכן רמת הסיכון צפויה להשתנות לאורך השנים.",
            "yield_note": "נתוני תשואה רשמיים יש לבדוק דרך הקישורים הרשמיים של רשות שוק ההון והפניקס.",
            "official_links": [
                "https://my.fnx.co.il",
                "https://www.fnx.co.il/calculators/year/",
                "https://insurancedata.cma.gov.il/Pages/Entry.aspx",
            ],
        },
    ],
}


async def _ask_openai(question: str, context: dict) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("חסר OPENAI_API_KEY ולכן לא ניתן להפעיל את עוזר הביטוחים.")

    developer_prompt = (
        "אתה עוזר ביטוחי אישי בעברית. "
        "ענה בעברית בלבד, קצר, ברור וזהיר. "
        "ענה רק על סמך ההקשר שניתן לך. "
        "אם חסר נתון, אמור שחסר. "
        "אל תמציא כיסויים, תשואות או עלויות שלא קיימים בהקשר. "
        "אם נשאלים על תשואה, סיכון או ביצועים, הפנה קודם לקישורים הרשמיים כאשר אין לך נתון מספרי מאומת."
    )

    payload = {
        "question": question,
        "context": context,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "input": [
                    {"role": "developer", "content": [{"type": "input_text", "text": developer_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()

    if isinstance(data.get("output_text"), str) and data.get("output_text").strip():
        return data["output_text"].strip()

    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    raise RuntimeError("מודל ה-AI לא החזיר תשובה קריאה.")


def _fallback_answer(question: str, context: dict) -> str:
    question = (question or "").strip()
    if not question:
        return "כתוב כאן שאלה על אחת הפוליסות, ואנסה לכוון אותך לפי הנתונים ששמורים במערכת."

    lower = question.lower()
    if "משכנתא" in lower or "ליברה" in lower:
        return (
            "יש לך שני ביטוחי חיים למשכנתא בליברה על הנכסים ברוטשילד 8א, חיפה ובהגורן 34, עתלית. "
            "אחד משויך לבנק מזרחי טפחות והשני לבנק דיסקונט. "
            "הפרמיות החודשיות הן 24 ש\"ח ו-42 ש\"ח בהתאמה."
        )
    if "דירה" in lower or "מגדל" in lower:
        return (
            "ביטוח הדירה נמצא במגדל לבית, פוליסה 1800600336/25, בתוקף עד 31/07/2026, "
            "עם פרמיה שנתית של 483 ש\"ח ועם כיסויי תכולה, רעידת אדמה, צד שלישי וחבות מעבידים."
        )
    if "פנסיה" in lower or "תשואה" in lower or "סיכון" in lower:
        return (
            "יש לך שתי פוליסות פנסיה בהפניקס: מקיפה ומשלימה. "
            "לבדיקת תשואות ונתונים רשמיים כדאי לפתוח את הקישורים של הפניקס ושל רשות שוק ההון שמופיעים בכרטיסי הפנסיה."
        )
    if "בריאות" in lower or "רפוא" in lower:
        return (
            "יש לך כיסויי בריאות בהפניקס ובמגדל. "
            "בהפניקס מופיעים מחלות קשות, אבחנה מהירה, ניתוחים והשתלות בחו\"ל ותרופות מורחבות. "
            "במגדל מופיעים ניתוחים בישראל, אמבולטורי, רפואה משלימה וסיעוד."
        )
    return (
        "אפשר לשאול על ביטוחי המשכנתא בליברה, על ביטוח הדירה במגדל, על כיסויי הבריאות, "
        "או על מסלולי הפנסיה והמסמכים שלהם."
    )


async def answer_insurance_question(question: str) -> dict:
    question = (question or "").strip()
    if not question:
        raise RuntimeError("חסרה שאלה על הביטוחים.")

    try:
        answer = await _ask_openai(question, INSURANCE_CONTEXT)
    except Exception:
        answer = _fallback_answer(question, INSURANCE_CONTEXT)

    return {
        "answer": answer,
        "context": INSURANCE_CONTEXT,
    }
