from services.parsers.shponder_pedlon import parse


RAW_TEXT = """פדלון שפונדר ביצוע בע\"מ
מאיר אריאל 4 מתחם עסקים גראנד נטר
נתניה
כתובת למשלוח דואר : הלוחמים ,9 אבן יהודה ת.ד 1406
09-8996263
09-8996258
פקס:
טלפון:
ח.פ516087269 :
לכבוד:
תאריך הזמנה:
22/06/2026
בן יעקב פתרונות טקסטיל
תאריך עדכון:
22/06/2026
גירסת מסמך:
2
פקס:
טלפון:
לידי:
הזמנת רכש מס14458:
נבקשכם לספק עבורינו את הפריטים המפורטים להלן במועדי האספקה המופיעים מטה
פרויקט : בניה רויה - גלריה אבן יהודה
כתובת פרויקט:
הרימון 3 אבן יהודה,
לידי : אייל בנימינוב 052-4679037
קוד פריט/
מק\"ט
תיאור פריט/
הערות
כמות
י.מ.
ת. אספקה
מחיר יח'/
אחוז הנחה
סה\"כ לשורה
1
150-0294
כיסוי להגנת דלתות 236/89 ס\"מ
יש לוודא את המידות טרם שליחת הכיסויים הגנת
דלתות לבקשת סמי
36.00
יח'
21/06/2026
₪76.00
2,736.00
2
123-0063
עבודה
36.00
יח'
21/06/2026
₪22.00
792.00
תנאי תשלום : שוטף 90+
הערות למסמך : ע\"ס בקשת רכש 4990
אושר עי עידו
סה\"כ חייב במע\"מ:
מע\"מ:
%
3,528.00
18.00
635.04
סה\"כ מסמך:
4,163.04
יש לצרף הזמנה זו ותעודת משלוח חתומה על ידי אחד מעובדי החברה ,שם מלא וחתימה.
בכבוד רב,
חמוטל פרץ
Hamutal.p@sf-group.co.il
פדלון שפונדר ביצוע בע\"מ"""

OCR_TEXT = """פדלון שפונדר ביצוע בע"מ

מאיר אריאל 4 מתחם עסקים גראנד נטר

נתניה

כתובת למשלוח דואר: הלוחמים 9, אבן יהודה ת.ד 1406
טלפון: 8" פקס: 09-8996263
ח.פ: | 516087269

לכבוד: תאריך הזמנה: 22/06/2026
בן יעקב פתרונות טקסטיל תאריך עדכון: 22/06/2026
טלפון: פקס: גירסת מסמך: 2
לידי:
הזמנת רכש מ0ס:14458
נבקשכם לספק עבורינו את הפריטים המפורטים להלן במועדי האספקה המופיעים מטה
פרויקט: בניה רויה - גלריה אבן יהודה לידי: | אייל בנימינוב, 052-4679037
כתובת פרויקט: | הרימון 3 אבן יהודה,
קוד פריט/ תיאור פריט/ כמות י.מ. ת. אספקה מחיר יח'/ סה"כ לשורה
מק"ט הערות אחוז הנחה
1 150-0294 כיסוי להגנת דלתות 236/89 ס"מ 36.00 יח 21/06/2026 ₪76.00 2,736.00
יש לוודא את המידות טרם שליחת הכיסויים הגנת
דלתות לבקשת סמי
2 123-0063 עבודה 36.00 יח 21/06/2026 ₪22.00 792.00
תנאי תשלום: | שוטף +90 סה"כ חייב במע"מ: 3,528.00
הערות למסמך: | ע"ס בקשת רכש 4990 מע"מ: % 18.00 635.04
אושר עי עידו
סה"כ מסמך: 4,163.04
יש לצרף הזמנה זו ותעודת משלוח חתומה על ידי אחד מעובדי החברה, שם מלא וחתימה.
בכבוד רב,
חמוטל פרץ
Hamutal.p@sf-group.co. il
פדלון שפונדר ביצוע בע"מ"""


def test_shponder_pedlon_parser_extracts_core_fields():
    result = parse(RAW_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == 'פדלון שפונדר ביצוע בע"מ'
    assert header["customer_id"] == "516087269"
    assert header["po_number"] == "14458"
    assert header["po_date"] == "22/06/2026"
    assert header["project"] == "בניה רויה - גלריה אבן יהודה"
    assert header["delivery_address"] == "הרימון 3 אבן יהודה,"
    assert header["contact_name"] == "אייל בנימינוב"
    assert header["contact_phone"] == "052-4679037"
    assert header["customer_phone"] == "09-8996263"
    assert header["customer_email"] == "Hamutal.p@sf-group.co.il"
    assert header["payment_terms_days"] == 90
    assert header["payment_terms_label"] == "שוטף + 90"
    assert header["subtotal"] == 3528.0
    assert header["vat"] == 635.04
    assert header["total"] == 4163.04
    assert "4990" in header["extra"]["order_notes"]
    assert "אושר עי עידו" in header["extra"]["order_notes"]
    assert len(items) == 2

    assert items[0].sku == "150-0294"
    assert items[0].description == "כיסוי להגנת דלתות 236/89 ס\"מ יש לוודא את המידות טרם שליחת הכיסויים הגנת דלתות לבקשת סמי"
    assert items[0].quantity == 36.0
    assert items[0].unit == "יח'"
    assert items[0].unit_price == 76.0
    assert items[0].line_total == 2736.0

    assert items[1].sku == "123-0063"
    assert items[1].description == "עבודה"
    assert items[1].quantity == 36.0
    assert items[1].unit == "יח'"
    assert items[1].unit_price == 22.0
    assert items[1].line_total == 792.0


def test_shponder_pedlon_parser_handles_ocr_text():
    result = parse(OCR_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == 'פדלון שפונדר ביצוע בע"מ'
    assert header["customer_id"] == "516087269"
    assert header["po_number"] == "14458"
    assert header["po_date"] == "22/06/2026"
    assert header["project"] == "בניה רויה - גלריה אבן יהודה"
    assert header["delivery_address"] == "הרימון 3 אבן יהודה,"
    assert header["contact_name"] == "אייל בנימינוב"
    assert header["contact_phone"] == "052-4679037"
    assert header["customer_email"] == "Hamutal.p@sf-group.co.il"
    assert header["payment_terms_days"] == 90
    assert header["subtotal"] == 3528.0
    assert header["vat"] == 635.04
    assert header["total"] == 4163.04
    assert len(items) == 2
    assert items[0].sku == "150-0294"
    assert items[1].sku == "123-0063"
