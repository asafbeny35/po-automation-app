# PO Automation App – FULL CONTEXT (V2 – CURRENT STATE)

## Overview
PDF → Parse → Edit → Green Invoice → Label → Merge → WhatsApp → Google Sheets → Transport (optional)

---

## MODES

- sandbox → extract only
- prod → create real documents
- sandbox_with_transport → sandbox + transport
- prod_with_transport → production + transport

Server logic:

run_transport = mode in ("prod_with_transport", "sandbox_with_transport")

if mode == "prod_with_transport":
    mode = "prod"
elif mode == "sandbox_with_transport":
    mode = "sandbox"

---

## /process
- Upload PDF
- Extract + parse
- Fetch payment terms from GreenInvoice
- Return JSON only
- DOES NOT create documents

---

## /finalize
- Create delivery + invoice
- Generate label
- Copy original PO
- Merge PDFs
- Send WhatsApp
- Append Google Sheets
- Optional: open transport

---

## OUTPUT STRUCTURE

output/{customer} - {po_number}/

Files:
- delivery.pdf
- invoice.pdf
- label.pdf
- original PO
- merged.pdf
- message.txt

---

## MERGED PDF RULES

Includes:
1. Delivery
2. Delivery (duplicate)
3. Label

Excludes:
- Invoice
- PO

---

## WHATSAPP
- Sends ONLY merged.pdf
- Phone: 0547720142

---

## TRANSPORT
Triggered if:
run_transport == True

Thread-based execution

---

## FRONTEND

### Upload
- Drag & drop works
- Click works
- File name displayed

### הפק
- Calls /process only
- No document creation

### צור
- Calls /finalize

---

## DATA MODEL

po.extra = {
  "project": "",
  "delivery_address": "",
  "contact_name": "",
  "contact_phone": "",
  "footer_text": ""
}

---

## RULES

- Do NOT create customers
- Must have customer_id
- Trust PDF for:
  - address
  - contact info

---

## DEBUG LOGS

Expected logs:

LABEL OK
SOURCE PO COPIED
MERGED PDF CREATED
Transport automation started

---

## FILES

- app.py
- services/greeninvoice.py
- services/label_generator_v4.py
- services/whatsapp_web.py
- services/google_sheets.py
- services/tictruck.py
- templates/index.html

---

## STATUS

System is:
- Stable
- Working
- Near production

---

## DEV RULES

- No refactor
- Only minimal fixes
- Do not break flow
