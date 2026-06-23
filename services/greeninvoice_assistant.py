from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from calendar import monthrange

import httpx

from .config import settings
from .greeninvoice import (
    GreenInvoiceClient,
    _canonical_income_customer_name,
    _extract_receipt_invoice_numbers,
    _normalize_income_customer_name,
)

MONTH_NAME_TO_NUMBER = {
    "ינואר": 1,
    "פברואר": 2,
    "מרץ": 3,
    "אפריל": 4,
    "מאי": 5,
    "יוני": 6,
    "יולי": 7,
    "אוגוסט": 8,
    "ספטמבר": 9,
    "אוקטובר": 10,
    "נובמבר": 11,
    "דצמבר": 12,
}

NUMBER_TO_MONTH_NAME = {value: key for key, value in MONTH_NAME_TO_NUMBER.items()}

QUESTION_SYNONYMS = (
    ("מכרתי", "הכנסות"),
    ("מכרנו", "הכנסות"),
    ("מחזור", "הכנסות"),
    ("שילם", "תקבול"),
    ("שילמו", "תקבול"),
    ("שולם", "תקבול"),
    ("שולמו", "תקבול"),
    ("גבינו", "תקבול"),
    ("קיבלנו", "תקבול"),
    ("התקבל", "תקבול"),
    ("התקבלו", "תקבול"),
    ("חשבוניות מס", "חשבוניות"),
    ("מסמכים", "חשבוניות"),
)


def _month_start_months_ago(months_back: int) -> date:
    today = date.today()
    year = today.year
    month = today.month - (months_back - 1)
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _build_greeninvoice_client(mode: str) -> GreenInvoiceClient:
    if mode == "sandbox":
        return GreenInvoiceClient(
            base_url=settings.greeninvoice_sandbox_base_url,
            api_key=settings.greeninvoice_sandbox_api_key,
            api_secret=settings.greeninvoice_sandbox_api_secret,
        )

    return GreenInvoiceClient(
        base_url=settings.greeninvoice_prod_base_url,
        api_key=settings.greeninvoice_prod_api_key,
        api_secret=settings.greeninvoice_prod_api_secret,
    )


def _build_income_context(documents: list[dict]) -> dict:
    monthly_totals = defaultdict(float)
    customer_totals = defaultdict(float)
    document_count_by_month = defaultdict(int)

    for doc in documents:
        doc_date = str(doc.get("date") or "")
        month_key = doc_date[:7] if len(doc_date) >= 7 else ""
        amount = float(doc.get("amount") or 0)
        customer_name = str(doc.get("customer_name") or "ללא שם").strip() or "ללא שם"

        if month_key:
            monthly_totals[month_key] += amount
            document_count_by_month[month_key] += 1
        customer_totals[customer_name] += amount

    monthly_rows = [
        {
            "month": month,
            "income_total": round(total, 2),
            "documents": document_count_by_month.get(month, 0),
        }
        for month, total in sorted(monthly_totals.items())
    ]
    customer_rows = [
        {
            "customer_name": customer,
            "income_total": round(total, 2),
        }
        for customer, total in sorted(customer_totals.items(), key=lambda item: item[1], reverse=True)[:20]
    ]

    return {
        "documents_count": len(documents),
        "income_total": round(sum(float(doc.get("amount") or 0) for doc in documents), 2),
        "monthly_totals": monthly_rows,
        "top_customers": customer_rows,
        "sample_documents": documents[:50],
    }


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _normalize_question(question: str) -> str:
    text = re.sub(r"\s+", " ", str(question or "").strip().lower())
    for old, new in QUESTION_SYNONYMS:
        text = text.replace(old, new)
    return text


def _wants_invoice_only(question: str) -> bool:
    question = (question or "").lower()
    return "חשבונית" in question or "חשבוניות" in question


def _wants_credit_notes(question: str) -> bool:
    question = (question or "").lower()
    return "זיכוי" in question or "זיכויים" in question or "credit" in question


def _question_requests_income_aggregation(question: str) -> bool:
    normalized = _normalize_question(question)
    markers = (
        "הכנסות",
        "מכרתי",
        "מכרנו",
        "מחזור",
        "סך",
        "כמה כסף",
        "בכמה כסף",
        "השווא",
        "לעומת",
        "מול",
        "אשתקד",
        "שנה שעברה",
        "פער",
        "עלייה",
        "ירידה",
        "אחוז",
    )
    return any(marker in normalized for marker in markers)


def _invoice_type_codes() -> set[str]:
    return {
        str(settings.greeninvoice_tax_invoice_doc_type or "305"),
        "320",
    }


def _is_credit_document(doc: dict) -> bool:
    type_text = str(doc.get("type") or "").strip().lower()
    type_code = str(doc.get("type_code") or "").strip()
    return type_code == "320" or "זיכוי" in type_text or "credit" in type_text


def _is_invoice_or_credit_document(doc: dict) -> bool:
    type_text = str(doc.get("type") or "").strip().lower()
    type_code = str(doc.get("type_code") or "").strip()
    if type_code in _invoice_type_codes():
        return True
    if _is_credit_document(doc):
        return True
    looks_like_invoice = ("חשבונית" in type_text) or ("invoice" in type_text)
    looks_like_receipt = ("קבלה" in type_text) or ("receipt" in type_text)
    looks_like_delivery = ("תעודת משלוח" in type_text) or ("delivery" in type_text)
    looks_like_quote = ("הצעת מחיר" in type_text) or ("quote" in type_text)
    return looks_like_invoice and not looks_like_receipt and not looks_like_delivery and not looks_like_quote


def _income_documents_for_aggregation(documents: list[dict]) -> list[dict]:
    return [doc for doc in (documents or []) if _is_invoice_or_credit_document(doc)]


def _filter_documents_for_question(documents: list[dict], question: str) -> list[dict]:
    question = (question or "").strip()
    if not question:
        return documents

    invoice_only = _wants_invoice_only(question)
    include_credits = _wants_credit_notes(question) or _question_requests_income_aggregation(question)

    filtered = []
    for doc in documents:
        doc_type = str(doc.get("type") or "").lower()
        doc_type_code = str(doc.get("type_code") or "").strip()

        if invoice_only:
            looks_like_invoice = ("חשבונית" in doc_type) or ("invoice" in doc_type) or (doc_type_code in _invoice_type_codes())
            if not looks_like_invoice:
                continue

        if not include_credits and ("זיכוי" in doc_type or "credit" in doc_type):
            continue

        filtered.append(doc)

    return filtered


