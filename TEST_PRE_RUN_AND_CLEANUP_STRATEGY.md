# אסטרטגיית Pre-Run ו־Cleanup לסוויטת הבדיקות

## מטרת המסמך
המסמך הזה מגדיר איך מריצים את סוויטת הבדיקות של המערכת בצורה בטוחה, מדורגת ונקייה, כך שלא ניצור נזק או בלגן מיותר ב־UI, ב־Sheets, ב־Drive, ב־WhatsApp, ב־Gmail או ב־GreenInvoice Sandbox.

המסמך הזה משלים את:
- [/Users/asafbeny/Downloads/po_automation_app/TEST_PLAN_FULL_SYSTEM.md](/Users/asafbeny/Downloads/po_automation_app/TEST_PLAN_FULL_SYSTEM.md)

## עקרונות בטיחות קשיחים
- כל בדיקת יצירה רצה רק ב־`Sandbox`.
- לעולם לא יוצרים מסמכים ב־`GreenInvoice PROD`.
- כל `WhatsApp` נשלח אך ורק ל־`0547720142`.
- כל ישות טסט חייבת להכיל גם:
  - תגית `TEST`
  - וגם את השם `נעלולי פלא`
- אם נוצרה ישות בלי אחד משני הסימונים האלה:
  - זה נחשב כשל בדיקה חמור
  - ויש לעצור את הריצה ולחקור

## מה חייב להיות מוכן לפני ריצה
### שרת
- השרת המקומי חייב להיות זמין:
  - `http://localhost:8000`
- אין חובה "להוריד UI".
- עדיף שהשרת יהיה במצב יציב, בלי הפעלות מחדש תוך כדי ריצה.

### חיבורים ואינטגרציות
- `Gmail OAuth` מחובר ותקין
- `Google Drive` מחובר
- `Google Sheets` מחובר
- `WhatsApp Web` מחובר
- `GreenInvoice Sandbox` תקין

### קבצי בדיקות
- dependencies של הבדיקות מותקנות
- state לדפדפן הבדיקות מוכן
- אין שינויים לא שמורים בתיקיית:
  - [/Users/asafbeny/Downloads/po_automation_app/tests_full_system](/Users/asafbeny/Downloads/po_automation_app/tests_full_system)

## Checklist לפני ריצה ראשונה
### 1. אימות סביבת בדיקות
- לוודא ש־`PO_TEST_GREENINVOICE_MODE=sandbox`
- לוודא ש־`PO_TEST_ALLOW_PROD=false`
- לוודא ש־`PO_TEST_WHATSAPP_NUMBER=0547720142`
- לוודא שקיים browser storage state אם מריצים `E2E`

### 2. אימות guardrails
- לוודא שכל builders של יצירה מייצרים:
  - `TEST`
  - `נעלולי פלא`
- לוודא ש־payloads ידניים בבדיקות API לא משתמשים בשמות "רגילים"

### 3. אימות סביבות חיצוניות
- לוודא שאין חלון `WhatsApp` תקוע במודאל לא סגור
- לוודא שאין חלון system file picker פתוח
- לוודא ש־Gmail/Drive מחוברים עם החשבונות הנכונים

### 4. snapshot מקדים
לפני הרצה ראשונה מומלץ לשמור snapshot או תיעוד של:
- מספר שורות בהיסטוריות עיקריות
- תיקיות Drive הרלוונטיות
- מצב `Sandbox` ב־GreenInvoice
- מצב `localStorage` אם רוצים להשוות אחרי הריצה

## סדר הרצה מומלץ
### שלב 1. בדיקות בטוחות בלבד
- `unit`
- בדיקות manifests
- route smoke
- compile/syntax

מטרה:
- לזהות שגיאות מבניות בלי לגעת בדאטה

### שלב 2. API read-only / low-risk
- `GET` routes
- `state`
- `refresh` שלא יוצר רשומות
- `resolve`
- `prepare`

מטרה:
- לוודא שהשרת מגיב, שהקונטרקטים חיים, ושהאינטגרציות לא נופלות מייד

### שלב 3. UI surface / read-only E2E
- פתיחת טאבים
- פתיחת מודאלים
- בדיקת נראות
- בדיקת progress bars
- בדיקת labels / filters / toggles / states

מטרה:
- לזהות regressions ב־UI בלי ליצור ישויות

### שלב 4. API create / update ב־Sandbox
- יצירות בטוחות
- עדכונים עם ישויות `TEST | נעלולי פלא`
- בלי שליחות, אם אפשר

מטרה:
- לזהות כשלים של persistence וסנכרון

### שלב 5. E2E create ב־Sandbox
- flows של יצירה
- flows של save / history / drive sync
- בלי פתיחה רחבה של שליחות עדיין

### שלב 6. שליחות טסט
- Gmail test sends
- WhatsApp test sends ל־`0547720142` בלבד

