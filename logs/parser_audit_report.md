# Parser Audit Report

- Source root: `/Users/asafbeny/Library/Mobile Documents/com~apple~CloudDocs/Downloads/בן יעקב/מדבקות`
- Purchase-order candidates audited: **58**
- Average completeness score: **83.8**

## Parsers

### almogim

- Files: **2**
- Average score: **100.0**
- Weakest examples:
  - `אלמוגים/PO26000537/PO26000537 - הדפסת הזמנת רכש.pdf` · PO26000537 · score 100 · no details
  - `אלמוגים/PO26000800/PO26000800 - הדפסת הזמנת רכש.pdf` · PO26000800 · score 100 · no details

### amram

- Files: **18**
- Average score: **98.4**
- Frequent missing fields: `item_description` × 1, `item_line_total` × 1
- Weakest examples:
  - `עמרם אברהם ביצועים/PO26000447/Print Purchase Order - PO26000447.pdf` · PO26000447 · score 72 · item_description, item_line_total
  - `עמרם אברהם ביצועים/PO25005539/Print Purchase Order - PO25005539.pdf` · PO25005539 · score 100 · no details
  - `עמרם אברהם ביצועים/PO25005548/Print Purchase Order - PO25005548.pdf` · PO25005548 · score 100 · no details
  - `עמרם אברהם ביצועים/PO25005677/Print Purchase Order - PO25005677.pdf` · PO25005677 · score 100 · no details
  - `עמרם אברהם ביצועים/PO25006546/Print Purchase Order - PO25006546.pdf` · PO25006546 · score 100 · no details

### artec

- Files: **3**
- Average score: **88.0**
- Frequent missing fields: `delivery_address` × 3
- Weakest examples:
  - `Artec/HashDoc_115496.pdf` · 115496 · score 88 · delivery_address
  - `Artec/HashDoc_116179.pdf` · 116179 · score 88 · delivery_address
  - `Artec/HashDoc_116385.pdf` · 116385 · score 88 · delivery_address

### brosh

- Files: **6**
- Average score: **100.0**
- Weakest examples:
  - `ברוש/PO25001555‎/הדפסת הזמנת רכש - PO25001555.pdf` · PO25001555 · score 100 · no details
  - `ברוש/PO25001860‎/הדפסת הזמנת רכש - PO25001860.pdf` · PO25001860 · score 100 · no details
  - `ברוש/PO26000069‎/הדפסת הזמנת רכש - PO26000069.pdf` · PO26000069 · score 100 · no details
  - `ברוש/ברוש ניר עבודות הנדסה ובנין בע״מ - PO26000625/הדפסת הזמנת רכש - PO26000625.pdf` · PO26000625 · score 100 · no details
  - `ברוש/ברוש ניר עבודות הנדסה ובנין בע״מ - PO26000648/הדפסת הזמנת רכש - PO26000648.pdf` · PO26000648 · score 100 · no details

### electra_ashtrom

- Files: **3**
- Average score: **100.0**
- Weakest examples:
  - `אשטרום אלקטרה/00405/ddc461f5-71d1-4d42-a3da-c2bc64f256f8.pdf` · PO2535000405 · score 100 · no details
  - `אשטרום אלקטרה/PO2535000543/839f10d2-6a79-4be9-9965-27865aec0162.pdf` · PO2535000543 · score 100 · no details
  - `אשטרום אלקטרה/PO2535000636/057ad725-885d-46a4-8444-871218b7c997.pdf` · PO2535000636 · score 100 · no details

### generic

- Files: **5**
- Average score: **13.2**
- Frequent missing fields: `contact_name` × 5, `contact_phone` × 5, `item_description` × 5, `item_line_total` × 5, `delivery_address` × 4, `customer_name` × 3, `po_date` × 3, `po_number` × 1
- Weakest examples:
  - `קבוצת ימין/001/מפרט מגיני דלתות - אסף.pdf` · 100 · score 0 · customer_name, po_date, customer_id, delivery_address, contact_name, contact_phone, item_description, item_line_total, total
  - `Plasan Reem/52252/450048.pdf` · 25225 · score 1 · customer_name, po_date, delivery_address, contact_name, contact_phone, item_description, item_line_total
  - `Plasan Sasa/4134065/450049.pdf` · 5604314 · score 1 · customer_name, po_date, delivery_address, contact_name, contact_phone, item_description, item_line_total
  - `Plasan Reem/52252/רא״ם 3 גלילים.pdf` · ללא מספר · score 28 · po_number, contact_name, contact_phone, item_description, item_line_total
  - `ירגד פרויקטים בע״מ/בן יעקב - הזמנת רכש.pdf` · 88600062OP · score 36 · delivery_address, contact_name, contact_phone, item_description, item_line_total

