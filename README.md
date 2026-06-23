# PO Automation App for macOS

אפליקציית ווב מקומית שמבצעת את הזרימה הבאה:
1. העלאת PDF של הזמנת רכש.
2. חילוץ נתונים בסיסיים מה-PDF.
3. יצירת תעודת משלוח ב-Morning / חשבונית ירוקה.
4. יצירת חשבונית מס.
5. הוספת שורה חדשה לגוגל שיטס.
6. שליחת שני ה-PDF-ים דרך WhatsApp Web.

## מה חשוב לדעת מראש
- חילוץ אוטומטי מ-PDF לא יהיה מושלם לכל פורמט של הזמנת רכש. אם כל ה-PDFים שלך נראים דומה, אפשר לכוונן את `services/po_parser.py` פעם אחת ולהגיע לדיוק טוב.
- החלק של WhatsApp Web מבוסס על אוטומציית דפדפן, לא על API רשמי של חשבון ווטסאפ אישי. לכן הוא יותר שביר משאר השלבים.
- בשלב Green Invoice ייתכן שתצטרך לעדכן פעם אחת את שמות השדות ב-payload לפי החשבון והמסמכים שלך.

## התקנה
```bash
cd po_automation_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## קבצים שתצטרך להוסיף
### 1) Google Service Account
שמור קובץ service account בשם:
```bash
google-service-account.json
```
תן למייל של ה-service account הרשאת עריכה על ה-Google Sheet.

### 2) .env
מלא את כל הערכים ב-`.env`.

## הרצה
```bash
uvicorn app:app --reload
```
ואז פתח:
```bash
http://127.0.0.1:8000
```

## מבנה שדות בשיטס
השורה הראשונה ב-sheet צריכה להכיל כותרות. ברירת המחדל היא:
- Timestamp
- PO Number
- PO Date
- Customer Name
- Customer ID
- Customer Email
- Customer Phone
- Delivery Address
- Subtotal
- VAT
- Total
- Items Count
- GreenInvoice Delivery ID
- GreenInvoice Invoice ID
- Source PDF

אפשר לשנות את הרשימה דרך `GOOGLE_SHEETS_HEADERS`.

## התאמות שכדאי לעשות אצלך
### parser
אם הזמנות הרכש שלך קבועות בפורמט, תעדכן regex-ים ב:
- `services/po_parser.py`

### Green Invoice payload
אם ה-API אצלך מצפה למבנה מעט שונה, תעדכן:
- `services/greeninvoice.py`

### WhatsApp recipient
תעדכן את:
- `WHATSAPP_RECIPIENT`

בפורמט בינלאומי, למשל `9725XXXXXXXX`.

## שדרוג מומלץ
לפני יצירת המסמכים בפועל, כדאי להוסיף מסך ביניים שבו הנתונים שחולצו מה-PDF מוצגים לעריכה ידנית ואישור. זה יחסוך טעויות בהפקת מסמכים חשבונאיים.
