    # ===== COC (PLASAN ONLY) =====
    try:
        from services.coc_generator import generate_coc_pdf
        from pathlib import Path

        if po.customer_name == "פלסן סאסא בע\"מ":
            target_dir = Path(delivery_pdf_path).parent if delivery_pdf_path else OUTPUT_DIR
            target_dir.mkdir(parents=True, exist_ok=True)

            coc_path = target_dir / f"coc_{po.po_number}.pdf"
            logo_path = "assets/logo.svg"

            generate_coc_pdf(po, str(coc_path), logo_path)

            print("COC CREATED:", coc_path)

    except Exception as e:
        print("COC ERROR:", repr(e))
