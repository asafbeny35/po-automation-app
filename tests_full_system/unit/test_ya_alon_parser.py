from services.parsers.ya_alon import parse


RAW_TEXT = """ימרכ רה לאימרכ | PO79486 סמ שכר תנמזה
"הינב ןולא א.י" :םש לע תינובשח
זעוב /ןדריה רהנ 'חר
ליטסקט תונורתפ בקעי ןב דובכל הינב ןולא א.י הרבחה םש רמתיא 0546518168 חולשמל תבותכ
052-4277427
037017779 פ.ח 512879172 פ.ח 21.6.2026 הקפסה ךיראת
תילתע ,34 ןרוגה קפסה תבותכ ץיבוקסומ לייגיבא ןימזמה םש וסור יקושהריסמל רשק שיא
3032434
0547720142 ןופלט 0522229736 ןופלט 0538517424 ןופלט
ריחמ כ”הס החנה הדיחיל ריחמ תומכ הדימ תדיחי רצומ גוס רצומ הנומת
₪ 3,030 0% ₪ 101 30 'חי תלדל הנגה יוסיכ תורגסמ תותלדל תינוגימ
הנקתה + הקפסא :תורעה
₪ 290 0% ₪ 290 1 הדיחי הלבוה הלבוה
₪ 3,917.6 :ריחמ כ”הס ₪ 597.6 :מ”עמ 18.0% 0% :תיללכ החנה ₪ 3,320 :מ”עמ ינפל םוכס 2 :םיטירפ כ”הס
לארשי ,םי לילג ,מ”עב היצקילפא טקנופ
support@punct.co.il
"""


def test_ya_alon_parser_extracts_core_fields():
    result = parse(RAW_TEXT)
    assert result is not None

    customer_name, items, header = result
    assert customer_name == "י.א אלון בניה"
    assert header["customer_id"] == "512879172"
    assert header["po_number"] == "PO79486"
    assert header["po_date"] == "21/6/2026"
    assert header["project"] == "כרמיאל הר כרמי"
    assert header["delivery_address"] == "רח' נהר הירדן/בועז, כרמיאל הר כרמי"
    assert header["contact_name"] == "שוקי רוסו"
    assert header["contact_phone"] == "0538517424"
    assert header["subtotal"] == 3320.0
    assert header["vat"] == 597.6
    assert header["total"] == 3917.6
    assert len(items) == 2
    assert items[0].description == "מיגונית לדלתות מסגרות - כיסוי הגנה לדלת"
    assert items[0].quantity == 30.0
    assert items[0].unit_price == 101.0
    assert items[0].line_total == 3030.0
    assert items[0].unit == "יח'"
    assert items[1].description == "הובלה"
    assert items[1].quantity == 1.0
    assert items[1].unit_price == 290.0
    assert items[1].line_total == 290.0