### hagivaa

- Files: **1**
- Average score: **66.0**
- Frequent missing fields: `customer_id` × 1, `item_line_total` × 1, `total` × 1
- Weakest examples:
  - `הגבעה י.ח./PO-64715/PO-64715 (1).pdf` · 51746 · score 66 · customer_id, item_line_total, total

### lati

- Files: **3**
- Average score: **100.0**
- Weakest examples:
  - `לאטי יזום ובנייה/PO25002412/הדפסת הזמנת רכש - PO25002412_ שמעון 054-4.pdf` · PO25002412 · score 100 · no details
  - `לאטי יזום ובנייה/PO26000252/הדפסת הזמנת רכש - PO26000252_ שמעון 054-44.pdf` · PO26000252 · score 100 · no details
  - `לאטי יזום ובנייה/PO26000471/הדפסת הזמנת רכש - PO26000471_ חמזה-0506696.pdf` · PO26000471 · score 100 · no details

### levinstein

- Files: **3**
- Average score: **100.0**
- Weakest examples:
  - `לוינשטיין נתיב/26004/הזמנת רכש_26004_20251015_143734.pdf` · 26004 · score 100 · no details
  - `לוינשטיין נתיב/26214/הזמנת רכש_26214_20251119_160049.pdf` · 26214 · score 100 · no details
  - `לוינשטיין נתיב/לוינשטין נתיב הנדסה ובנין בע-מ - 26937/lev-April.pdf` · 26937 · score 100 · no details

### masad_armour

- Files: **1**
- Average score: **64.0**
- Frequent missing fields: `delivery_address` × 1, `contact_name` × 1, `contact_phone` × 1
- Weakest examples:
  - `Masad Armour/PO25000251/251.pdf` · PO25000251 · score 64 · delivery_address, contact_name, contact_phone

### ram_aderet

- Files: **2**
- Average score: **100.0**
- Weakest examples:
  - `רם אדרת/PO25006660‎/Print Purchase Order - PO25006660.pdf` · PO25006660 · score 100 · no details
  - `רם אדרת/Print Purchase Order - PO25005026.pdf` · PO25005026 · score 100 · no details

### sela

- Files: **1**
- Average score: **72.0**
- Frequent missing fields: `item_description` × 1, `item_line_total` × 1
- Weakest examples:
  - `סלע ביצוע/PO26000850‎/הדפסת הזמנת רכש - PO26000850.pdf` · PO26000850 · score 72 · item_description, item_line_total

### tubul

- Files: **7**
- Average score: **69.1**
- Frequent missing fields: `contact_name` × 7, `contact_phone` × 7, `po_number` × 1, `item_description` × 1, `item_line_total` × 1
- Weakest examples:
  - `טובול חומרי בניין/1208134587/הזמנת רכש_1208134587_20251229_142749.pdf` · ללא מספר · score 28 · po_number, contact_name, contact_phone, item_description, item_line_total
  - `טובול חומרי בניין/1201230407/הזמנת רכש_1201230407_20251021_122746.pdf` · 1201230407 · score 76 · contact_name, contact_phone
  - `טובול חומרי בניין/1201231850/הזמנת רכש_1201231850_20251116_134105.pdf` · 1201231850 · score 76 · contact_name, contact_phone
  - `טובול חומרי בניין/1201232450/הזמנת רכש_1201232450_20251126_165421.pdf` · 1201232450 · score 76 · contact_name, contact_phone
  - `טובול חומרי בניין/1201234538/הזמנת רכש_1201234538_20260108_160448.pdf` · 1201234538 · score 76 · contact_name, contact_phone

### yitzhak_stern

- Files: **1**
- Average score: **72.0**
- Frequent missing fields: `item_description` × 1, `item_line_total` × 1
- Weakest examples:
  - `יצחק שטרן ושו״ת בע״מ/PO25005673/Print Purchase Order - PO25005673.pdf` · PO25005673 · score 72 · item_description, item_line_total

### yuval_alon

- Files: **2**
- Average score: **49.0**
- Frequent missing fields: `po_date` × 2, `delivery_address` × 2, `contact_name` × 2, `contact_phone` × 2
- Weakest examples:
  - `יובל אלון/יובל אלון - 2000001126/2000001126_כל המסמכים.pdf` · 6211000002 · score 49 · po_date, delivery_address, contact_name, contact_phone
  - `יובל אלון/יובל אלון - 2000001126/הזמנה 2000001126.pdf` · 6211000002 · score 49 · po_date, delivery_address, contact_name, contact_phone

