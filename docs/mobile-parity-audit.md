# BenYacovMobile Parity Audit

תאריך: 2026-06-19

מטרת המסמך: לבדוק מול `po_automation_app` הדסקטופי אילו יכולות כבר זמינות ב־`BenYacovMobile`, ואיך הן נגישות מתוך האפליקציה.

## עיקרון הבדיקה

פיצ'ר נחשב "מכוסה" אם מתקיים אחד מאלה:

1. יש לו מסך native ייעודי באייפון.
2. יש לו מסלול פעולה נגיש מתוך `NativeOperationsHubView` עם טופס/הפעלה native.
3. יש לו API מחובר בפועל דרך `AppSession` ונקודת כניסה באפליקציה.

## מטריצת כיסוי

### הזמנות

- הזמנות בעבודה: קיים במסך `OrdersView`.
- היסטוריית הזמנות: נגישה דרך `NativeOperationsHubView` בקבוצת `documents`.
- היסטוריית הצעות מחיר: נגישה דרך `NativeOperationsHubView` בקבוצת `documents`.
- יצירת הזמנה ידנית / פרסור PDF / finalize: קיים ב־`OrderComposerView`.
- אישורי מסירה: קיים במסך `OrdersView`.
- פעולות השלמה להזמנות, הצעות, אישורי מסירה ותבניות אחרונות: נגישות דרך קיצורי "פעולות משלימות" ב־`OrdersView` אל `documents` ו־`communications`.

### תשלומים והעברות

- טבלת הכל / לגבייה / לתשלום: קיים ב־`PaymentsTransferWorkspaceView`.
- יצירת שורה: מחובר דרך `AppSession`.
- עדכון שורה: מחובר דרך `AppSession`.
- סימון שולם / לא שולם: מחובר דרך `AppSession`.
- מחיקת שורה: מחובר דרך `AppSession`.
- פעולות refresh / edit lock: קיימות ב־backend ומכוסות ב־state וב־operations.

### כספים

- חשבוניות: קיים ב־`FinanceView`.
- ניכויי מס במקור: קיים ב־`FinanceView`.
- תנועות בנק: קיים ב־`FinanceView`.
- העלאת חשבונית, review draft ושמירה: קיים ב־`FinanceView`.
- export / email של דיווחים: קיים ב־`FinanceView`.
- פתיחת קובץ חשבונית: קיים ב־`FinanceView`.
- פעולות כספים נוספות כמו מחיקה מרובה, override due dates, יצירת קבלה, settings, import ניכויים: נגישות דרך קיצור "מרכז פעולות כספים".
- פעולות קבצים/Drive/מסמכים משלימות: נגישות דרך קיצור "קבצים, ייצואים ומסמכים".

### לקוחות

- חיפוש וסקירת לקוחות: קיים ב־`CustomersView`.
- לקוחות לא פעילים: קיים ב־`InactiveCustomersModuleView`.
- רענון לקוחות, רענון מ־Drive, יצירה, עדכון, מחיקה, שיוך תחום, הפעלה/השבתה, שליחת מייל: נגישים מתוך `NativeOperationsHubView` בקבוצת `customers`.
- החל מהסבב הזה: נוספו קיצורי כניסה ישירים ממסך `CustomersView` לפעולות לקוחות וללקוחות לא פעילים.

### שיווק

- pipeline: קיים ב־`MarketingCenterModuleView`.
- מסמכי שיווק: קיים ב־`MarketingCenterModuleView`.
- reminders: קיים ב־`MarketingCenterModuleView`.
- construction companies: קיים ב־`MarketingCenterModuleView`.
- work managers: קיים ב־`MarketingCenterModuleView`.
- quote update / create updated quote / email / whatsapp / pricing import-export: קיים ב־`MarketingCenterModuleView` וב־`AppSession`.

### מלאי ותמחור

