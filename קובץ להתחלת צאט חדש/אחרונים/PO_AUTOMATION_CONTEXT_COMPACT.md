# PO Automation – AI CONTEXT (COMPACT)

## FLOW
PDF → /process → JSON → /finalize → Docs → Label → Merge → WhatsApp → Sheets → Transport

---

## MODES
sandbox → extract only  
prod → create docs  
sandbox_with_transport → sandbox + transport  
prod_with_transport → prod + transport  

run_transport = mode in ("prod_with_transport","sandbox_with_transport")

---

## /process
- parse PDF
- fetch customer + payment terms
- return JSON ONLY
❌ no docs

---

## /finalize
- delivery + invoice
- label
- copy PO
- merge PDFs
- WhatsApp send
- Google Sheets
- optional transport

---

## MERGE
file: {po}_כל המסמכים.pdf

IN:
- delivery
- delivery
- label

OUT:
- invoice
- PO

---

## WHATSAPP
send ONLY merged PDF  
phone: 0547720142

---

## TRANSPORT
thread-based  
runs only if run_transport=True

---

## FRONTEND
upload() → /process  
send() → /finalize  

✔ drag works  
✔ click works  
✔ filename shown  

---

## RULES
- must have customer_id  
- no customer creation  
- prefer PDF data  

---

## DEBUG EXPECTED
LABEL OK  
SOURCE PO COPIED  
MERGED PDF CREATED  
Transport started  

---

## FILES
app.py  
services/*  
templates/index.html  

---

## STATUS
✔ working  
✔ stable  
✔ production-ready  

---

## DEV RULES
❌ no refactor  
❌ no flow changes  
✔ only minimal fixes