## Lowest-Score Files

- `קבוצת ימין/001/מפרט מגיני דלתות - אסף.pdf` · parser `generic` · score **0** · customer_name, po_date, customer_id, delivery_address, contact_name, contact_phone, item_description, item_line_total, total
- `Plasan Reem/52252/450048.pdf` · parser `generic` · score **1** · customer_name, po_date, delivery_address, contact_name, contact_phone, item_description, item_line_total
- `Plasan Sasa/4134065/450049.pdf` · parser `generic` · score **1** · customer_name, po_date, delivery_address, contact_name, contact_phone, item_description, item_line_total
- `Plasan Reem/52252/רא״ם 3 גלילים.pdf` · parser `generic` · score **28** · po_number, contact_name, contact_phone, item_description, item_line_total
- `טובול חומרי בניין/1208134587/הזמנת רכש_1208134587_20251229_142749.pdf` · parser `tubul` · score **28** · po_number, contact_name, contact_phone, item_description, item_line_total
- `ירגד פרויקטים בע״מ/בן יעקב - הזמנת רכש.pdf` · parser `generic` · score **36** · delivery_address, contact_name, contact_phone, item_description, item_line_total
- `יובל אלון/יובל אלון - 2000001126/2000001126_כל המסמכים.pdf` · parser `yuval_alon` · score **49** · po_date, delivery_address, contact_name, contact_phone
- `יובל אלון/יובל אלון - 2000001126/הזמנה 2000001126.pdf` · parser `yuval_alon` · score **49** · po_date, delivery_address, contact_name, contact_phone
- `Masad Armour/PO25000251/251.pdf` · parser `masad_armour` · score **64** · delivery_address, contact_name, contact_phone
- `הגבעה י.ח./PO-64715/PO-64715 (1).pdf` · parser `hagivaa` · score **66** · customer_id, item_line_total, total
- `יצחק שטרן ושו״ת בע״מ/PO25005673/Print Purchase Order - PO25005673.pdf` · parser `yitzhak_stern` · score **72** · item_description, item_line_total
- `סלע ביצוע/PO26000850‎/הדפסת הזמנת רכש - PO26000850.pdf` · parser `sela` · score **72** · item_description, item_line_total
- `עמרם אברהם ביצועים/PO26000447/Print Purchase Order - PO26000447.pdf` · parser `amram` · score **72** · item_description, item_line_total
- `טובול חומרי בניין/1201230407/הזמנת רכש_1201230407_20251021_122746.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `טובול חומרי בניין/1201231850/הזמנת רכש_1201231850_20251116_134105.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `טובול חומרי בניין/1201232450/הזמנת רכש_1201232450_20251126_165421.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `טובול חומרי בניין/1201234538/הזמנת רכש_1201234538_20260108_160448.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `טובול חומרי בניין/1201235896/הזמנת רכש_1201235896_20260205_170204.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `טובול חומרי בניין/1201236883/הזמנת רכש_1201236883_20260225_171004.pdf` · parser `tubul` · score **76** · contact_name, contact_phone
- `Artec/HashDoc_115496.pdf` · parser `artec` · score **88** · delivery_address
- `Artec/HashDoc_116179.pdf` · parser `artec` · score **88** · delivery_address
- `Artec/HashDoc_116385.pdf` · parser `artec` · score **88** · delivery_address
- `אלמוגים/PO26000537/PO26000537 - הדפסת הזמנת רכש.pdf` · parser `almogim` · score **100** · ok
- `אלמוגים/PO26000800/PO26000800 - הדפסת הזמנת רכש.pdf` · parser `almogim` · score **100** · ok
- `אשטרום אלקטרה/00405/ddc461f5-71d1-4d42-a3da-c2bc64f256f8.pdf` · parser `electra_ashtrom` · score **100** · ok
- `אשטרום אלקטרה/PO2535000543/839f10d2-6a79-4be9-9965-27865aec0162.pdf` · parser `electra_ashtrom` · score **100** · ok
- `אשטרום אלקטרה/PO2535000636/057ad725-885d-46a4-8444-871218b7c997.pdf` · parser `electra_ashtrom` · score **100** · ok
- `ברוש/PO25001555‎/הדפסת הזמנת רכש - PO25001555.pdf` · parser `brosh` · score **100** · ok
- `ברוש/PO25001860‎/הדפסת הזמנת רכש - PO25001860.pdf` · parser `brosh` · score **100** · ok
- `ברוש/PO26000069‎/הדפסת הזמנת רכש - PO26000069.pdf` · parser `brosh` · score **100** · ok
