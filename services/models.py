from pydantic import BaseModel
from typing import List, Optional


class POItem(BaseModel):
    description: str = ""
    quantity: float = 0
    unit_price: float = 0
    line_total: float = 0
    sku: str = ""
    unit: str = ""
    generate_label: Optional[bool] = None


class PurchaseOrderData(BaseModel):
    po_number: str = ""
    po_date: str = ""
    customer_name: str = ""
    customer_id: str = ""
    customer_email: str = ""
    customer_phone: str = ""

    delivery_address: str = ""
    project: str = ""

    contact_name: str = ""
    contact_phone: str = ""

    subtotal: float = 0
    vat: float = 0
    total: float = 0

    payment_terms_days: Optional[int] = None
    payment_terms_label: str = ""

    items: List[POItem] = []

    raw_text: str = ""
    extra: dict = {}
