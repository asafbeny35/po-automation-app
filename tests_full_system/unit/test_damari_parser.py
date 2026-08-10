from services.parsers.damari import parse


RAW_TEXT = """מ"עב חותיפו הינב ירמד .ח.י
115750 שכר תנמזה 054-7720142
10/08/2026 :הנמזה ךיראת
'חי
לכה ךס ריחמ תומכ טירפ רואית טירפ דוק
הדימ
2,584.00 38.0000 68.00 'חי דב + ךותיח - תלדל הנגה ןוקית- הנקתה ללוכ תלדל הנגה 17479
הרצ ףנכ לע ךרוא
780.00 390.0000 2.00 'חי - הלבוה 44065
3,364.00 מ"עמו החנה ינפל כ"הס
605.52 18.00 % מ"עמ
3,969.52
מ"עמ ללוכ כ"הס"""


def test_damari_parser_extracts_standard_columns_and_wrapped_description():
    result = parse(RAW_TEXT)
    assert result is not None

    _, items, header = result
    assert header["po_number"] == "115750"
    assert header["subtotal"] == 3364.0
    assert header["vat"] == 605.52
    assert header["total"] == 3969.52
    assert len(items) == 2

    assert items[0].sku == "17479"
    assert items[0].description == (
        "הגנה לדלת כולל התקנה - תיקון הגנה לדלת - חיתוך + בד אורך על כנף צרה"
    )
    assert items[0].quantity == 68.0
    assert items[0].unit_price == 38.0
    assert items[0].line_total == 2584.0

    assert items[1].sku == "44065"
    assert items[1].description == "הובלה"
    assert items[1].quantity == 2.0
    assert items[1].unit_price == 390.0
    assert items[1].line_total == 780.0