def _extract_month_mentions(question: str) -> list[int]:
    question = _normalize_question(question or "")
    found = []
    for month_name, month_number in MONTH_NAME_TO_NUMBER.items():
        if month_name in question:
            found.append((question.index(month_name), month_number))
    return [month for _, month in sorted(found, key=lambda item: item[0])]


def _extract_relative_month(question: str, today: date) -> list[int]:
    question = _normalize_question(question)
    if "החודש שעבר" in question:
        month = today.month - 1 or 12
        return [month]
    if "החודש" in question:
        return [today.month]
    return []


def _sum_documents_between(documents: list[dict], start_date: date, end_date: date) -> float:
    total = 0.0
    for doc in documents:
        doc_date = _parse_iso_date(str(doc.get("date") or ""))
        if not doc_date:
            continue
        if start_date <= doc_date <= end_date:
            total += float(doc.get("amount") or 0)
    return round(total, 2)


def _documents_count_between(documents: list[dict], start_date: date, end_date: date) -> int:
    count = 0
    for doc in documents:
        doc_date = _parse_iso_date(str(doc.get("date") or ""))
        if doc_date and start_date <= doc_date <= end_date:
            count += 1
    return count


def _format_currency(value: float) -> str:
    return f"₪ {value:,.2f}"


def _format_percent(value: float) -> str:
    return f"{value:.2f}%"


def _question_requests_period_comparison(question: str) -> bool:
    question = _normalize_question(question)
    comparison_markers = (
        "יחס",
        "השווא",
        "לעומת",
        "מול",
        "אשתקד",
        "שנה שעברה",
        "המקבילה",
        "עלייה",
        "ירידה",
        "אחוז",
        "פער",
    )
    return any(marker in question for marker in comparison_markers)


def _documents_between(documents: list[dict], start_date: date, end_date: date) -> list[dict]:
    selected = []
    for doc in documents:
        doc_date = _parse_iso_date(str(doc.get("date") or ""))
        if not doc_date:
            continue
        if start_date <= doc_date <= end_date:
            selected.append(doc)
    return selected


def _documents_coverage(documents: list[dict]) -> tuple[date | None, date | None]:
    months_back = max(int(settings.greeninvoice_assistant_months_back or 36), 1)
    return _month_start_months_ago(months_back), date.today()


def _coverage_message(request_start: date, request_end: date, available_start: date | None, available_end: date | None) -> str | None:
    if not available_start or not available_end:
        return "לא הצלחתי לזהות טווח נתונים תקין מהמסמכים שחזרו מה־API."
    if request_start < available_start or request_end > available_end:
        return (
            f"אין לי כרגע כיסוי מלא לתקופה שביקשת. "
            f"הנתונים שחזרו מה־API מכסים רק את הטווח {available_start.isoformat()} עד {available_end.isoformat()}, "
            f"ולכן תשובה על {request_start.isoformat()} עד {request_end.isoformat()} תהיה חלקית ולא אמינה."
        )
    return None


def _question_requests_customer_list(question: str) -> bool:
    question = _normalize_question(question)
    customer_markers = (
        "רשימת כל הלקוחות",
        "רשימת הלקוחות",
        "כל הלקוחות",
        "אילו לקוחות",
        "איזה לקוחות",
        "מי הלקוחות",
        "לקוחות שונים",
    )
    return ("לקוח" in question or "לקוחות" in question) and any(marker in question for marker in customer_markers)