- מלאי גולמי: קיים ב־`InventoryCenterModuleView`.
- מלאי גמר: קיים ב־`InventoryCenterModuleView`.
- הזמנות רכש ספקים: קיים ב־`InventoryCenterModuleView`.
- תעודות ספק: קיים ב־`InventoryCenterModuleView`.
- restore real stock: קיים ב־`InventoryCenterModuleView`.
- תמחור ועצי מוצר: קיים ב־`PricingCenterModuleView`.
- פעולות מלאי משלימות כמו יצירת הזמנת רכש, delete summary, upload transport label: נגישות דרך `NativeOperationsHubView` בקבוצת `inventory`.

### עובדים ושכר

- עובדים: קיים ב־`HRWorkspaceView`.
- שכר: קיים ב־`HRWorkspaceView`.
- שעות ונוכחות: קיים ב־`HRWorkspaceView`.
- הפרשות: קיים ב־`HRWorkspaceView`.
- מסמכים: קיים ב־`HRWorkspaceView`.
- אישורי מחלה: קיים ב־`HRWorkspaceView`.
- תלושים להפקה / preview / send / history: קיים ב־`HRWorkspaceView` וב־`AppSession`.
- קליטת קבצי HR / upload / export: מכוסים דרך `HRWorkspaceView` ו־`NativeOperationsHubView`.

### מנהלי פרויקטים

- טבלה וטעינת PDF: קיים ב־`ProjectManagersModuleView`.

### מנהלה

- פזומט: קיים ב־`AdminCenterModuleView`.
- סיבוס: קיים ב־`AdminCenterModuleView`.
- פתיחת תיקיות/מסמכים/Drive רלוונטיים: קיים ב־`AdminCenterModuleView` וב־`NativeOperationsHubView`.

### משרד

- רשתות, משתמשים, מחשבון מע״מ, מחשבון מידות, מחשבון קוואיטפייפ: קיים ב־`OfficeModuleView`.

### מרכז תמיכה / פעולות מערכת

- סטטוס מערכת, שגיאות פעילות, פעולות route-level כלליות: קיים ב־`SupportCenterModuleView` וב־`NativeOperationsHubView`.

## פערים שעדיין דורשים הרחבה

אלה לא "לא קיימים", אלא אזורים שבהם הכיסוי כרגע יותר תפעולי/כללי מאשר מסך native ייעודי עמוק:

1. לקוחות: רוב פעולות העריכה/שליחה זמינות כרגע דרך מרכז פעולות הלקוחות, לא דרך כרטיס לקוח מלא.
2. הזמנות: order history / quote history / recent templates נגישים כרגע דרך פעולות משלימות, לא עדיין דרך מסך history ייעודי עשיר כמו בדסקטופ.
3. כספים: חלק מהפעולות החריגות נגישות כרגע דרך מרכז פעולות כספים, לא ככפתור שורה ישיר.

## שינויים שבוצעו בסבב הזה

1. `CustomersView` קיבל קיצורי כניסה ישירים ל:
   - פעולות לקוחות מלאות
   - לקוחות לא פעילים
2. `OrdersView` קיבל קיצורי כניסה ישירים ל:
   - היסטוריה/הצעות/הזמנות עבודה
   - תקשורת ואישורי מסירה
3. `FinanceView` קיבל קיצורי כניסה ישירים ל:
   - מרכז פעולות כספים
   - קבצים, ייצואים ומסמכים
4. `NativeOperationsHubView` נפתח לשימוש חוצה־מסכים עם `initialGroup`.

## המשך עבודה מומלץ

1. להחליף בהדרגה פעולות גנריות בכרטיסי שורה native מלאים.
2. להתחיל בלקוחות ובהיסטוריית הזמנות/הצעות, כי שם עדיין יש תלות יחסית גבוהה ב־Operations Hub.
3. אחרי זה לעבור למסכי כספים החריגים ולסגור parity ברמת "כפתור ישיר לכל שורה".
