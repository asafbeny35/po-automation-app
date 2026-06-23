# PO Automation App – Project Context

## מהות הפרויקט
אפליקציית אוטומציה להזמנות רכש בתחום הבנייה.

מטרה:
העלאת PDF של הזמנת רכש → חילוץ נתונים → הצגה בטופס → תיקון ידני → יצירת תעודת משלוח וחשבונית דרך Green Invoice → שמירת קבצים → יצירת PDF מאוחד → שליחה ב-WhatsApp → עדכון Google Sheets.

---

## סטאק טכנולוגי

Backend:
- Python 3.11
- FastAPI

Frontend:
- HTML + JavaScript

Parsing:
- pdfplumber
- parsers ייעודיים לפי לקוח

APIs / Services:
- Green Invoice API
- Google Sheets API
- WhatsApp Web automation עם Playwright

PDF:
- ReportLab
- PyPDF2

---

## מבנה פרויקט

### app.py
Endpoints:
- `/process`
- `/finalize`

### services/
- `po_parser.py`  
  נקודת הכניסה הראשית ל-parsing

- `parsers/registry.py`  
  מנהל את רשימת ה-parsers

- `parsers/yuval_alon.py`  
  parser עובד לדוגמה עבור יובל אלון

- `models.py`  
  כולל:
  - `PurchaseOrderData`
  - `POItem`

- `google_sheets.py`
- `greeninvoice.py`
- `whatsapp_web.py`
- `label_generator_v4.py`
- `pdf_utils.py`
- `logger_utils.py`

### templates/
- `index.html`

---

## Flow של המערכת

1. העלאת PDF
2. חילוץ טקסט מה-PDF
3. parse_purchase_order()
4. ניסיון parser חדש דרך registry
5. אם אין התאמה → fallback ישן
6. החזרת PurchaseOrderData
7. הצגה בטופס frontend
8. המשתמש עורך אם צריך
9. finalize:
   - יצירת תעודת משלוח
   - יצירת חשבונית
   - יצירת מדבקה
   - שמירת קבצים בתיקייה
   - יצירת merged PDF
   - שליחה ב-WhatsApp
   - כתיבה ל-Google Sheets

---

## חוקים עסקיים קריטיים

- לא יוצרים לקוח חדש ב-Green Invoice
- עובדים רק עם לקוח קיים לפי ח.פ
- תנאי תשלום תמיד נלקחים מ-Green Invoice
- כתובת אספקה + איש קשר תמיד נלקחים מה-PDF
- WhatsApp שולח רק merged PDF
- Google Sheets חייב להתעדכן תמיד אחרי יצירת המסמכים

---

## קבצים שנוצרים

- delivery.pdf
- invoice.pdf
- label.pdf
- העתק של הזמנת הרכש המקורית
- merged.pdf

### merged.pdf חייב לכלול בדיוק:
1. תעודת משלוח
2. תעודת משלוח שוב
3. מדבקה

ולא לכלול:
- invoice
- PO

---

## מודלים חשובים

### POItem
שדות:
- description
- quantity
- unit_price
- line_total
- sku

### PurchaseOrderData
שדות:
- po_number
- po_date
- customer_name
- customer_id
- customer_email
- customer_phone
- delivery_address
- subtotal
- vat
- total
- payment_terms_days
- payment_terms_label
- items
- raw_text
- extra

---

## חוזה parser חדש

כל parser חדש צריך להחזיר dict במבנה הזה:

{
  "customer_name": "",
  "customer_id": "",
  "customer_phone": "",
  "customer_email": "",
  "delivery_address": "",
  "po_number": "",
  "po_date": "",
  "subtotal": 0.0,
  "vat": 0.0,
  "total": 0.0,
  "items": [
    {
      "description": "",
      "quantity": 0,
      "unit_price": 0,
      "line_total": 0,
      "sku": ""
    }
  ],
  "extra": {
    "project": "",
    "contact_name": "",
    "contact_phone": "",
    "footer_text": ""
  }
}

---

## מצב נוכחי

- parser של יובל אלון עובד תקין
- extraction של:
  - כתובת אספקה
  - איש קשר
  - טלפון איש קשר
  - טלפון לקוח
  - תיאור מוצר
  - סכומים
  תקין במסמך של יובל אלון

- יש registry לפרסרים
- יש fallback parser
- יש logging

---

## דגשים חשובים לעבודה על הפרויקט

- לא לשבור parser קיים שעובד
- לא להחליף parser ישן בלי fallback
- כשיש תיקון ללקוח מסוים, עדיף parser ייעודי
- יש להעדיף פקודות מוכנות להרצה בטרמינל
- יש להחזיר קוד מלא להדבקה כשמבקשים שינוי
- יש לשמור על יציבות לפני “שיפורים יפים”

---

## איך לענות בפרויקט הזה

תענה כמו מפתח סיניור:
- קצר
- מדויק
- עם פקודות הרצה
- עם קוד מלא
- בלי חפירות
- בלי לשבור מה שעובד