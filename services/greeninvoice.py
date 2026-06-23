import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import httpx

from .config import settings
from .models import PurchaseOrderData
from .parsers.common import fix_hebrew_text


def _safe_folder_name(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r'[\\/:*?"<>|]+', "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120]


def _normalize_income_customer_name(value: str) -> str:
    raw = re.sub(r"\s+", " ", str(value or "").strip())
    if not raw:
        return ""
    fixed = re.sub(r"\s+", " ", fix_hebrew_text(raw).strip())
    hebrew_count = sum(1 for c in raw if "א" <= c <= "ת")
    if hebrew_count < 3 or not fixed or fixed == raw:
        return raw

    forward_tokens = (
        'בע"מ',
        'בע״מ',
        "בעמ",
        "חברה",
        "קיבוץ",
        "פרויקטים",
        "פרוייקטים",
        "בניה",
        "הנדסה",
        "סיבוס",
        "ייזום",
        "יזום",
    )
    reverse_tokens = (
        'מ"עב',
        'מ״עב',
        "מעב",
        "הרבח",
        "ץוביק",
        "םיטקיורפ",
        "הינב",
        "הסדנה",
        "סוביס",
        "םוזיי",
        "םוזי",
    )

    raw_score = sum(2 for token in forward_tokens if token in raw) + sum(-2 for token in reverse_tokens if token in raw)
    fixed_score = sum(2 for token in forward_tokens if token in fixed) + sum(-2 for token in reverse_tokens if token in fixed)

    if fixed_score > raw_score:
        return fixed
    return raw


def _normalize_income_customer_id(value: str) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _canonical_income_customer_name(value: str) -> str:
    normalized = _normalize_income_customer_name(value)
    normalized = normalized.replace("״", '"').replace("”", '"').replace("“", '"').replace("׳", "'")
    normalized = re.sub(r"[\"'`]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


# לקוחות בודדים שבהם תנאי האשראי בפועל חייבים לגבור על מה שמופיע בהזמנת הרכש
# וגם על ערך ריק/0 שחוזר לעתים מ־GreenInvoice.
PAYMENT_TERMS_OVERRIDES_BY_CUSTOMER_ID: dict[str, int] = {
    "513921668": 60,  # אקו סיטי
}

PAYMENT_TERMS_OVERRIDES_BY_CUSTOMER_NAME: dict[str, int] = {
    _canonical_income_customer_name("אקו סיטי"): 60,
    _canonical_income_customer_name('אקוסיטי אס אל הנדסה ובניה בע"מ'): 60,
}


def _normalize_greeninvoice_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not (raw.startswith("http://") or raw.startswith("https://")):
        return raw
    try:
        parsed = urlsplit(raw)
    except Exception:
        return raw
    host = (parsed.netloc or "").strip().lower()
    path = parsed.path or ""
    if host == "www.greeninvoice.co.il" and path.startswith("/api"):
        return urlunsplit((parsed.scheme or "https", "api.greeninvoice.co.il", path, parsed.query, parsed.fragment))
    return raw


def _extract_customer_id_from_payload(item: dict | None) -> str:
    source = item if isinstance(item, dict) else {}
    for key in ("taxId", "idNumber", "vatNumber", "companyNumber", "companyId"):
        value = _normalize_income_customer_id(source.get(key) or "")
        if value:
            return value
    return ""


def _payment_terms_override_for_customer(customer_id: str = "", customer_name: str = "") -> int | None:
    normalized_customer_id = _normalize_income_customer_id(customer_id)
    if normalized_customer_id:
        override_days = PAYMENT_TERMS_OVERRIDES_BY_CUSTOMER_ID.get(normalized_customer_id)
        if override_days is not None:
            return int(override_days)

    canonical_name = _canonical_income_customer_name(customer_name)
    if canonical_name:
        override_days = PAYMENT_TERMS_OVERRIDES_BY_CUSTOMER_NAME.get(canonical_name)
        if override_days is not None:
            return int(override_days)

    return None


def _merge_income_customer_entries(entries: list[dict]) -> list[dict]:
    by_tax: dict[str, dict] = {}
    by_name_only: dict[str, dict] = {}

    for entry in entries:
        customer_name = _normalize_income_customer_name(entry.get("customer_name") or "")
        customer_id = _normalize_income_customer_id(entry.get("customer_id") or "")
        canonical_name = _canonical_income_customer_name(customer_name)
        if not customer_name and not customer_id:
            continue

        target = None
        if customer_id and customer_id in by_tax:
            target = by_tax[customer_id]
        elif canonical_name and canonical_name in by_name_only:
            target = by_name_only[canonical_name]

        if not target:
            target = {
                "customer_key": f"tax:{customer_id}" if customer_id else f"name:{canonical_name}",
                "customer_id": customer_id,
                "customer_name": customer_name or "ללא שם",
                "documents_count": int(entry.get("documents_count") or 0),
                "total_amount": round(float(entry.get("total_amount") or 0), 2),
                "last_date": str(entry.get("last_date") or ""),
                "payment_terms_days": str(entry.get("payment_terms_days") or ""),
            }
        else:
            target["documents_count"] = int(target.get("documents_count") or 0) + int(entry.get("documents_count") or 0)
            target["total_amount"] = round(float(target.get("total_amount") or 0) + float(entry.get("total_amount") or 0), 2)
            incoming_last = str(entry.get("last_date") or "")
            if incoming_last and incoming_last > str(target.get("last_date") or ""):
                target["last_date"] = incoming_last
            if customer_id and not str(target.get("customer_id") or ""):
                target["customer_id"] = customer_id
                target["customer_key"] = f"tax:{customer_id}"
            if customer_name and (
                len(customer_name) > len(str(target.get("customer_name") or ""))
                or str(target.get("customer_name") or "") == "ללא שם"
            ):
                target["customer_name"] = customer_name
            if not str(target.get("payment_terms_days") or "").strip() and str(entry.get("payment_terms_days") or "").strip():
                target["payment_terms_days"] = str(entry.get("payment_terms_days") or "").strip()

        if customer_id:
            by_tax[customer_id] = target
        if canonical_name:
            by_name_only[canonical_name] = target

    merged = {id(entry): entry for entry in list(by_tax.values()) + list(by_name_only.values())}
    return sorted(
        merged.values(),
        key=lambda item: (str(item.get("customer_name") or ""), str(item.get("customer_id") or "")),
    )


def _extract_receipt_invoice_number(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    match = re.search(r"חשבונית\s*מס\s*([0-9A-Za-z\-/]+)", raw)
    if match:
        return match.group(1).strip()
    match = re.search(r"invoice\s*([0-9A-Za-z\-/]+)", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_receipt_invoice_numbers(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []

    found: list[str] = []
    patterns = (
        r"חשבונית\s*מס\s*([0-9A-Za-z\-/,\s]+)",
        r"invoice\s*([0-9A-Za-z\-/,\s]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, raw, re.IGNORECASE):
            chunk = str(match.group(1) or "").strip()
            for part in re.split(r"[,\s]+", chunk):
                candidate = str(part or "").strip()
                if not candidate:
                    continue
                if not re.fullmatch(r"[0-9A-Za-z\-/]+", candidate):
                    continue
                if candidate not in found:
                    found.append(candidate)

    single = _extract_receipt_invoice_number(raw)
    if single and single not in found:
        found.insert(0, single)
    return found


def _extract_po_number(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    patterns = (
        r"\bPO\s*[-/]?\s*(\d{5,})\b",
        r"הזמנת\s*רכש\s*[-:|]?\s*PO\s*[-/]?\s*(\d{5,})",
        r"הזמנת\s*רכש\s*[-:|]?\s*(\d{5,})",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            digits = re.sub(r"\D+", "", match.group(1) or "")
            if digits:
                return f"PO{digits}"
    return ""


class GreenInvoiceClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self._customer_cache = {}

    async def _get_token(self) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            payload_attempts = [
                {
                    "id": self.api_key,
                    "secret": self.api_secret,
                    "client_id": self.api_key,
                    "clientId": self.api_key,
                },
                {
                    "client_id": self.api_key,
                    "secret": self.api_secret,
                },
                {
                    "clientId": self.api_key,
                    "secret": self.api_secret,
                },
            ]
            last_error_text = ""
            last_status = 0
            for payload in payload_attempts:
                response = await client.post(
                    f"{self.base_url}/account/token",
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                if response.status_code < 400:
                    data = response.json()
                    token = data.get("token")
                    if not token:
                        raise RuntimeError(f"Missing token: {data}")
                    return token
                last_status = response.status_code
                last_error_text = response.text
            print("TOKEN STATUS:", last_status)
            print("TOKEN RESPONSE TEXT:", last_error_text)
            raise httpx.HTTPStatusError(
                "GreenInvoice token request failed",
                request=response.request,
                response=response,
            )

    def _auth_headers(self, token: str):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    async def _get_document_types(self, token: str):
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/documents/types",
                headers=self._auth_headers(token),
            )
            response.raise_for_status()
            return response.json()

    def _iter_dicts(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._iter_dicts(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_dicts(item)

    def _extract_type_value(self, d):
        for key in ("type", "id", "documentType"):
            val = d.get(key)
            if isinstance(val, int):
                return val
        return None

    async def _resolve_delivery_type(self, token: str) -> int:
        if settings.greeninvoice_delivery_doc_type:
            return int(settings.greeninvoice_delivery_doc_type)

        data = await self._get_document_types(token)

        candidates = []
        for d in self._iter_dicts(data):
            t = self._extract_type_value(d)
            if t is None:
                continue
            txt = json.dumps(d, ensure_ascii=False).lower()
            if ("תעודת משלוח" in txt) or ("delivery" in txt and "invoice" not in txt):
                candidates.append((t, txt))

        if not candidates:
            raise RuntimeError(f"לא נמצא סוג מסמך של תעודת משלוח. DOC TYPES={data}")

        return candidates[0][0]

    async def _find_customer_by_id(self, token: str, customer_id: str):
        customer_id = str(customer_id or "").strip()
        normalized_target = re.sub(r"\D", "", customer_id)
        if not normalized_target:
            return None

        if normalized_target in self._customer_cache:
            return self._customer_cache[normalized_target]

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while page <= 20:
                response = await client.post(
                    f"{self.base_url}/clients/search",
                    headers=self._auth_headers(token),
                    json={"search": customer_id, "page": page, "pageSize": 100},
                )

                if response.status_code >= 400:
                    return None

                data = response.json()
                items = data.get("items", []) if isinstance(data, dict) else []

                for item in items:
                    candidates = [
                        item.get("taxId"),
                        item.get("idNumber"),
                        item.get("vatNumber"),
                        item.get("companyNumber"),
                        item.get("companyId"),
                    ]
                    for cand in candidates:
                        if cand and re.sub(r"\D", "", str(cand)) == normalized_target:
                            self._customer_cache[normalized_target] = item
                            return item

                total_pages = 1
                if isinstance(data, dict):
                    total_pages = int(data.get("pages") or 1)

                if page >= total_pages:
                    break
                page += 1

        return None

    async def get_client_by_guid(self, client_guid: str, token: str | None = None):
        client_guid = str(client_guid or "").strip()
        if not client_guid:
            return None

        cache_key = f"guid:{client_guid}"
        if cache_key in self._customer_cache:
            return self._customer_cache[cache_key]

        auth_token = token or await self._get_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/clients/{client_guid}",
                headers=self._auth_headers(auth_token),
            )
            if response.status_code >= 400:
                return None
            data = response.json() if response.content else {}
            if isinstance(data, dict):
                self._customer_cache[cache_key] = data
                normalized_tax = _normalize_income_customer_id(
                    data.get("taxId")
                    or data.get("idNumber")
                    or data.get("vatNumber")
                    or data.get("companyNumber")
                    or data.get("companyId")
                    or ""
                )
                if normalized_tax:
                    self._customer_cache[normalized_tax] = data
                return data
        return None

    def _extract_payment_days_from_customer(self, customer_data) -> int | None:
        if not isinstance(customer_data, dict):
            return None

        candidates = []

        payment_terms = customer_data.get("paymentTerms")
        if isinstance(payment_terms, dict):
            for key in ("days", "value", "current", "net"):
                if payment_terms.get(key) not in (None, ""):
                    candidates.append(payment_terms.get(key))
        elif payment_terms not in (None, ""):
            candidates.append(payment_terms)

        for key in (
            "paymentTermsDays",
            "paymentDays",
            "payment_terms_days",
            "termsDays",
            "days",
        ):
            if customer_data.get(key) not in (None, ""):
                candidates.append(customer_data.get(key))

        for val in candidates:
            try:
                txt = str(val).strip()
                m = re.search(r"(\d+)", txt)
                if m:
                    return int(m.group(1))
            except Exception:
                pass

        return None

    def _resolve_payment_days_for_customer(
        self,
        customer_data: dict | None = None,
        customer_id: str = "",
        customer_name: str = "",
    ) -> int | None:
        source = customer_data if isinstance(customer_data, dict) else {}

        override_days = _payment_terms_override_for_customer(
            customer_id=customer_id or _extract_customer_id_from_payload(source),
            customer_name=customer_name or str(source.get("name") or ""),
        )
        if override_days is not None:
            return override_days

        return self._extract_payment_days_from_customer(source)


    def _merge_customer_data_into_po(self, po: PurchaseOrderData, customer_data: dict):
        if not isinstance(customer_data, dict):
            return po

        # שם
        if customer_data.get("name"):
            po.customer_name = customer_data.get("name")

        # ח.פ / ע.מ
        for key in ("taxId", "idNumber", "vatNumber", "companyNumber", "companyId"):
            if customer_data.get(key):
                po.customer_id = str(customer_data.get(key))
                break

        # מייל
        if not po.customer_email:
            emails = customer_data.get("emails") or []
            if isinstance(emails, list) and emails:
                if isinstance(emails[0], dict):
                    po.customer_email = emails[0].get("email") or ""
                else:
                    po.customer_email = str(emails[0])

        # איש קשר
        extra = po.extra or {}
        if not extra.get("contact_name") and customer_data.get("contactPerson"):
            extra["contact_name"] = str(customer_data.get("contactPerson"))

        # כתובת
        address_parts = []
        if customer_data.get("address"):
            address_parts.append(str(customer_data.get("address")))
        if customer_data.get("city"):
            address_parts.append(str(customer_data.get("city")))
        if customer_data.get("zip"):
            address_parts.append(str(customer_data.get("zip")))

        if not po.delivery_address and address_parts:
            po.delivery_address = " / ".join([x for x in address_parts if x])

        # ימי אשראי
        days = self._resolve_payment_days_for_customer(
            customer_data=customer_data,
            customer_id=po.customer_id or "",
            customer_name=po.customer_name or "",
        )
        if days is not None:
            po.payment_terms_days = days
            po.payment_terms_label = f"שוטף + {days}"

        po.extra = extra
        return po


    async def get_existing_customer_details(self, customer_id: str):
        token = await self._get_token()
        customer_data = await self._find_customer_by_id(token, customer_id)
        if not customer_data:
            return None
        return customer_data

    async def _find_customer_by_name(self, token: str, customer_name: str):
        matches = await self._find_customers_by_name(token, customer_name)
        return matches[0] if matches else None

    async def _find_customers_by_name(self, token: str, customer_name: str) -> list[dict]:
        normalized_target = _canonical_income_customer_name(customer_name)
        if not normalized_target:
            return []

        matches: list[dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while page <= 20:
                response = await client.post(
                    f"{self.base_url}/clients/search",
                    headers=self._auth_headers(token),
                    json={"search": customer_name, "page": page, "pageSize": 100},
                )
                if response.status_code >= 400:
                    return []

                data = response.json()
                items = data.get("items", []) if isinstance(data, dict) else []
                for item in items:
                    candidate_name = _canonical_income_customer_name(item.get("name") or "")
                    if candidate_name and candidate_name == normalized_target:
                        item_id = str(item.get("id") or item.get("guid") or "").strip()
                        if item_id and any(str(existing.get("id") or existing.get("guid") or "").strip() == item_id for existing in matches):
                            continue
                        matches.append(item)

                total_pages = 1
                if isinstance(data, dict):
                    total_pages = int(data.get("pages") or 1)
                if page >= total_pages:
                    break
                page += 1

        return matches

    async def get_existing_customer_details_by_name(self, customer_name: str):
        token = await self._get_token()
        customer_data = await self._find_customer_by_name(token, customer_name)
        if not customer_data:
            return None
        return customer_data

    async def get_existing_customer_candidates_by_name(self, customer_name: str) -> list[dict]:
        token = await self._get_token()
        return await self._find_customers_by_name(token, customer_name)

    def _row_base(self, item, price_value):
        row = {
            "description": item.description,
            "quantity": float(item.quantity or 1),
            "price": float(price_value),
            "vatType": 0,
        }
        if getattr(item, "sku", None):
            row["sku"] = item.sku
            row["catalogNum"] = item.sku
            row["catalogNumber"] = item.sku
            row["itemCode"] = item.sku
        return row

    def _rows_for_delivery(self, po: PurchaseOrderData):
        rows = []
        for item in (po.items or []):
            rows.append(self._row_base(item, 0))
        if not rows:
            rows.append(
                {
                    "description": f"הזמנת רכש {po.po_number or ''}",
                    "quantity": 1,
                    "price": 0,
                    "vatType": 0,
                }
            )
        return rows

    def _rows_for_invoice(self, po: PurchaseOrderData):
        rows = []

        if po.items:
            for item in po.items:
                qty = float(item.quantity or 1)
                unit_price = float(item.unit_price or 0)
                line_total = float(item.line_total or 0)

                if unit_price <= 0:
                    if line_total > 0 and qty > 0:
                        unit_price = line_total / qty
                    elif float(po.subtotal or 0) > 0 and qty > 0:
                        unit_price = float(po.subtotal) / qty
                    elif float(po.total or 0) > 0 and qty > 0:
                        unit_price = float(po.total) / qty

                rows.append(self._row_base(item, unit_price))

        if not rows:
            amount = float(po.subtotal or po.total or 0)
            if amount <= 0:
                raise ValueError(f"סכום הזמנת רכש לא תקין: subtotal={po.subtotal}, total={po.total}")
            rows.append(
                {
                    "description": f"הזמנת רכש {po.po_number or ''}",
                    "quantity": 1,
                    "price": amount,
                    "vatType": 0,
                }
            )

        return rows

    def _normalize_document_response(self, data: dict):
        return SimpleNamespace(
            raw=data,
            document_id=data.get("id") or data.get("document_id") or data.get("documentId"),
            number=data.get("number") or data.get("document_number") or data.get("documentNumber"),
            url=(data.get("url") or {}).get("he") or (data.get("url") or {}).get("origin"),
        )

    async def create_document(self, token: str, payload: dict):
        print("DOCUMENT PAYLOAD:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/documents",
                headers=self._auth_headers(token),
                json=payload,
            )
            if response.status_code >= 400:
                print("STATUS:", response.status_code)
                print("RESPONSE TEXT:", response.text)
            response.raise_for_status()
            data = response.json()
            print("DOCUMENT RESPONSE:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return self._normalize_document_response(data)

    async def download_pdf(self, token: str, url: str, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            save_path.write_bytes(response.content)
        return save_path

    async def _build_sales_document_context(self, po: PurchaseOrderData):
        token = await self._get_token()
        delivery_type = await self._resolve_delivery_type(token)
        invoice_type = int(settings.greeninvoice_tax_invoice_doc_type or 305)

        footer_text = (po.extra or {}).get("footer_text", "")
        if po.customer_id:
            footer_text = f'ח.פ / ע.מ: {po.customer_id} | ' + footer_text

        customer_data = await self._find_customer_by_id(token, po.customer_id)
        if not customer_data and str(po.customer_name or "").strip():
            customer_data = await self._find_customer_by_name(token, str(po.customer_name or "").strip())

        if customer_data:
            client_payload = {"id": customer_data.get("id")}
            if not po.payment_terms_days:
                days = self._resolve_payment_days_for_customer(
                    customer_data=customer_data,
                    customer_id=po.customer_id or "",
                    customer_name=po.customer_name or "",
                )
                if days is not None:
                    po.payment_terms_days = days
                    po.payment_terms_label = f"שוטף + {days}"
        else:
            client_payload = {
                "name": f"{po.customer_name or ''} / ח.פ {po.customer_id}" if po.customer_id else (po.customer_name or ""),
                "email": po.customer_email or "",
                "idNumber": po.customer_id or "",
            }

        base_dir = Path("output")
        customer_val = (po.customer_name or "לקוח").split(" - ח.פ")[0]
        po_val = po.po_number or "document"
        safe_customer = _safe_folder_name(customer_val)
        safe_po = _safe_folder_name(po_val)
        folder_name = f"{safe_customer} - {safe_po}"

        return {
            "token": token,
            "delivery_type": delivery_type,
            "invoice_type": invoice_type,
            "footer_text": footer_text,
            "client_payload": client_payload,
            "folder_name": folder_name,
        }

    def _sales_output_dir(self, po: PurchaseOrderData, output_dir=None) -> Path:
        if output_dir:
            base_dir = Path(output_dir)
        else:
            sandbox_mode = "sandbox" in str(self.base_url or "").lower()
            base_dir = Path("output") / ("Sandbox Docs" if sandbox_mode else "Production Docs")
        customer_val = (po.customer_name or "לקוח").split(" - ח.פ")[0]
        po_val = po.po_number or "document"
        safe_customer = _safe_folder_name(customer_val)
        safe_po = _safe_folder_name(po_val)
        target_dir = base_dir / f"{safe_customer} - {safe_po}"
        if "sandbox" in str(self.base_url or "").lower():
            sandbox_target_name = target_dir.name
            if not sandbox_target_name.endswith("-sandbox"):
                target_dir = target_dir.with_name(f"{sandbox_target_name}-sandbox")
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    async def create_delivery_only(self, po: PurchaseOrderData, output_dir=None):
        ctx = await self._build_sales_document_context(po)
        delivery_payload = {
            "type": ctx["delivery_type"],
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": ctx["client_payload"],
            "description": f"הזמנת רכש {po.po_number or ''}",
            "remarks": ctx["footer_text"],
            "bottomText": ctx["footer_text"],
            "income": self._rows_for_delivery(po),
            "incomeRows": self._rows_for_delivery(po),
        }
        delivery = await self.create_document(ctx["token"], delivery_payload)
        delivery_pdf_path = None
        target_dir = self._sales_output_dir(po, output_dir)
        if delivery.url:
            delivery_pdf_path = await self.download_pdf(
                ctx["token"],
                delivery.url,
                target_dir / f"{_safe_folder_name(po.po_number or 'document')}_delivery_{delivery.number}.pdf",
            )
        return delivery, delivery_pdf_path

    async def create_invoice_only(self, po: PurchaseOrderData, output_dir=None, linked_document_id: str = ""):
        ctx = await self._build_sales_document_context(po)
        invoice_payload = {
            "type": ctx["invoice_type"],
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": ctx["client_payload"],
            "description": f"הזמנת רכש {po.po_number or ''}",
            "remarks": ctx["footer_text"],
            "bottomText": ctx["footer_text"],
            "linkedDocumentIds": [linked_document_id] if str(linked_document_id or "").strip() else [],
            "income": self._rows_for_invoice(po),
            "incomeRows": self._rows_for_invoice(po),
        }
        invoice = await self.create_document(ctx["token"], invoice_payload)
        invoice_pdf_path = None
        target_dir = self._sales_output_dir(po, output_dir)
        if invoice.url:
            invoice_pdf_path = await self.download_pdf(
                ctx["token"],
                invoice.url,
                target_dir / f"{_safe_folder_name(po.po_number or 'document')}_invoice_{invoice.number}.pdf",
            )
        return invoice, invoice_pdf_path

    async def create_delivery_and_invoice(self, po: PurchaseOrderData, output_dir=None):
        ctx = await self._build_sales_document_context(po)

        delivery_payload = {
            "type": ctx["delivery_type"],
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": ctx["client_payload"],
            "description": f"הזמנת רכש {po.po_number or ''}",
            "remarks": ctx["footer_text"],
            "bottomText": ctx["footer_text"],
            "income": self._rows_for_delivery(po),
            "incomeRows": self._rows_for_delivery(po),
        }

        invoice_payload = {
            "type": ctx["invoice_type"],
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": ctx["client_payload"],
            "description": f"הזמנת רכש {po.po_number or ''}",
            "remarks": ctx["footer_text"],
            "bottomText": ctx["footer_text"],
            "linkedDocumentIds": [],
            "income": self._rows_for_invoice(po),
            "incomeRows": self._rows_for_invoice(po),
        }

        delivery = await self.create_document(ctx["token"], delivery_payload)

        if delivery.document_id:
            invoice_payload["linkedDocumentIds"] = [delivery.document_id]

        invoice = await self.create_document(ctx["token"], invoice_payload)

        delivery_pdf_path = None
        invoice_pdf_path = None

        output_dir = self._sales_output_dir(po, output_dir)
        safe_po = _safe_folder_name(po.po_number or "document")

        if delivery.url:
            delivery_pdf_path = await self.download_pdf(
                ctx["token"],
                delivery.url,
                output_dir / f"{safe_po}_delivery_{delivery.number}.pdf",
            )

        if invoice.url:
            invoice_pdf_path = await self.download_pdf(
                ctx["token"],
                invoice.url,
                output_dir / f"{safe_po}_invoice_{invoice.number}.pdf",
            )

        return delivery, invoice, delivery_pdf_path, invoice_pdf_path

    def _extract_list_from_response(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data", "documents", "rows", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    def _extract_text(self, item: dict, keys: tuple[str, ...]) -> str:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("name", "title", "label", "text", "value"):
                    nested = value.get(nested_key)
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
        return ""

    def _extract_number(self, item: dict, keys: tuple[str, ...]) -> float:
        for key in keys:
            value = item.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = re.sub(r"[^\d.\-]", "", value)
                if cleaned in ("", "-", ".", "-."):
                    continue
                try:
                    return float(cleaned)
                except Exception:
                    continue
            if isinstance(value, dict):
                nested = self._extract_number(value, ("value", "amount", "total"))
                if nested:
                    return nested
        return 0.0

    def _extract_document_date(self, item: dict) -> str:
        for key in ("date", "documentDate", "createdAt", "created_at", "issueDate"):
            value = item.get(key)
            if not value:
                continue
            txt = str(value).strip()
            if not txt:
                continue
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            m = re.search(r"(\d{2})/(\d{2})/(\d{4})", txt)
            if m:
                return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return ""

    def _extract_due_date(self, item: dict) -> str:
        for key in ("dueDate", "paymentDate", "targetDate", "closingDate"):
            value = item.get(key)
            if not value:
                continue
            txt = str(value).strip()
            if not txt:
                continue
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            m = re.search(r"(\d{2})/(\d{2})/(\d{4})", txt)
            if m:
                return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return ""

    def _parse_iso_date(self, value: str) -> date | None:
        try:
            return datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
        except Exception:
            return None

    def _document_type_text(self, item: dict) -> str:
        parts = [
            self._extract_text(item, ("typeName", "documentTypeName", "document_type_name", "typeLabel")),
        ]
        type_value = item.get("type")
        if isinstance(type_value, str) and type_value.strip():
            parts.append(type_value.strip())
        document_type_value = item.get("documentType")
        if isinstance(document_type_value, str) and document_type_value.strip():
            parts.append(document_type_value.strip())
        document_type_alt = item.get("document_type")
        if isinstance(document_type_alt, str) and document_type_alt.strip():
            parts.append(document_type_alt.strip())
        if isinstance(item.get("documentType"), dict):
            parts.append(self._extract_text(item.get("documentType") or {}, ("name", "title", "label", "description", "value")))
        if isinstance(item.get("type"), dict):
            parts.append(self._extract_text(item.get("type") or {}, ("name", "title", "label", "description", "value")))
        if isinstance(item.get("documentTypeName"), dict):
            parts.append(self._extract_text(item.get("documentTypeName") or {}, ("name", "title", "label", "description", "value")))
        return " ".join([p for p in parts if p]).strip().lower()

    def _document_type_code(self, item: dict) -> str:
        candidates = []
        for key in ("type", "documentType", "document_type", "typeId", "documentTypeId"):
            value = item.get(key)
            if isinstance(value, (int, float)):
                candidates.append(str(int(value)))
            elif isinstance(value, str) and value.strip().isdigit():
                candidates.append(value.strip())
            elif isinstance(value, dict):
                for nested_key in ("id", "value", "code", "type"):
                    nested = value.get(nested_key)
                    if isinstance(nested, (int, float)):
                        candidates.append(str(int(nested)))
                    elif isinstance(nested, str) and nested.strip().isdigit():
                        candidates.append(nested.strip())
        return candidates[0] if candidates else ""

    def _looks_like_income_document(self, item: dict) -> bool:
        txt = self._document_type_text(item)
        income_terms = (
            "חשבונית מס",
            "חשבונית מס קבלה",
            "חשבונית מס-קבלה",
            "קבלה",
            "חשבונית",
            "receipt",
            "invoice",
            "credit",
            "זיכוי",
        )
        exclude_terms = (
            "תעודת משלוח",
            "delivery",
            "purchase order",
            "הזמנת רכש",
            "הצעת מחיר",
            "quote",
        )
        return any(term in txt for term in income_terms) and not any(term in txt for term in exclude_terms)

    def _looks_like_invoice_document(self, item: dict) -> bool:
        type_code = self._document_type_code(item)
        if type_code in {"305", "320"}:
            return True

        txt = self._document_type_text(item)
        invoice_terms = (
            "חשבונית מס",
            "חשבונית מס קבלה",
            "חשבונית מס-קבלה",
            "invoice",
        )
        exclude_terms = (
            "קבלה",
            "receipt",
            "תעודת משלוח",
            "delivery",
            "הצעת מחיר",
            "quote",
            "זיכוי",
            "credit",
        )
        return any(term in txt for term in invoice_terms) and not any(term in txt for term in exclude_terms)

    def _looks_like_quote_document(self, item: dict) -> bool:
        type_code = self._document_type_code(item)
        if type_code == "10":
            return True
        txt = self._document_type_text(item)
        quote_terms = (
            "הצעת מחיר",
            "quote",
            "price quote",
            "quotation",
        )
        exclude_terms = (
            "תעודת משלוח",
            "delivery",
            "חשבונית",
            "invoice",
            "קבלה",
            "receipt",
        )
        return any(term in txt for term in quote_terms) and not any(term in txt for term in exclude_terms)

    def _looks_like_delivery_document(self, item: dict) -> bool:
        type_code = self._document_type_code(item)
        if type_code == "200":
            return True
        txt = self._document_type_text(item)
        delivery_terms = (
            "תעודת משלוח",
            "delivery",
            "delivery note",
        )
        exclude_terms = (
            "הצעת מחיר",
            "quote",
            "חשבונית",
            "invoice",
            "קבלה",
            "receipt",
        )
        return any(term in txt for term in delivery_terms) and not any(term in txt for term in exclude_terms)

    def _looks_like_purchase_order_document(self, item: dict) -> bool:
        type_code = self._document_type_code(item)
        if type_code == "500":
            return True
        txt = self._document_type_text(item)
        purchase_terms = (
            "הזמנת רכש",
            "הזמנת קניה",
            "purchase order",
            "po",
        )
        exclude_terms = (
            "הצעת מחיר",
            "quote",
            "תעודת משלוח",
            "delivery",
            "חשבונית",
            "invoice",
            "קבלה",
            "receipt",
        )
        return any(term in txt for term in purchase_terms) and not any(term in txt for term in exclude_terms)

    def _extract_document_url(self, item: dict) -> str:
        candidates = [
            item.get("url"),
            item.get("pdfUrl"),
            item.get("downloadUrl"),
            item.get("documentUrl"),
            item.get("documentLink"),
        ]
        for nested_key in ("links", "document", "pdf", "files"):
            nested = item.get(nested_key)
            if isinstance(nested, dict):
                candidates.extend(
                    [
                        nested.get("url"),
                        nested.get("pdfUrl"),
                        nested.get("downloadUrl"),
                        nested.get("href"),
                    ]
                )
            elif isinstance(nested, list):
                for sub_item in nested:
                    if isinstance(sub_item, dict):
                        candidates.extend(
                            [
                                sub_item.get("url"),
                                sub_item.get("pdfUrl"),
                                sub_item.get("downloadUrl"),
                                sub_item.get("href"),
                            ]
                        )
        for value in candidates:
            if isinstance(value, dict):
                for nested_key in ("he", "origin", "url", "pdfUrl", "downloadUrl", "href"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return _normalize_greeninvoice_url(nested_value.strip())
            if isinstance(value, str) and value.strip():
                return _normalize_greeninvoice_url(value.strip())
        return ""

    def _extract_item_name(self, item: dict) -> str:
        def _clean(value: str) -> str:
            return re.sub(r"\s+", " ", str(value or "").strip())

        line_collections = []
        for key in ("income", "incomeRows", "rows", "items", "products", "lines"):
            value = item.get(key)
            if isinstance(value, list):
                line_collections.append(value)
            elif isinstance(value, dict):
                for nested_key in ("rows", "items", "products", "lines"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        line_collections.append(nested)

        for collection in line_collections:
            for line in collection:
                if not isinstance(line, dict):
                    continue
                for key in ("description", "name", "itemName", "title", "productName"):
                    text = _clean(line.get(key))
                    if text:
                        return text
        return ""

    def _extract_item_sku(self, item: dict) -> str:
        def _clean(value: str) -> str:
            return re.sub(r"\s+", " ", str(value or "").strip())

        line_collections = []
        for key in ("income", "incomeRows", "rows", "items", "products", "lines", "expense", "expenseRows"):
            value = item.get(key)
            if isinstance(value, list):
                line_collections.append(value)
            elif isinstance(value, dict):
                for nested_key in ("rows", "items", "products", "lines"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        line_collections.append(nested)

        for collection in line_collections:
            for line in collection:
                if not isinstance(line, dict):
                    continue
                for key in ("sku", "itemCode", "catalogNum", "catalogNumber", "productSku", "code", "catalogNo"):
                    text = _clean(line.get(key))
                    if text:
                        return text
        return ""

    def _extract_first_line_value(self, item: dict, keys: tuple[str, ...]) -> str:
        line_collections = []
        for key in ("income", "incomeRows", "rows", "items", "products", "lines", "expense", "expenseRows"):
            value = item.get(key)
            if isinstance(value, list):
                line_collections.append(value)
            elif isinstance(value, dict):
                for nested_key in ("rows", "items", "products", "lines"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        line_collections.append(nested)
        for collection in line_collections:
            for line in collection:
                if not isinstance(line, dict):
                    continue
                for key in keys:
                    value = line.get(key)
                    if value is None:
                        continue
                    text = str(value).strip()
                    if text:
                        return text
        return ""

    def _normalize_income_document(self, item: dict) -> dict | None:
        if not isinstance(item, dict):
            return None

        doc_type = self._document_type_text(item)
        if doc_type and not self._looks_like_income_document(item):
            return None

        amount = self._extract_number(
            item,
            (
                "amount",
                "sum",
                "total",
                "totalAmount",
                "gross",
                "grossAmount",
                "grandTotal",
            ),
        )
        if amount == 0:
            amount = self._extract_number(item, ("openAmount", "balance", "paidAmount"))

        if "זיכוי" in doc_type or "credit" in doc_type:
            amount = -abs(amount)

        number = self._extract_text(item, ("number", "documentNumber", "id"))
        customer_name = self._extract_text(item, ("clientName", "customerName", "name"))
        client_data = item.get("client") or {}
        if not customer_name and isinstance(client_data, dict):
            customer_name = self._extract_text(client_data or {}, ("name", "fullName"))
        customer_id = self._extract_text(client_data, ("taxId", "idNumber", "vatNumber", "companyNumber"))
        client_id = self._extract_text(client_data, ("id",))

        date_value = self._extract_document_date(item)
        if not date_value:
            return None

        return {
            "id": self._extract_text(item, ("id", "documentId", "uuid")),
            "number": number,
            "date": date_value,
            "amount": amount,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "client_id": client_id,
            "type": doc_type or "income document",
            "type_code": self._document_type_code(item),
            "source_url": self._extract_document_url(item),
            "item_name": self._extract_item_name(item),
            "raw": item,
        }

    def _normalize_quote_document(self, item: dict) -> dict | None:
        if not isinstance(item, dict) or not self._looks_like_quote_document(item):
            return None
        date_value = self._extract_document_date(item)
        if not date_value:
            return None
        client_data = item.get("client") or {}
        customer_name = self._extract_text(item, ("clientName", "customerName", "name"))
        if not customer_name and isinstance(client_data, dict):
            customer_name = self._extract_text(client_data or {}, ("name", "fullName"))
        customer_id = self._extract_text(client_data, ("taxId", "idNumber", "vatNumber", "companyNumber"))
        client_id = self._extract_text(client_data, ("id",))
        return {
            "id": self._extract_text(item, ("id", "documentId", "uuid")),
            "number": self._extract_text(item, ("number", "documentNumber", "id")),
            "date": date_value,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "client_id": client_id,
            "type": self._document_type_text(item) or "quote",
            "type_code": self._document_type_code(item),
            "source_url": self._extract_document_url(item),
            "item_name": self._extract_item_name(item),
            "raw": item,
        }

    def _normalize_delivery_document(self, item: dict) -> dict | None:
        if not isinstance(item, dict) or not self._looks_like_delivery_document(item):
            return None
        date_value = self._extract_document_date(item)
        if not date_value:
            return None
        client_data = item.get("client") or {}
        customer_name = self._extract_text(item, ("clientName", "customerName", "name"))
        if not customer_name and isinstance(client_data, dict):
            customer_name = self._extract_text(client_data or {}, ("name", "fullName"))
        customer_id = self._extract_text(client_data, ("taxId", "idNumber", "vatNumber", "companyNumber"))
        client_id = self._extract_text(client_data, ("id",))
        return {
            "id": self._extract_text(item, ("id", "documentId", "uuid")),
            "number": self._extract_text(item, ("number", "documentNumber", "id")),
            "date": date_value,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "client_id": client_id,
            "type": self._document_type_text(item) or "delivery",
            "type_code": self._document_type_code(item),
            "source_url": self._extract_document_url(item),
            "item_name": self._extract_item_name(item),
            "raw": item,
        }

    def _normalize_purchase_order_document(self, item: dict) -> dict | None:
        if not isinstance(item, dict) or not self._looks_like_purchase_order_document(item):
            return None
        date_value = self._extract_document_date(item)
        if not date_value:
            return None
        client_data = item.get("client") or item.get("recipient") or {}
        customer_name = self._extract_text(item, ("clientName", "customerName", "name"))
        if not customer_name and isinstance(client_data, dict):
            customer_name = self._extract_text(client_data or {}, ("name", "fullName"))
        customer_id = self._extract_text(client_data, ("taxId", "idNumber", "vatNumber", "companyNumber"))
        client_id = self._extract_text(client_data, ("id",))
        customer_email = self._extract_text(client_data, ("email", "mail"))
        customer_phone = self._extract_text(client_data, ("phone", "mobile", "cellular"))
        subtotal = self._extract_number(item, ("beforeVatAmount", "subtotal", "subTotal", "amountBeforeVat", "amount"))
        vat = self._extract_number(item, ("vatAmount", "vat", "tax", "taxAmount"))
        total = self._extract_number(item, ("amount", "amountLocal", "total", "totalAmount", "calculatedAmountLocal"))
        item_quantity = self._extract_first_line_value(item, ("quantity", "qty", "count", "amount"))
        item_unit = self._extract_first_line_value(item, ("unit", "unitName", "measureUnit", "measurementUnit"))
        item_unit_price = self._extract_first_line_value(item, ("unitPrice", "pricePerUnit", "price"))
        return {
            "id": self._extract_text(item, ("id", "documentId", "uuid")),
            "number": self._extract_text(item, ("number", "documentNumber", "id")),
            "date": date_value,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "client_id": client_id,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "type": self._document_type_text(item) or "purchase order",
            "type_code": self._document_type_code(item),
            "source_url": self._extract_document_url(item),
            "item_name": self._extract_item_name(item),
            "item_sku": self._extract_item_sku(item),
            "item_quantity": item_quantity,
            "item_unit": item_unit,
            "item_unit_price": item_unit_price,
            "subtotal": round(subtotal, 2) if subtotal else 0,
            "vat": round(vat, 2) if vat else 0,
            "total": round(total, 2) if total else 0,
            "raw": item,
        }

    def _normalize_open_invoice_document(self, item: dict) -> dict | None:
        if not isinstance(item, dict) or not self._looks_like_invoice_document(item):
            return None

        due_date = self._extract_due_date(item)
        if not due_date:
            return None

        amount_open = self._extract_number(
            item,
            (
                "amountOpened",
                "calculatedAmountOpenedLocal",
                "openAmount",
                "balance",
            ),
        )
        if amount_open <= 0:
            return None

        amount_total = self._extract_number(
            item,
            (
                "amount",
                "amountLocal",
                "calculatedAmountLocal",
                "total",
                "totalAmount",
            ),
        )
        document_date = self._extract_document_date(item)
        has_payment_rows = bool(item.get("payment"))
        has_any_receipt = has_payment_rows

        if has_any_receipt:
            return None

        # מציגים רק חשבוניות שלא הופקה להן קבלה כלל.
        # אם היתרה הפתוחה קטנה מהסכום הכולל, זה אומר שכבר הייתה סגירה/גבייה חלקית
        # או קיזוז כמו ניכוי מס במקור, ולכן לא נרצה להציג אותה ברשימה הזו.
        if amount_total > 0 and abs(amount_open - amount_total) > 0.01:
            return None

        client = item.get("client") or {}
        customer_name = self._extract_text(client, ("name", "fullName")) or self._extract_text(
            item, ("clientName", "customerName", "name")
        )
        customer_id = self._extract_text(client, ("taxId", "idNumber", "vatNumber", "companyNumber"))
        client_id = self._extract_text(client, ("id",))

        return {
            "id": self._extract_text(item, ("id", "documentId", "uuid")),
            "number": self._extract_text(item, ("number", "documentNumber")),
            "document_date": document_date,
            "due_date": due_date,
            "amount_open": round(amount_open, 2),
            "amount_total": round(amount_total, 2),
            "has_receipt": has_any_receipt,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "client_id": client_id,
            "currency": self._extract_text(item, ("currency",)) or "ILS",
            "type": self._document_type_text(item) or "invoice",
            "type_code": self._document_type_code(item),
            "raw": item,
        }

    async def _search_documents_page(self, token: str, page: int, page_size: int, date_from: str, date_to: str):
        attempts = [
            ("post", f"{self.base_url}/documents/search", {"page": page, "pageSize": page_size, "fromDate": date_from, "toDate": date_to}),
            ("post", f"{self.base_url}/documents/search", {"page": page, "pageSize": page_size, "dateFrom": date_from, "dateTo": date_to}),
            ("post", f"{self.base_url}/documents/search", {"page": page, "pageSize": page_size, "filters": {"dateFrom": date_from, "dateTo": date_to}}),
            ("get", f"{self.base_url}/documents", {"page": page, "pageSize": page_size, "dateFrom": date_from, "dateTo": date_to}),
        ]

        last_error = None
        async with httpx.AsyncClient(timeout=60) as client:
            for method, url, payload in attempts:
                try:
                    if method == "post":
                        response = await client.post(url, headers=self._auth_headers(token), json=payload)
                    else:
                        response = await client.get(url, headers=self._auth_headers(token), params=payload)

                    if response.status_code >= 400:
                        last_error = RuntimeError(f"documents search failed: {response.status_code} {response.text[:300]}")
                        continue

                    data = response.json()
                    items = self._extract_list_from_response(data)
                    meta = data if isinstance(data, dict) else {}
                    return items, meta
                except Exception as exc:
                    last_error = exc
                    continue

        if last_error:
            raise last_error
        raise RuntimeError("לא הצלחנו לבצע חיפוש מסמכים בחשבונית ירוקה.")

    async def get_income_documents(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 12):
        token = await self._get_token()
        documents = []

        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, date_from, date_to)
            if not items:
                break

            normalized_items = []
            for item in items:
                doc = self._normalize_income_document(item)
                if doc:
                    normalized_items.append(doc)

            documents.extend(normalized_items)

            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass

            if page >= total_pages or len(items) < page_size:
                break

        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('date')}"
            deduped[key] = doc

        return list(deduped.values())

    async def get_invoice_documents(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 24):
        token = await self._get_token()
        documents = []

        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, date_from, date_to)
            if not items:
                break

            normalized_items = []
            for item in items:
                if not self._looks_like_invoice_document(item):
                    continue
                doc = self._normalize_income_document(item)
                if doc:
                    normalized_items.append(doc)

            documents.extend(normalized_items)

            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass

            if page >= total_pages or len(items) < page_size:
                break

        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('date')}"
            deduped[key] = doc

        return sorted(
            deduped.values(),
            key=lambda doc: (doc.get("date") or "", doc.get("customer_name") or "", doc.get("number") or ""),
        )

    async def get_quote_documents(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 36):
        token = await self._get_token()
        documents = []
        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, date_from, date_to)
            if not items:
                break
            for item in items:
                doc = self._normalize_quote_document(item)
                if doc:
                    documents.append(doc)
            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass
            if page >= total_pages or len(items) < page_size:
                break
        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('date')}"
            deduped[key] = doc
        return sorted(deduped.values(), key=lambda doc: (doc.get("date") or "", doc.get("customer_name") or "", doc.get("number") or ""), reverse=True)

    async def get_delivery_documents(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 80):
        token = await self._get_token()
        documents = []
        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, date_from, date_to)
            if not items:
                break
            for item in items:
                doc = self._normalize_delivery_document(item)
                if doc:
                    documents.append(doc)
            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass
            if page >= total_pages or len(items) < page_size:
                break
        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('date')}"
            deduped[key] = doc
        return sorted(deduped.values(), key=lambda doc: (doc.get("date") or "", doc.get("customer_name") or "", doc.get("number") or ""), reverse=True)

    async def get_purchase_order_documents(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 24):
        token = await self._get_token()
        documents = []
        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, date_from, date_to)
            if not items:
                break
            for item in items:
                doc = self._normalize_purchase_order_document(item)
                if doc:
                    documents.append(doc)
            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass
            if page >= total_pages or len(items) < page_size:
                break
        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('date')}"
            deduped[key] = doc
        return sorted(
            deduped.values(),
            key=lambda doc: (doc.get("date") or "", doc.get("customer_name") or "", doc.get("number") or ""),
            reverse=True,
        )

    async def list_invoice_customers(self, date_from: str, date_to: str, page_size: int = 100, max_pages: int = 24):
        documents = await self.get_invoice_documents(date_from=date_from, date_to=date_to, page_size=page_size, max_pages=max_pages)
        customers: dict[str, dict] = {}

        for doc in documents:
            customer_name = _normalize_income_customer_name(doc.get("customer_name") or "")
            customer_id = _normalize_income_customer_id(doc.get("customer_id") or "")
            normalized_customer_name = _canonical_income_customer_name(customer_name)
            customer_key = f"tax:{customer_id}" if customer_id else f"name:{normalized_customer_name}"
            if not customer_name and not customer_id:
                continue
            entry = customers.get(customer_key)
            if not entry:
                entry = {
                    "customer_key": customer_key,
                    "customer_id": customer_id,
                    "customer_name": customer_name or "ללא שם",
                    "documents_count": 0,
                    "total_amount": 0.0,
                    "last_date": "",
                }
                customers[customer_key] = entry

            entry["documents_count"] += 1
            entry["total_amount"] = round(float(entry["total_amount"]) + float(doc.get("amount") or 0), 2)
            doc_date = str(doc.get("date") or "")
            if doc_date and doc_date > str(entry.get("last_date") or ""):
                entry["last_date"] = doc_date

        return _merge_income_customer_entries(list(customers.values()))

    async def list_all_clients(self, page_size: int = 100, max_pages: int = 40):
        token = await self._get_token()
        customers: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=60) as client:
            for page in range(1, max_pages + 1):
                response = await client.post(
                    f"{self.base_url}/clients/search",
                    headers=self._auth_headers(token),
                    json={"search": "", "page": page, "pageSize": page_size},
                )

                if response.status_code >= 400:
                    raise RuntimeError(f"clients search failed: {response.status_code} {response.text[:300]}")

                data = response.json() if response.content else {}
                items = data.get("items", []) if isinstance(data, dict) else []
                if not items:
                    break

                for item in items:
                    customer_name = _normalize_income_customer_name(
                        item.get("name") or item.get("fullName") or item.get("customerName") or ""
                    )
                    customer_id = _normalize_income_customer_id(
                        item.get("taxId")
                        or item.get("idNumber")
                        or item.get("vatNumber")
                        or item.get("companyNumber")
                        or item.get("companyId")
                        or ""
                    )
                    if not customer_name and not customer_id:
                        continue
                    normalized_customer_name = _canonical_income_customer_name(customer_name)
                    customer_key = f"tax:{customer_id}" if customer_id else f"name:{normalized_customer_name}"
                    entry = customers.get(customer_key)
                    if not entry:
                        emails_value = item.get("emails") or []
                        emails: list[str] = []
                        if isinstance(emails_value, list):
                            for email_item in emails_value:
                                if isinstance(email_item, dict):
                                    email_value = str(email_item.get("email") or "").strip()
                                else:
                                    email_value = str(email_item or "").strip()
                                if email_value:
                                    emails.append(email_value)
                        customers[customer_key] = {
                            "customer_key": customer_key,
                            "customer_guid": str(item.get("id") or item.get("guid") or "").strip(),
                            "customer_id": customer_id,
                            "customer_name": customer_name or "ללא שם",
                            "active": "TRUE" if bool(item.get("active")) else "FALSE",
                            "send": "TRUE" if bool(item.get("send")) else "FALSE",
                            "department": str(item.get("department") or "").strip(),
                            "accounting_key": str(item.get("accountingKey") or item.get("accounting_key") or "").strip(),
                            "payment_terms_days": str(self._extract_payment_days_from_customer(item) or ""),
                            "phone": str(item.get("phone") or "").strip(),
                            "mobile": str(item.get("mobile") or "").strip(),
                            "emails": ", ".join(emails),
                            "contact_person": str(item.get("contactPerson") or "").strip(),
                            "address": str(item.get("address") or "").strip(),
                            "city": str(item.get("city") or "").strip(),
                            "zip": str(item.get("zip") or "").strip(),
                            "country": str(item.get("country") or "").strip(),
                            "bank_name": str(item.get("bankName") or "").strip(),
                            "bank_branch": str(item.get("bankBranch") or "").strip(),
                            "bank_account": str(item.get("bankAccount") or "").strip(),
                            "remarks": str(item.get("remarks") or "").strip(),
                            "income_amount": str(item.get("incomeAmount") or ""),
                            "payment_amount": str(item.get("paymentAmount") or ""),
                            "balance_amount": str(item.get("balanceAmount") or ""),
                            "creation_date": str(item.get("creationDate") or "").strip(),
                            "last_update_date": str(item.get("lastUpdateDate") or "").strip(),
                        }

                total_pages = 1
                if isinstance(data, dict):
                    try:
                        total_pages = int(data.get("pages") or 1)
                    except Exception:
                        total_pages = 1
                if page >= total_pages or len(items) < page_size:
                    break

        return sorted(
            customers.values(),
            key=lambda row: (
                _canonical_income_customer_name(row.get("customer_name") or ""),
                str(row.get("customer_id") or ""),
            ),
        )

    async def create_client(self, payload: dict):
        token = await self._get_token()
        request_payload: dict = {}
        source = payload if isinstance(payload, dict) else {}
        allow_missing_id_number = bool(source.get("allowMissingIdNumber"))

        def _clean(value):
            return str(value or "").strip()

        if _clean(source.get("name")):
            request_payload["name"] = _clean(source.get("name"))
        if _clean(source.get("idNumber")):
            normalized_id = re.sub(r"\D+", "", _clean(source.get("idNumber")))
            request_payload["idNumber"] = normalized_id
            request_payload["taxId"] = normalized_id
        if _clean(source.get("phone")):
            request_payload["phone"] = _clean(source.get("phone"))
        if _clean(source.get("mobile")):
            request_payload["mobile"] = _clean(source.get("mobile"))
        if _clean(source.get("contactPerson")):
            request_payload["contactPerson"] = _clean(source.get("contactPerson"))
        if _clean(source.get("address")):
            request_payload["address"] = _clean(source.get("address"))
        if _clean(source.get("city")):
            request_payload["city"] = _clean(source.get("city"))
        if _clean(source.get("zip")):
            request_payload["zip"] = _clean(source.get("zip"))
        if _clean(source.get("country")):
            request_payload["country"] = _clean(source.get("country"))
        if _clean(source.get("remarks")):
            request_payload["remarks"] = _clean(source.get("remarks"))
        if _clean(source.get("department")):
            request_payload["department"] = _clean(source.get("department"))

        active_raw = str(source.get("active") or "").strip().lower()
        if active_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            request_payload["active"] = active_raw in {"true", "1", "yes", "on"}

        send_raw = str(source.get("send") or "").strip().lower()
        if send_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            request_payload["send"] = send_raw in {"true", "1", "yes", "on"}

        accounting_key = _clean(source.get("accountingKey"))
        if accounting_key:
            request_payload["accountingKey"] = accounting_key

        payment_terms = str(source.get("paymentTerms") or "").strip()
        if payment_terms:
            days_match = re.search(r"(\d+)", payment_terms)
            if days_match:
                request_payload["paymentTerms"] = int(days_match.group(1))

        emails_source = source.get("emails") or []
        emails: list[str] = []
        if isinstance(emails_source, list):
            for email in emails_source:
                cleaned = _clean(email)
                if cleaned:
                    emails.append(cleaned)
        else:
            for email in re.split(r"[;,]+", str(emails_source or "")):
                cleaned = _clean(email)
                if cleaned:
                    emails.append(cleaned)
        if emails:
            request_payload["emails"] = emails

        if not request_payload.get("name"):
            raise ValueError("חסר שם לקוח.")
        if not request_payload.get("idNumber") and not allow_missing_id_number:
            raise ValueError("חסר ח.פ / ת.ז.")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/clients",
                headers=self._auth_headers(token),
                json=request_payload,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"clients create failed: {response.status_code} {response.text[:300]}")
        return response.json() if response.content else {"status": "ok"}

    async def update_client(self, client_guid: str, payload: dict):
        token = await self._get_token()
        client_guid = str(client_guid or "").strip()
        if not client_guid:
            raise ValueError("חסר מזהה לקוח פנימי לעדכון.")

        request_payload: dict = {}
        source = payload if isinstance(payload, dict) else {}
        allow_missing_id_number = bool(source.get("allowMissingIdNumber"))

        def _clean(value):
            return str(value or "").strip()

        if _clean(source.get("name")):
            request_payload["name"] = _clean(source.get("name"))
        if _clean(source.get("idNumber")):
            normalized_id = re.sub(r"\D+", "", _clean(source.get("idNumber")))
            request_payload["idNumber"] = normalized_id
            request_payload["taxId"] = normalized_id
        if _clean(source.get("phone")):
            request_payload["phone"] = _clean(source.get("phone"))
        if _clean(source.get("mobile")):
            request_payload["mobile"] = _clean(source.get("mobile"))
        if _clean(source.get("contactPerson")):
            request_payload["contactPerson"] = _clean(source.get("contactPerson"))
        if _clean(source.get("address")):
            request_payload["address"] = _clean(source.get("address"))
        if _clean(source.get("city")):
            request_payload["city"] = _clean(source.get("city"))
        if _clean(source.get("zip")):
            request_payload["zip"] = _clean(source.get("zip"))
        if _clean(source.get("country")):
            request_payload["country"] = _clean(source.get("country"))
        if _clean(source.get("remarks")):
            request_payload["remarks"] = _clean(source.get("remarks"))
        if _clean(source.get("department")):
            request_payload["department"] = _clean(source.get("department"))

        active_raw = str(source.get("active") or "").strip().lower()
        if active_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            request_payload["active"] = active_raw in {"true", "1", "yes", "on"}

        send_raw = str(source.get("send") or "").strip().lower()
        if send_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            request_payload["send"] = send_raw in {"true", "1", "yes", "on"}

        accounting_key = _clean(source.get("accountingKey"))
        if accounting_key:
            request_payload["accountingKey"] = accounting_key

        payment_terms = str(source.get("paymentTerms") or "").strip()
        if payment_terms:
            days_match = re.search(r"(\d+)", payment_terms)
            if days_match:
                request_payload["paymentTerms"] = int(days_match.group(1))

        emails_source = source.get("emails") or []
        emails: list[str] = []
        if isinstance(emails_source, list):
            for email in emails_source:
                cleaned = _clean(email)
                if cleaned:
                    emails.append(cleaned)
        else:
            for email in re.split(r"[;,]+", str(emails_source or "")):
                cleaned = _clean(email)
                if cleaned:
                    emails.append(cleaned)
        if emails:
            request_payload["emails"] = emails

        if not request_payload.get("name"):
            raise ValueError("חסר שם לקוח.")
        if not request_payload.get("idNumber") and not allow_missing_id_number:
            raise ValueError("חסר ח.פ / ת.ז.")

        candidate_requests = (
            ("put", f"{self.base_url}/clients/{client_guid}"),
            ("patch", f"{self.base_url}/clients/{client_guid}"),
        )
        last_error = ""
        async with httpx.AsyncClient(timeout=60) as client:
            for method, url in candidate_requests:
                response = await client.request(
                    method.upper(),
                    url,
                    headers=self._auth_headers(token),
                    json=request_payload,
                )
                if 200 <= response.status_code < 300:
                    return response.json() if response.content else {"status": "ok"}
                if response.status_code in {404, 405}:
                    last_error = f"{method.upper()} {url} -> {response.status_code}"
                    continue
                raise RuntimeError(f"clients update failed: {response.status_code} {response.text[:300]}")
        raise RuntimeError(f"clients update failed: {last_error or 'endpoint not found'}")

    async def delete_client(self, client_guid: str):
        token = await self._get_token()
        client_guid = str(client_guid or "").strip()
        if not client_guid:
            raise ValueError("חסר מזהה לקוח פנימי למחיקה.")

        candidate_requests = (
            ("delete", f"{self.base_url}/clients/{client_guid}"),
            ("post", f"{self.base_url}/clients/{client_guid}/delete"),
        )
        last_error = ""
        async with httpx.AsyncClient(timeout=60) as client:
            for method, url in candidate_requests:
                response = await client.request(
                    method.upper(),
                    url,
                    headers=self._auth_headers(token),
                )
                if 200 <= response.status_code < 300:
                    return response.json() if response.content else {"status": "ok"}
                if response.status_code in {404, 405}:
                    last_error = f"{method.upper()} {url} -> {response.status_code}"
                    continue
                raise RuntimeError(f"clients delete failed: {response.status_code} {response.text[:300]}")
        raise RuntimeError(f"clients delete failed: {last_error or 'endpoint not found'}")

    async def get_open_invoices_due_between(
        self,
        due_from: str | None,
        due_to: str,
        page_size: int = 100,
        max_pages: int = 24,
        search_months_back: int = 24,
    ):
        token = await self._get_token()
        due_to_date = self._parse_iso_date(due_to)
        due_from_date = self._parse_iso_date(due_from) if due_from else None
        if not due_to_date:
            raise ValueError("טווח תאריכים לא תקין.")

        search_anchor = due_from_date or due_to_date
        search_start = (search_anchor - timedelta(days=search_months_back * 31)).isoformat()
        search_end = due_to
        documents = []

        for page in range(1, max_pages + 1):
            items, meta = await self._search_documents_page(token, page, page_size, search_start, search_end)
            if not items:
                break

            for item in items:
                doc = self._normalize_open_invoice_document(item)
                if not doc:
                    continue
                doc_due_date = self._parse_iso_date(doc.get("due_date"))
                if not doc_due_date:
                    continue
                if ((not due_from_date) or (due_from_date <= doc_due_date)) and doc_due_date <= due_to_date:
                    documents.append(doc)

            total_pages = 1
            for key in ("pages", "totalPages", "pageCount"):
                value = meta.get(key) if isinstance(meta, dict) else None
                if value:
                    try:
                        total_pages = int(value)
                        break
                    except Exception:
                        pass

            if page >= total_pages or len(items) < page_size:
                break

        deduped = {}
        for doc in documents:
            key = f"{doc.get('id')}::{doc.get('number')}::{doc.get('due_date')}"
            deduped[key] = doc

        return sorted(
            deduped.values(),
            key=lambda doc: (doc.get("due_date") or "", doc.get("customer_name") or "", doc.get("number") or ""),
        )

    def _build_receipt_payment_row(self, payment: dict) -> dict:
        payment_method = str(payment.get("payment_method") or "").strip()
        amount = float(payment.get("amount") or 0)
        payment_date = str(payment.get("payment_date") or date.today().isoformat()).strip()

        if amount <= 0:
            raise ValueError("סכום הקבלה חייב להיות גדול מ-0.")

        base_row = {
            "amount": amount,
            "price": amount,
            "currency": "ILS",
            "date": payment_date,
            "ref": [],
        }

        if payment_method == "bank_transfer":
            return {
                **base_row,
                "type": 4,
                "name": "העברה בנקאית",
                "description": (payment.get("notes") or "").strip(),
            }

        if payment_method == "cash":
            return {
                **base_row,
                "type": 1,
                "name": "מזומן",
                "description": (payment.get("notes") or "").strip(),
            }

        if payment_method == "payment_app":
            provider = str(payment.get("payment_app_provider") or "bit").strip()
            sub_type = 1 if provider.lower() == "bit" else 2 if provider.lower() == "paybox" else None
            row = {
                **base_row,
                "type": 10,
                "name": "אפליקציית תשלום",
                "description": provider,
            }
            if sub_type:
                row["subType"] = sub_type
            return row

        if payment_method == "check":
            check_number = str(payment.get("check_number") or "").strip()
            bank_number = str(payment.get("bank_number") or "").strip()
            branch_number = str(payment.get("branch_number") or "").strip()
            account_number = str(payment.get("account_number") or "").strip()
            if not (check_number and bank_number and branch_number and account_number):
                raise ValueError("בתשלום בצ׳ק צריך למלא מספר צ׳ק, בנק, סניף ומספר חשבון.")
            check_number = re.sub(r"\D+", "", check_number)
            bank_number = re.sub(r"\D+", "", bank_number)
            branch_number = re.sub(r"\D+", "", branch_number)
            account_number = re.sub(r"[^\dA-Za-z-]", "", account_number)
            return {
                **base_row,
                "type": 2,
                "name": "צ'ק",
                "description": (
                    f"מס' צ'ק {check_number} / בנק {bank_number} / "
                    f"סניף {branch_number} / מס' חשבון {account_number}"
                ),
                "chequeNum": check_number,
                "bankName": bank_number,
                "bankBranch": branch_number,
                "bankAccount": account_number,
            }

        raise ValueError("אופן התשלום שנבחר לא נתמך.")

    def _build_receipt_withholding_row(self, withholding: dict, payment_date: str) -> dict | None:
        if not isinstance(withholding, dict) or not bool(withholding.get("applied")):
            return None
        amount = round(float(withholding.get("withheld_amount") or 0), 2)
        percent = round(float(withholding.get("percent") or 0), 2)
        if amount <= 0:
            return None
        description = "ניכוי במקור"
        if percent > 0:
            description = f"ניכוי במקור {percent:.2f}%"
        return {
            "amount": amount,
            "price": amount,
            "currency": "ILS",
            "date": payment_date,
            "ref": [],
            "type": 5,
            "name": "ניכוי במקור",
            "description": description,
        }

    async def create_receipt_for_invoice(self, invoice: dict, payment: dict, withholding: dict | None = None):
        token = await self._get_token()
        invoice_id = str(invoice.get("id") or "").strip()
        invoice_number = str(invoice.get("number") or "").strip()

        if not invoice_id:
            raise ValueError("חסר מזהה חשבונית ליצירת קבלה.")

        client_payload = {}
        if invoice.get("client_id"):
            client_payload["id"] = invoice.get("client_id")
        else:
            if invoice.get("customer_name"):
                client_payload["name"] = invoice.get("customer_name")
            if invoice.get("customer_id"):
                client_payload["idNumber"] = invoice.get("customer_id")

        payment_date = str(payment.get("payment_date") or date.today().isoformat()).strip()
        payment_rows = [self._build_receipt_payment_row(payment)]
        withholding_row = self._build_receipt_withholding_row(withholding or {}, payment_date)
        if withholding_row:
            payment_rows.append(withholding_row)

        payload = {
            "type": 400,
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": client_payload,
            "description": f"קבלה עבור חשבונית מס {invoice_number}",
            "remarks": (payment.get("notes") or "").strip(),
            "linkedDocumentIds": [invoice_id],
            "payment": payment_rows,
        }

        receipt = await self.create_document(token, payload)
        return {
            "receipt_id": receipt.document_id,
            "receipt_number": str(receipt.number or ""),
            "raw": receipt.raw,
        }

    async def list_receipt_numbers_by_invoice_numbers(
        self,
        invoice_numbers: list[str],
        date_from: str,
        date_to: str,
        page_size: int = 100,
        max_pages: int = 80,
    ) -> dict[str, str]:
        wanted = {str(number or "").strip() for number in invoice_numbers if str(number or "").strip()}
        if not wanted:
            return {}

        documents = await self.get_income_documents(
            date_from=date_from,
            date_to=date_to,
            page_size=page_size,
            max_pages=max_pages,
        )
        receipt_map: dict[str, str] = {}

        for doc in documents:
            type_code = str(doc.get("type_code") or "").strip()
            type_text = str(doc.get("type") or "").strip().lower()
            if type_code != "400" and "קבלה" not in type_text and "receipt" not in type_text:
                continue

            raw = doc.get("raw") or {}
            description = str(raw.get("description") or "").strip()
            remarks = str(raw.get("remarks") or "").strip()
            receipt_number = str(doc.get("number") or "").strip()
            if not receipt_number:
                continue

            linked_numbers = _extract_receipt_invoice_numbers(description)
            if not linked_numbers:
                linked_numbers = _extract_receipt_invoice_numbers(remarks)
            if not linked_numbers:
                continue

            for linked_number in linked_numbers:
                if linked_number in wanted:
                    receipt_map[linked_number] = receipt_number

        return receipt_map

    async def list_receipt_links(
        self,
        date_from: str,
        date_to: str,
        page_size: int = 100,
        max_pages: int = 80,
    ) -> list[dict]:
        documents = await self.get_income_documents(
            date_from=date_from,
            date_to=date_to,
            page_size=page_size,
            max_pages=max_pages,
        )
        links: list[dict] = []

        for doc in documents:
            type_code = str(doc.get("type_code") or "").strip()
            type_text = str(doc.get("type") or "").strip().lower()
            if type_code != "400" and "קבלה" not in type_text and "receipt" not in type_text:
                continue

            raw = doc.get("raw") or {}
            description = str(raw.get("description") or "").strip()
            remarks = str(raw.get("remarks") or "").strip()
            linked_numbers = _extract_receipt_invoice_numbers(description)
            if not linked_numbers:
                linked_numbers = _extract_receipt_invoice_numbers(remarks)
            if not linked_numbers:
                linked_numbers = [""]

            for linked_number in linked_numbers:
                links.append(
                    {
                        "receipt_number": str(doc.get("number") or "").strip(),
                        "customer_name": _normalize_income_customer_name(doc.get("customer_name") or ""),
                        "customer_id": _normalize_income_customer_id(doc.get("customer_id") or ""),
                        "amount": round(float(doc.get("amount") or 0), 2),
                        "document_date": str(doc.get("date") or "").strip(),
                        "description": description,
                        "remarks": remarks,
                        "linked_invoice_number": linked_number,
                        "linked_po_number": _extract_po_number(description),
                    }
                )

        return links