מטרה:
- לבדוק את קצה האינטגרציה רק אחרי שכל השאר יציב

## מתי עוצרים מייד
- אם מתגלה ניסיון יצירה ב־`PROD`
- אם מתגלה target WhatsApp שונה מ־`0547720142`
- אם נוצרת ישות בלי `TEST`
- אם נוצרת ישות בלי `נעלולי פלא`
- אם בדיקה מוחקת ישות שלא מסומנת כטסט
- אם נוצרות כפילויות לא צפויות בלי מזהי טסט
- אם שליחה אמיתית כמעט נשלחה ליעד לא נכון

## מה עלול להתלכלך בזמן ריצה
### Google Sheets
- היסטוריות
- טבלאות ביניים
- שורות sandbox
- שורות `TEST | נעלולי פלא`

### Google Drive
- תיקיות טסט
- קבצי PDF / ZIP / XLSX
- attachments
- קבצי split / export

### WhatsApp
- הודעות טסט
- קבצים מצורפים

### Gmail
- מיילי טסט
- attachments

### output מקומי
- קבצי PDF
- ZIP
- XLSX
- cache

### GreenInvoice Sandbox
- חשבוניות / תעודות / הצעות / קבלות טסט

### UI / Browser
- localStorage
- session state
- collapse/filter/sort state
- קבצי artifacts / screenshots

## Cleanup אוטומטי - מה צריך למחוק
### כלי ה־cleanup בפועל
סקריפט ה־cleanup של סוויטת הבדיקות נמצא כאן:
- [/Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py](/Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py)

פקודות שימוש:
- `dry-run` בלבד, בלי למחוק כלום:
  - `python /Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py`
- ניקוי בפועל:
  - `python /Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py --apply`
- שמירת דוח JSON:
  - `python /Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py --report-json /tmp/po-test-cleanup-report.json`

### 1. שורות שיט
למחוק כל שורה שמכילה אחד מהבאים:
- `TEST`
- `נעלולי פלא`
- `TEST-`
- `TEST-SKU`
- מזהי ריצה אם נוסיף בעתיד `test_run_id`

### 2. תיקיות וקבצים ב־Drive
למחוק:
- תיקיות עם `TEST`
- תיקיות עם `נעלולי פלא`
- קבצים עם `TEST`
- קבצים עם `נעלולי פלא`

### 3. output מקומי
למחוק:
- תיקיות output של sandbox test
- exports
- temporary split files
- delivery/invoice caches

### 4. browser state
- לנקות localStorage של הבדיקות
- לנקות screenshots/artifacts זמניים אם לא צריך לשמור evidence

### 5. GreenInvoice Sandbox
- לאתר מסמכי `TEST | נעלולי פלא`
- למחוק או לבטל לפי סוג המסמך

## Cleanup חלקי מול מלא
### Cleanup חלקי
מתאים כש:
- רוצים לשמור evidence
- רוצים להשאיר artifacts לניתוח
- רוצים להשאיר הודעות WhatsApp / emails כהוכחת הרצה

### Cleanup מלא
מתאים כש:
- הסתיים סבב
- רוצים סביבת sandbox נקייה
- לפני ריצה רחבה נוספת

## מה לא ניתן לנקות אוטומטית בקלות
- הודעות WhatsApp שכבר נשלחו
- מיילים שכבר נשלחו
- פעולות אנושיות שנעשו ידנית תוך כדי
- רשומות ישנות שנוצרו בלי סימון טוב לפני החמרת הכללים

## מדיניות Naming מחייבת
כל יצירה חדשה תשתמש בפורמט דומה לזה:
- `TEST | נעלולי פלא 1 | לקוח`
- `TEST | נעלולי פלא 2 | מוצר`
- `TEST | נעלולי פלא 3 | שירות`

ובשדות מזהים נוספים, אם יש:
- `po_number`: `TEST-YYYYMMDD-001`
- `sku`: `TEST-SKU-001`
- `subject`: `TEST | נעלולי פלא | ...`

## המלצה אופרטיבית להרצה ראשונה
1. להריץ קודם `unit + manifest + route smoke`
2. אחר כך `UI surface`
3. אחר כך `API create sandbox`
4. אחר כך `E2E sandbox create`
5. ורק לבסוף `Gmail/WhatsApp test send`

## Definition of Done לסבב הרצה
סבב בדיקות נחשב "סגור" רק אם:
- כל failures נסקרו
- כל ישויות `TEST | נעלולי פלא` אותרו
- cleanup בוצע או תועד במפורש
- אין שאריות לא מזוהות ב־Sheets / Drive / Sandbox
- אין שום יצירה או שליחה שיצאה בטעות ל־`PROD`

## הערה אחרונה
המטרה של המסמך הזה היא לא רק "להריץ בדיקות", אלא לאפשר הרצה בטוחה, נשלטת, הפיכה ככל האפשר, ועם traceability מלא לכל מה שהבדיקות נגעו בו.