def _extract_explicit_year(question: str) -> int | None:
    match = re.search(r"(20\d{2})", question or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _extract_explicit_years(question: str) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()
    for match in re.finditer(r"(20\d{2})", question or ""):
        try:
            year = int(match.group(1))
        except Exception:
            continue
        if year in seen:
            continue
        seen.add(year)
        found.append(year)
    return found


def _extract_target_year(question: str, today: date) -> int | None:
    explicit = _extract_explicit_year(question)
    if explicit:
        return explicit
    normalized = _normalize_question(question)
    if "אשתקד" in normalized or "שנה שעברה" in normalized:
        return today.year - 1
    if "השנה" in normalized:
        return today.year
    return None


def _extract_period(question: str, today: date) -> tuple[date, date] | None:
    months = _extract_month_mentions(question) or _extract_relative_month(question, today)
    target_year = _extract_target_year(question, today)
    normalized = _normalize_question(question)

    if months:
        start_month = months[0]
        end_month = months[-1]
        year = target_year or today.year
        end_day = today.day if ("עד כה" in normalized or "עד היום" in normalized) and year == today.year and end_month == today.month else monthrange(year, end_month)[1]
        return date(year, start_month, 1), date(year, end_month, end_day)

    if target_year:
        end_date = today if ("עד כה" in normalized or "עד היום" in normalized) and target_year == today.year else date(target_year, 12, 31)
        return date(target_year, 1, 1), end_date

    return None


def _document_amount(doc: dict) -> float:
    try:
        return round(float(doc.get("amount") or 0), 2)
    except Exception:
        return 0.0


def _documents_for_customer(documents: list[dict], customer_name: str) -> list[dict]:
    wanted = _canonical_income_customer_name(customer_name)
    return [
        doc for doc in documents
        if _canonical_income_customer_name(doc.get("customer_name") or "") == wanted
    ]


def _question_requests_top_customer(question: str) -> bool:
    question = _normalize_question(question)
    markers = ("הלקוח הכי", "הלקוח הגדול", "מי הלקוח", "איזה לקוח", "לקוח מוביל", "לקוח הכי חזק")
    return any(marker in question for marker in markers)


def _question_requests_top_month(question: str) -> bool:
    question = _normalize_question(question)
    markers = ("איזה חודש", "החודש הכי", "חודש הכי חזק", "חודש הכי טוב", "החודש החזק")
    return any(marker in question for marker in markers)


def _question_requests_average(question: str) -> bool:
    question = _normalize_question(question)
    markers = ("ממוצע", "ממוצעת", "ממוצעות")
    return any(marker in question for marker in markers)


def _question_requests_count(question: str) -> bool:
    question = _normalize_question(question)
    markers = ("כמה חשבוניות", "כמה קבלות", "כמה מסמכים", "מספר חשבוניות", "מספר קבלות")
    return any(marker in question for marker in markers)


def _question_requests_biggest_document(question: str) -> bool:
    question = _normalize_question(question)
    markers = ("הכי גבוהה", "הכי גדול", "הגדולה ביותר", "החשבון הכי", "החשבונית הכי")
    return any(marker in question for marker in markers)


def _question_requests_document_status(question: str) -> bool:
    question = _normalize_question(question)
    markers = (
        "פתוח",
        "פתוחה",
        "פתוחות",
        "סגור",
        "סגורה",
        "נסגר",
        "נסגרה",
        "טופל",
        "טופלה",
        "עדיין פתוח",
        "עדיין פתוחה",
    )
    return any(marker in question for marker in markers)


def _question_requests_receipt_linkage(question: str) -> bool:
    question = _normalize_question(question)
    markers = (
        "קבלה",
        "קבלות",
        "משויכת",
        "משויך",
        "שויכה",
        "שויך",
        "סגרה",
        "סגר",
        "לאיזה חשבונית",
        "לאיזו חשבונית",
    )
    return any(marker in question for marker in markers)


def _extract_document_number_from_question(question: str, ui_context: dict | None = None) -> str:
    raw = str(question or "").strip()
    matches = re.findall(r"\b(\d{5,10})\b", raw)
    if matches:
        return matches[0]
    normalized = _normalize_question(raw)
    if any(token in normalized for token in ("החשבונית הזאת", "החשבונית הזו", "המסמך הזה", "המסמך הזאת", "הקבלה הזאת", "הקבלה הזו")):
        contextual_number = str((ui_context or {}).get("current_document_number") or "").strip()
        if contextual_number:
            return contextual_number
    return ""


def _serialize_raw_document(doc: dict) -> str:
    raw = doc.get("raw")
    if not raw:
        return ""
    try:
        return json.dumps(raw, ensure_ascii=False)
    except Exception:
        return str(raw)


def _find_documents_by_number(documents: list[dict], document_number: str) -> list[dict]:
    wanted = str(document_number or "").strip()
    if not wanted:
        return []
    return [
        doc for doc in documents
        if str(doc.get("number") or "").strip() == wanted
    ]


def _find_receipts_linked_to_invoice(documents: list[dict], invoice_number: str) -> list[dict]:
    wanted = str(invoice_number or "").strip()
    if not wanted:
        return []
    matches: list[dict] = []
    for doc in _receipt_documents(documents):
        references = set(_extract_receipt_invoice_numbers(_serialize_raw_document(doc)))
        if wanted in references:
            matches.append(doc)
    return matches


def _document_brief(doc: dict) -> str:
    doc_type = str(doc.get("type") or "מסמך").strip()
    number = str(doc.get("number") or "ללא מספר").strip()
    customer_name = str(doc.get("customer_name") or "ללא לקוח").strip()
    doc_date = _parse_iso_date(str(doc.get("date") or ""))
    date_text = doc_date.strftime("%d/%m/%Y") if doc_date else str(doc.get("date") or "ללא תאריך")
    amount = _document_amount(doc)
    return f"{doc_type} {number} של {customer_name} מתאריך {date_text} בסך {_format_currency(amount)}"


def _document_payload_for_ui(doc: dict, *, role: str = "document") -> dict:
    return {
        "role": role,
        "id": str(doc.get("id") or "").strip(),
        "number": str(doc.get("number") or "").strip(),
        "type": str(doc.get("type") or "").strip(),
        "customer_name": str(doc.get("customer_name") or "").strip(),
        "date": str(doc.get("date") or "").strip(),
        "amount": _document_amount(doc),
        "source_url": str(doc.get("source_url") or "").strip(),
    }


def _normalize_assistant_ui_context(ui_context: dict | None) -> dict:
    if not isinstance(ui_context, dict):
        return {}
    normalized: dict[str, object] = {}
    for key in (
        "current_document_number",
        "current_customer_name",
        "active_tab",
        "mode_label",
    ):
        value = str(ui_context.get(key) or "").strip()
        if value:
            normalized[key] = value
    invoice_numbers = ui_context.get("loaded_open_invoice_numbers")
    if isinstance(invoice_numbers, list):
        normalized["loaded_open_invoice_numbers"] = [
            str(item or "").strip()
            for item in invoice_numbers
            if str(item or "").strip()
        ][:20]
    loaded_count = ui_context.get("loaded_open_invoices_count")
    try:
        if loaded_count is not None and str(loaded_count).strip():
            normalized["loaded_open_invoices_count"] = int(loaded_count)
    except Exception:
        pass
    return normalized


async def _build_specific_document_result(
    question: str,
    documents: list[dict],
    today: date,
    client: GreenInvoiceClient,
    ui_context: dict | None = None,
) -> dict | None:
    document_number = _extract_document_number_from_question(question, ui_context)
    if not document_number:
        return None

    matched_documents = _find_documents_by_number(documents, document_number)
    needs_open_status = _question_requests_document_status(question) or _question_requests_receipt_linkage(question)
    open_match = None

    if needs_open_status:
        try:
            open_invoices = await client.get_open_invoices_due_between(
                due_from=None,
                due_to=(today + timedelta(days=3650)).isoformat(),
                page_size=int(settings.greeninvoice_assistant_page_size or 100),
                max_pages=max(int(settings.greeninvoice_assistant_max_pages or 12), 18),
                search_months_back=max(int(settings.greeninvoice_assistant_months_back or 36), 60),
            )
            open_match = next(
                (doc for doc in open_invoices if str(doc.get("number") or "").strip() == document_number),
                None,
            )
        except Exception:
            open_match = None

    linked_receipts = _find_receipts_linked_to_invoice(documents, document_number)

    if not matched_documents and not open_match and not linked_receipts:
        return {
            "answer": f"לא מצאתי כרגע מסמך מספר {document_number} בטווח הנתונים שנבדק.",
            "summary": f"לא נמצא מסמך {document_number}",
            "findings": [f"לא זוהה מסמך מספר {document_number} בין מסמכי ההכנסה שנטענו."],
            "suggestions": [
                "בדוק שהמספר הוקלד נכון.",
                "אם זה מסמך ישן מאוד, ייתכן שהוא מחוץ לטווח הנתונים שהעוזר טוען כרגע.",
            ],
            "matched_documents": [],
        }

    findings: list[str] = []
    suggestions: list[str] = []
    ui_documents: list[dict] = []

    if matched_documents:
        for doc in matched_documents:
            findings.append(f"מצאתי {_document_brief(doc)}.")
            ui_documents.append(_document_payload_for_ui(doc))

    if open_match:
        findings.append(
            f"המסמך {document_number} עדיין מופיע כרגע כחשבונית פתוחה בסך {_format_currency(float(open_match.get('amount_open') or 0))}."
        )
        suggestions.append("אם כבר הופקה קבלה אבל המסמך עדיין פתוח, כדאי לבדוק אם הקבלה באמת שויכה לחשבונית הנכונה.")
        ui_documents.append(
            {
                **_document_payload_for_ui(open_match, role="open_invoice"),
                "amount_open": round(float(open_match.get("amount_open") or 0), 2),
                "due_date": str(open_match.get("due_date") or "").strip(),
            }
        )
    elif needs_open_status:
        findings.append(f"המסמך {document_number} לא מופיע כרגע ברשימת החשבוניות הפתוחות.")
        suggestions.append("אם זו חשבונית מס, זה בדרך כלל אומר שהיא כבר נסגרה או לא פתוחה כרגע במערכת.")

    if linked_receipts:
        receipt_numbers = ", ".join(str(doc.get("number") or "").strip() for doc in linked_receipts if str(doc.get("number") or "").strip())
        findings.append(f"מצאתי קבלות שמשויכות לחשבונית {document_number}: {receipt_numbers}.")
        for doc in linked_receipts:
            ui_documents.append(_document_payload_for_ui(doc, role="receipt"))
    elif _question_requests_receipt_linkage(question):
        findings.append(f"לא מצאתי בנתונים שנמשכו קבלה שקושרת במפורש לחשבונית {document_number}.")
        suggestions.append("אם ציפית לראות קבלה משויכת, אפשר לבדוק את מסמך הקבלה עצמו ואת סטטוס החשבונית ב־GreenInvoice.")

    summary = f"בדקתי את מסמך {document_number}."
    if open_match:
        summary = f"בדקתי את מסמך {document_number} והוא עדיין פתוח."
    elif linked_receipts:
        summary = f"בדקתי את מסמך {document_number} ומצאתי לו קבלות משויכות."

    answer_lines = [summary, *findings]
    if suggestions:
        answer_lines.append("פעולה מומלצת: " + suggestions[0])

    deduped_ui_documents: list[dict] = []
    seen_ui_keys: set[str] = set()
    for item in ui_documents:
        key = f"{item.get('role')}::{item.get('id')}::{item.get('number')}::{item.get('date')}"
        if key in seen_ui_keys:
            continue
        seen_ui_keys.add(key)
        deduped_ui_documents.append(item)

    return {
        "answer": "\n".join(answer_lines),
        "summary": summary,
        "findings": findings,
        "suggestions": suggestions,
        "matched_documents": deduped_ui_documents,
        "intent": "specific_document",
    }


def _mentions_current_year(question: str) -> bool:
    normalized = _normalize_question(question)
    return any(marker in normalized for marker in ("השנה", "השנה הזו", "השנה הזאת", "השנה הנוכחית"))


def _question_requests_single_period_total(question: str) -> bool:
    question = (question or "").strip()
    markers = (
        "בכמה כסף",
        "כמה כסף",
        "מה מכרתי",
        "כמה מכרתי",
        "סך המכירות",
        "סך ההכנסות",
        "מה ההכנסה",
        "מה היו ההכנסות",
        "כמה הכנסות",
    )
    return any(marker in question for marker in markers)


def _question_requests_customer_paid_total(question: str) -> bool:
    question = (question or "").strip()
    payment_markers = (
        "שילם",
        "שילמו",
        "שולם",
        "שולמו",
        "גבינו",
        "גבו",
        "התקבל",
        "התקבלו",
        "קבלה",
        "קבלות",
        "תקבול",
        "תקבולים",
    )
    amount_markers = (
        "כמה כסף",
        "כמה",
        "סך",
        "סהכ",
        'סה"כ',
        "בסך",
    )
    return any(marker in question for marker in payment_markers) and any(marker in question for marker in amount_markers)


def _receipt_documents(documents: list[dict]) -> list[dict]:
    receipts = []
    for doc in documents:
        type_code = str(doc.get("type_code") or "").strip()
        type_text = str(doc.get("type") or "").strip().lower()
        if type_code == "400" or "קבלה" in type_text or "receipt" in type_text:
            receipts.append(doc)
    return receipts


def _extract_customer_from_question(question: str, customer_names: list[str]) -> str | None:
    canonical_question = _canonical_income_customer_name(question or "")
    if not canonical_question:
        return None

    stopwords = {
        "כמה",
        "כסף",
        "שילם",
        "שילמו",
        "שולם",
        "שולמו",
        "לנו",
        "עד",
        "היום",
        "עדהיום",
        "סהכ",
        "בסך",
        "של",
        "מה",
        "הלקוח",
        "לקוח",
        "תקבולים",
        "תקבול",
        "קבלה",
        "קבלות",
    }

    best_name = None
    best_score = 0
    for original_name in customer_names:
        canonical_name = _canonical_income_customer_name(original_name)
        if not canonical_name:
            continue

        score = 0
        if canonical_name in canonical_question:
            score += 100

        tokens = [
            token for token in re.split(r"[\s\\/\-]+", canonical_name)
            if len(token) >= 2 and token not in stopwords
        ]
        matched_tokens = 0
        for token in tokens:
            if token in canonical_question:
                matched_tokens += 1
                score += min(len(token), 12)

        if matched_tokens and tokens:
            score += matched_tokens * 5
            if matched_tokens == len(tokens):
                score += 20

        if score > best_score:
            best_score = score
            best_name = original_name

    return best_name if best_score >= 4 else None


def _build_customer_paid_total_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_customer_paid_total(question):
        return None

    receipts = _receipt_documents(documents)
    if not receipts:
        return "לא מצאתי קבלות בטווח הנתונים שנבדק, ולכן אין לי כרגע בסיס לחשב כמה שולם בפועל."

    customer_names = sorted({
        _normalize_income_customer_name(doc.get("customer_name") or "")
        for doc in receipts
        if _normalize_income_customer_name(doc.get("customer_name") or "")
    })
    matched_customer = _extract_customer_from_question(question, customer_names)
    if not matched_customer:
        return None

    matched_customer_canonical = _canonical_income_customer_name(matched_customer)
    relevant_receipts = [
        doc for doc in receipts
        if _canonical_income_customer_name(doc.get("customer_name") or "") == matched_customer_canonical
    ]

    if "עד היום" in question or "עד כה" in question:
        relevant_receipts = [
            doc for doc in relevant_receipts
            if (_parse_iso_date(str(doc.get("date") or "")) or today) <= today
        ]

    total = round(sum(float(doc.get("amount") or 0) for doc in relevant_receipts), 2)
    count = len(relevant_receipts)
    if not count:
        return f"לא מצאתי קבלות של {matched_customer} בטווח הנתונים שנבדק."

    latest_payment_date = max(
        (_parse_iso_date(str(doc.get("date") or "")) for doc in relevant_receipts),
        default=None,
    )
    latest_suffix = f" הקבלה האחרונה שזוהתה היא מ-{latest_payment_date.strftime('%d/%m/%Y')}." if latest_payment_date else ""
    return (
        f"עד היום {matched_customer} שילמו לנו בסך הכול {_format_currency(total)} "
        f"על פני {count} קבלות.{latest_suffix}"
    )


def _build_customer_sales_total_answer(question: str, documents: list[dict], today: date) -> str | None:
    normalized = _normalize_question(question)
    if "תקבול" in normalized:
        return None
    if _question_requests_period_comparison(question):
        return None
    if not any(marker in normalized for marker in ("הכנסות", "חשבוניות", "בכמה כסף", "כמה כסף", "סך")):
        return None

    documents = _income_documents_for_aggregation(documents)
    customer_names = sorted({
        _normalize_income_customer_name(doc.get("customer_name") or "")
        for doc in documents
        if _normalize_income_customer_name(doc.get("customer_name") or "")
    })
    matched_customer = _extract_customer_from_question(question, customer_names)
    if not matched_customer:
        return None

    scoped_docs = _documents_for_customer(documents, matched_customer)
    period = _extract_period(question, today)
    if period:
        start_date, end_date = period
        available_start, available_end = _documents_coverage(scoped_docs)
        coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
        if coverage_issue:
            return coverage_issue
        scoped_docs = _documents_between(scoped_docs, start_date, end_date)

    total = round(sum(_document_amount(doc) for doc in scoped_docs), 2)
    count = len(scoped_docs)
    if not count:
        return f"לא מצאתי חשבוניות של {matched_customer} בטווח שביקשת."

    if period:
        start_date, end_date = period
        period_label = f"בתקופה {start_date.strftime('%d/%m/%Y')} עד {end_date.strftime('%d/%m/%Y')}"
    else:
        period_label = "עד היום"
    return f"{period_label} סך החשבוניות של {matched_customer} הוא {_format_currency(total)} על פני {count} מסמכים."


def _build_count_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_count(question):
        return None

    normalized = _normalize_question(question)
    target_docs = _receipt_documents(documents) if "קבלות" in normalized or "קבלה" in normalized else documents
    label = "קבלות" if target_docs is not documents else "חשבוניות"

    customer_names = sorted({
        _normalize_income_customer_name(doc.get("customer_name") or "")
        for doc in target_docs
        if _normalize_income_customer_name(doc.get("customer_name") or "")
    })
    matched_customer = _extract_customer_from_question(question, customer_names)
    if matched_customer:
        target_docs = _documents_for_customer(target_docs, matched_customer)

    period = _extract_period(question, today)
    if period:
        start_date, end_date = period
        available_start, available_end = _documents_coverage(target_docs)
        coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
        if coverage_issue:
            return coverage_issue
        target_docs = _documents_between(target_docs, start_date, end_date)

    count = len(target_docs)
    if matched_customer:
        return f"מצאתי {count} {label} עבור {matched_customer}."
    return f"מצאתי {count} {label} בטווח שביקשת."


def _build_average_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_average(question):
        return None

    normalized = _normalize_question(question)
    target_docs = _receipt_documents(documents) if "תקבול" in normalized or "קבלה" in normalized else documents
    metric_label = "קבלה" if target_docs is not documents else "חשבונית"

    customer_names = sorted({
        _normalize_income_customer_name(doc.get("customer_name") or "")
        for doc in target_docs
        if _normalize_income_customer_name(doc.get("customer_name") or "")
    })
    matched_customer = _extract_customer_from_question(question, customer_names)
    if matched_customer:
        target_docs = _documents_for_customer(target_docs, matched_customer)

    period = _extract_period(question, today)
    if period:
        start_date, end_date = period
        available_start, available_end = _documents_coverage(target_docs)
        coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
        if coverage_issue:
            return coverage_issue
        target_docs = _documents_between(target_docs, start_date, end_date)

    if not target_docs:
        return "לא מצאתי מסמכים מתאימים כדי לחשב ממוצע."

    avg = round(sum(_document_amount(doc) for doc in target_docs) / len(target_docs), 2)
    if matched_customer:
        return f"הממוצע למסמך עבור {matched_customer} הוא {_format_currency(avg)} לכל {metric_label}."
    return f"הממוצע למסמך בטווח שביקשת הוא {_format_currency(avg)} לכל {metric_label}."


def _build_top_customer_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_top_customer(question):
        return None

    target_docs = _income_documents_for_aggregation(documents)
    period = _extract_period(question, today)
    if period:
        start_date, end_date = period
        available_start, available_end = _documents_coverage(target_docs)
        coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
        if coverage_issue:
            return coverage_issue
        target_docs = _documents_between(target_docs, start_date, end_date)

    if not target_docs:
        return "לא מצאתי מסמכים מתאימים כדי לזהות לקוח מוביל."

    totals = defaultdict(float)
    counts = defaultdict(int)
    for doc in target_docs:
        name = _normalize_income_customer_name(doc.get("customer_name") or "")
        if not name:
            continue
        totals[name] += _document_amount(doc)
        counts[name] += 1

    if not totals:
        return "לא מצאתי לקוחות עם נתונים מספיקים כדי לזהות מוביל."

    best_name, best_total = max(totals.items(), key=lambda item: item[1])
    return f"הלקוח המוביל בטווח שביקשת הוא {best_name} עם {_format_currency(round(best_total, 2))} על פני {counts[best_name]} מסמכים."


def _build_top_month_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_top_month(question):
        return None

    period = _extract_period(question, today)
    target_docs = _income_documents_for_aggregation(documents)
    target_year = _extract_target_year(question, today) or today.year
    if not period:
        period = (date(target_year, 1, 1), date(target_year, 12, 31))
    start_date, end_date = period
    available_start, available_end = _documents_coverage(target_docs)
    coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
    if coverage_issue:
        return coverage_issue
    target_docs = _documents_between(target_docs, start_date, end_date)

    if not target_docs:
        return "לא מצאתי נתונים לחישוב החודש המוביל."

    monthly = defaultdict(float)
    for doc in target_docs:
        doc_date = str(doc.get("date") or "")
        if len(doc_date) >= 7:
            monthly[doc_date[:7]] += _document_amount(doc)
    if not monthly:
        return "לא הצלחתי לבנות סיכום חודשי מהנתונים."

    best_month, best_total = max(monthly.items(), key=lambda item: item[1])
    year, month = best_month.split("-")
    return f"החודש החזק ביותר הוא {NUMBER_TO_MONTH_NAME.get(int(month), month)} {year} עם {_format_currency(round(best_total, 2))}."


def _build_biggest_document_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_biggest_document(question):
        return None

    normalized = _normalize_question(question)
    target_docs = _receipt_documents(documents) if "תקבול" in normalized or "קבלה" in normalized else _income_documents_for_aggregation(documents)
    period = _extract_period(question, today)
    if period:
        start_date, end_date = period
        available_start, available_end = _documents_coverage(target_docs)
        coverage_issue = _coverage_message(start_date, end_date, available_start, available_end)
        if coverage_issue:
            return coverage_issue
        target_docs = _documents_between(target_docs, start_date, end_date)

    customer_names = sorted({
        _normalize_income_customer_name(doc.get("customer_name") or "")
        for doc in target_docs
        if _normalize_income_customer_name(doc.get("customer_name") or "")
    })
    matched_customer = _extract_customer_from_question(question, customer_names)
    if matched_customer:
        target_docs = _documents_for_customer(target_docs, matched_customer)

    if not target_docs:
        return "לא מצאתי מסמכים מתאימים כדי לזהות את המסמך הגבוה ביותר."

    best_doc = max(target_docs, key=_document_amount)
    label = "קבלה" if target_docs is not documents and (str(best_doc.get("type_code") or "") == "400" or "קבלה" in str(best_doc.get("type") or "")) else "חשבונית"
    customer_name = _normalize_income_customer_name(best_doc.get("customer_name") or "ללא שם")
    doc_number = str(best_doc.get("number") or "ללא מספר")
    doc_date = _parse_iso_date(str(best_doc.get("date") or ""))
    date_text = doc_date.strftime("%d/%m/%Y") if doc_date else str(best_doc.get("date") or "ללא תאריך")
    return f"{label.capitalize()} מספר {doc_number} של {customer_name} מ-{date_text} היא הגבוהה ביותר עם {_format_currency(_document_amount(best_doc))}."


def _build_single_period_total_answer(question: str, documents: list[dict], today: date) -> str | None:
    if _question_requests_period_comparison(question) or _question_requests_customer_list(question):
        return None
    if not _question_requests_single_period_total(question):
        return None

    documents = _income_documents_for_aggregation(documents)
    months = _extract_month_mentions(question)
    if not months:
        return None

    target_month = months[0]
    target_year = _extract_explicit_year(question) or today.year
    use_to_date = ("עד כה" in question or "עד היום" in question) and target_month == today.month and target_year == today.year
    end_day = today.day if use_to_date else monthrange(target_year, target_month)[1]
    period_start = date(target_year, target_month, 1)
    period_end = date(target_year, target_month, end_day)

    available_start, available_end = _documents_coverage(documents)
    coverage_issue = _coverage_message(period_start, period_end, available_start, available_end)
    if coverage_issue:
        return coverage_issue

    period_docs = _documents_between(documents, period_start, period_end)
    total = round(sum(float(doc.get("amount") or 0) for doc in period_docs), 2)
    docs_count = len(period_docs)

    if not period_docs:
        return (
            f"לא מצאתי מסמכי הכנסה ב-{NUMBER_TO_MONTH_NAME[target_month]} {target_year}"
            + (" עד כה." if use_to_date else ".")
        )

    return (
        f"ב-{NUMBER_TO_MONTH_NAME[target_month]} {target_year}"
        + (" עד כה" if use_to_date else "")
        + f" סך ההכנסות הוא {_format_currency(total)} על פני {docs_count} מסמכים."
    )


def _build_multi_year_same_period_totals_answer(question: str, documents: list[dict], today: date) -> str | None:
    normalized = _normalize_question(question)
    if "תקבול" in normalized:
        return None
    if not _question_requests_single_period_total(question):
        return None

    documents = _income_documents_for_aggregation(documents)
    months = _extract_month_mentions(question)
    years = _extract_explicit_years(question)
    if not months or len(years) < 2:
        return None

    start_month = months[0]
    end_month = months[-1]
    use_to_date = ("עד כה" in normalized or "עד היום" in normalized) and end_month == today.month

    period_specs: list[tuple[int, date, date]] = []
    for year in years:
        end_day = today.day if use_to_date and year == today.year else monthrange(year, end_month)[1]
        period_specs.append((year, date(year, start_month, 1), date(year, end_month, end_day)))

    available_start, available_end = _documents_coverage(documents)
    min_start = min(start for _, start, _ in period_specs)
    max_end = max(end for _, _, end in period_specs)
    coverage_issue = _coverage_message(min_start, max_end, available_start, available_end)
    if coverage_issue:
        return coverage_issue

    month_label = (
        f"{NUMBER_TO_MONTH_NAME[start_month]} {years[0]}"
        if start_month == end_month
        else f"{NUMBER_TO_MONTH_NAME[start_month]}–{NUMBER_TO_MONTH_NAME[end_month]}"
    )
    lines: list[str] = []
    for year, period_start, period_end in period_specs:
        total = _sum_documents_between(documents, period_start, period_end)
        docs_count = _documents_count_between(documents, period_start, period_end)
        label = (
            f"{NUMBER_TO_MONTH_NAME[start_month]} {year}"
            if start_month == end_month
            else f"{NUMBER_TO_MONTH_NAME[start_month]}–{NUMBER_TO_MONTH_NAME[end_month]} {year}"
        )
        if use_to_date and year == today.year and end_month == today.month:
            label += " עד כה"
        lines.append(f"ב-{label} סך ההכנסות הוא {_format_currency(total)} על פני {docs_count} מסמכים.")

    if len(period_specs) == 2:
        first_year, first_start, first_end = period_specs[0]
        second_year, second_start, second_end = period_specs[1]
        first_total = _sum_documents_between(documents, first_start, first_end)
        second_total = _sum_documents_between(documents, second_start, second_end)
        delta = round(second_total - first_total, 2)
        if first_total:
            percent_change = ((second_total - first_total) / first_total) * 100
            direction = "עלייה" if percent_change >= 0 else "ירידה"
            lines.append(
                f"מ-{first_year} ל-{second_year} יש {direction} של {_format_percent(abs(percent_change))} "
                f"({_format_currency(abs(delta))})."
            )
        elif second_total:
            lines.append(f"ב-{first_year} לא נמצאו הכנסות בטווח הזה, וב-{second_year} הסכום הוא {_format_currency(second_total)}.")

    return "\n".join(lines)


def _build_customer_list_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_customer_list(question):
        return None

    months = _extract_month_mentions(question)
    if not months:
        return None

    target_month = months[0]
    target_year = _extract_explicit_year(question) or today.year

    end_day = today.day if ("עד כה" in question or "עד היום" in question) and target_month == today.month and target_year == today.year else monthrange(target_year, target_month)[1]
    period_start = date(target_year, target_month, 1)
    period_end = date(target_year, target_month, end_day)
    available_start, available_end = _documents_coverage(documents)
    coverage_issue = _coverage_message(period_start, period_end, available_start, available_end)
    if coverage_issue:
        return coverage_issue
    period_docs = _documents_between(documents, period_start, period_end)

    customer_names = sorted({
        str(doc.get("customer_name") or "").strip()
        for doc in period_docs
        if str(doc.get("customer_name") or "").strip()
    })

    if not customer_names:
        return (
            f"לא מצאתי לקוחות עם חשבוניות ב-{NUMBER_TO_MONTH_NAME[target_month]} {target_year}"
            + (" עד כה." if end_day != monthrange(target_year, target_month)[1] else ".")
        )

    lines = [
        f"אלה הלקוחות השונים שהוצאו להם חשבוניות ב-{NUMBER_TO_MONTH_NAME[target_month]} {target_year}"
        + (" עד כה:" if end_day != monthrange(target_year, target_month)[1] else ":")
    ]
    lines.extend(f"{index}. {name}" for index, name in enumerate(customer_names, start=1))
    lines.append(f"סה״כ {len(customer_names)} לקוחות שונים.")
    return "\n".join(lines)


def _build_period_comparison_answer(question: str, documents: list[dict], today: date) -> str | None:
    if not _question_requests_period_comparison(question):
        return None

    normalized = _normalize_question(question)
    documents = _income_documents_for_aggregation(documents)
    months = _extract_month_mentions(question)
    if not months:
        return None

    start_month = months[0]
    end_month = months[-1]

    explicit_year = _extract_explicit_year(question)
    mentions_current_year = _mentions_current_year(question)

    if explicit_year and mentions_current_year:
        current_year = today.year
        current_end_day = today.day if end_month == today.month and current_year == today.year else monthrange(current_year, end_month)[1]
        requested_end_day = monthrange(explicit_year, end_month)[1]

        explicit_start = date(explicit_year, start_month, 1)
        explicit_end = date(explicit_year, end_month, requested_end_day)
        current_start = date(current_year, start_month, 1)
        current_end = date(current_year, end_month, current_end_day)

        available_start, available_end = _documents_coverage(documents)
        if available_end and explicit_end > available_end and explicit_year == available_end.year and end_month == available_end.month:
            explicit_end = available_end
        if available_end and current_end > available_end and current_year == available_end.year and end_month == available_end.month:
            current_end = available_end

        coverage_issue = _coverage_message(min(explicit_start, current_start), max(explicit_end, current_end), available_start, available_end)
        if coverage_issue:
            return coverage_issue

        explicit_total = _sum_documents_between(documents, explicit_start, explicit_end)
        current_total = _sum_documents_between(documents, current_start, current_end)
        explicit_count = _documents_count_between(documents, explicit_start, explicit_end)
        current_count = _documents_count_between(documents, current_start, current_end)

        if explicit_start == current_start and explicit_end == current_end:
            return (
                f"נכון להיום, {today.strftime('%d/%m/%Y')}, שני הניסוחים בשאלה מתייחסים לאותו טווח בדיוק: "
                f"{explicit_start.strftime('%d/%m/%Y')} עד {explicit_end.strftime('%d/%m/%Y')}. "
                f"סך חשבוניות המס בטווח הזה הוא {_format_currency(current_total)} על פני {current_count} מסמכים, "
                f"לכן היחס הוא 1.00x והמגמה היא 0.00%."
            )

        if explicit_total == 0 and current_total == 0:
            return (
                f"לא נמצאו מסמכים מתאימים בטווח {NUMBER_TO_MONTH_NAME[start_month]}–{NUMBER_TO_MONTH_NAME[end_month]} "
                f"ב-{explicit_year} ובאותה תקופה השנה."
            )

        if explicit_total == 0:
            ratio_text = "לא ניתן לחשב יחס כי הסכום בתקופה המפורשת הוא 0."
            percent_text = "אין אחוז שינוי מחושב כי הסכום בתקופה המפורשת הוא 0."
        else:
            ratio_value = current_total / explicit_total
            percent_change = ((current_total - explicit_total) / explicit_total) * 100
            direction = "עלייה" if percent_change >= 0 else "ירידה"
            ratio_text = f"היחס בין התקופות הוא {ratio_value:.2f}x."
            percent_text = f"{direction} של {_format_percent(abs(percent_change))}."

        return "\n".join(
            [
                f"בתקופה {explicit_start.strftime('%d/%m/%Y')} עד {explicit_end.strftime('%d/%m/%Y')} "
                f"הסכום הכולל הוא {_format_currency(explicit_total)} על פני {explicit_count} מסמכים.",
                f"בתקופה {current_start.strftime('%d/%m/%Y')} עד {current_end.strftime('%d/%m/%Y')} "
                f"(עד היום) הסכום הכולל הוא {_format_currency(current_total)} על פני {current_count} מסמכים.",
                ratio_text,
                percent_text,
            ]
        )

    this_year = today.year
    last_year = explicit_year if explicit_year and explicit_year != this_year and mentions_current_year else today.year - 1

    use_to_date = (
        "עד כה" in normalized
        or "עד היום" in normalized
        or (this_year == today.year and end_month == today.month)
    )
    current_end_day = today.day if use_to_date and end_month == today.month else monthrange(this_year, end_month)[1]
    previous_end_day = min(current_end_day, monthrange(last_year, end_month)[1])

    current_start = date(this_year, start_month, 1)
    current_end = date(this_year, end_month, current_end_day)
    previous_start = date(last_year, start_month, 1)
    previous_end = date(last_year, end_month, previous_end_day)

    available_start, available_end = _documents_coverage(documents)

    if (
        available_end
        and current_end > available_end
        and current_end.year == available_end.year
        and current_end.month == available_end.month
    ):
        current_end = available_end
        previous_end = date(last_year, end_month, min(available_end.day, monthrange(last_year, end_month)[1]))

    coverage_issue = _coverage_message(previous_start, current_end, available_start, available_end)
    if coverage_issue:
        return coverage_issue

    current_total = _sum_documents_between(documents, current_start, current_end)
    previous_total = _sum_documents_between(documents, previous_start, previous_end)
    current_count = _documents_count_between(documents, current_start, current_end)
    previous_count = _documents_count_between(documents, previous_start, previous_end)

    if previous_total == 0 and current_total == 0:
        return (
            f"לא נמצאו מסמכים מתאימים בטווח {NUMBER_TO_MONTH_NAME[start_month]}–{NUMBER_TO_MONTH_NAME[end_month]} "
            f"לשנה הנוכחית או לאותה תקופה אשתקד."
        )

    if previous_total == 0:
        percent_change = None
        ratio_text = "לא ניתן לחשב יחס כי בתקופה המקבילה אשתקד הסכום הוא 0."
    else:
        percent_change = ((current_total - previous_total) / previous_total) * 100
        ratio_value = current_total / previous_total
        ratio_text = f"היחס בין התקופות הוא {ratio_value:.2f}x."

    direction = "עלייה" if (percent_change or 0) >= 0 else "ירידה"
    percent_text = (
        f"{direction} של {_format_percent(abs(percent_change))}."
        if percent_change is not None
        else "אין אחוז שינוי מחושב כי התקופה המקבילה אשתקד היא 0."
    )

    lines = [
        f"בתקופה {NUMBER_TO_MONTH_NAME[start_month]}–{NUMBER_TO_MONTH_NAME[end_month]} {this_year}"
        + (" (עד כה)" if use_to_date else "")
        + f" הסכום הכולל הוא {_format_currency(current_total)} על פני {current_count} מסמכים.",
        f"בתקופה המקבילה בשנת {last_year} הסכום הכולל הוא {_format_currency(previous_total)} על פני {previous_count} מסמכים.",
        ratio_text,
        percent_text,
    ]
    return "\n".join(lines)


async def _ask_openai(question: str, mode: str, context: dict) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("חסר OPENAI_API_KEY ולכן אי אפשר להפעיל את עוזר השאלות.")

    developer_prompt = (
        "אתה עוזר BI פיננסי לעסק ישראלי. "
        "ענה בעברית בלבד, קצר וברור, על בסיס הנתונים שנמסרו לך בלבד. "
        "אם חסר מידע כדי לענות בוודאות, אמור זאת במפורש. "
        "כאשר נשאלים על יחס/אחוז/פער בין חודשים, חשב אותו על בסיס monthly_totals בלבד. "
        "אל תמציא מסמכים או מספרים שלא נמצאים בנתונים."
    )

    user_payload = {
        "question": question,
        "mode": mode,
        "today": date.today().isoformat(),
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
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]},
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

    raise RuntimeError("מודל ה־AI לא החזיר תשובה קריאה.")


def _fallback_answer(question: str, context: dict) -> str:
    monthly = context.get("monthly_totals") or []
    if not monthly:
        return "לא נמצאו נתוני הכנסה זמינים בטווח שנבדק, ולכן עדיין אין לי על מה לחשב תשובה."

    latest = monthly[-1]
    prev = monthly[-2] if len(monthly) > 1 else None

    lines = [
        "ה־AI לא הוגדר כרגע עם OPENAI_API_KEY, אז אני מחזיר סיכום בסיסי מהנתונים שנשלפו.",
        f"נבדקו {context.get('documents_count', 0)} מסמכי הכנסה.",
        f"סך ההכנסות בטווח שנבדק: ₪ {context.get('income_total', 0):,.2f}",
        f"החודש האחרון בנתונים: {latest.get('month')} עם ₪ {latest.get('income_total', 0):,.2f}.",
    ]
    if prev:
        lines.append(f"החודש שקדם לו: {prev.get('month')} עם ₪ {prev.get('income_total', 0):,.2f}.")
    lines.append(f"השאלה שנשאלה הייתה: {question}")
    return "\n".join(lines)


async def answer_greeninvoice_question(question: str, mode: str = "prod", ui_context: dict | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        raise RuntimeError("חסר טקסט שאלה.")
    ui_context = _normalize_assistant_ui_context(ui_context)

    months_back = max(int(settings.greeninvoice_assistant_months_back or 36), 1)
    start_date = _month_start_months_ago(months_back).isoformat()
    end_date = date.today().isoformat()

    client = _build_greeninvoice_client(mode)
    documents = await client.get_income_documents(
        date_from=start_date,
        date_to=end_date,
        page_size=int(settings.greeninvoice_assistant_page_size or 100),
        max_pages=int(settings.greeninvoice_assistant_max_pages or 12),
    )
    documents = _filter_documents_for_question(documents, question)

    context = _build_income_context(documents)

    if not documents:
        return {
            "answer": "לא הצלחתי למצוא מסמכי הכנסה בטווח שנבדק, אז כרגע אין לי בסיס לענות על השאלה הזו.",
            "summary": "לא נמצאו מסמכים רלוונטיים",
            "documents_count": 0,
            "start_date": start_date,
            "end_date": end_date,
            "context": context,
            "ui_context": ui_context,
        }

    today = date.today()
    specific_document_result = await _build_specific_document_result(question, documents, today, client, ui_context)
    if specific_document_result:
        answer = specific_document_result.get("answer") or ""
        summary = specific_document_result.get("summary") or ""
        findings = specific_document_result.get("findings") or []
        suggestions = specific_document_result.get("suggestions") or []
        matched_documents = specific_document_result.get("matched_documents") or []
        intent = specific_document_result.get("intent") or "specific_document"
    else:
        deterministic_answer = _build_customer_list_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_multi_year_same_period_totals_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_customer_paid_total_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_period_comparison_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_customer_sales_total_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_average_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_top_customer_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_top_month_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_biggest_document_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_single_period_total_answer(question, documents, today)
        if not deterministic_answer:
            deterministic_answer = _build_count_answer(question, documents, today)
        if deterministic_answer:
            answer = deterministic_answer
        else:
            try:
                context_for_ai = dict(context)
                if ui_context:
                    context_for_ai["ui_context"] = ui_context
                answer = await _ask_openai(question, mode, context_for_ai)
            except Exception:
                answer = _fallback_answer(question, context)
        summary = ""
        findings = []
        suggestions = []
        matched_documents = []
        intent = "general"

    return {
        "answer": answer,
        "summary": summary,
        "findings": findings,
        "suggestions": suggestions,
        "matched_documents": matched_documents,
        "intent": intent,
        "documents_count": len(documents),
        "start_date": start_date,
        "end_date": end_date,
        "context": context,
        "ui_context": ui_context,
    }
