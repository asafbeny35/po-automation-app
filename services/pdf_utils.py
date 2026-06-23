from pathlib import Path
from PyPDF2 import PdfMerger


def merge_pdfs(pdf_paths, output_path):
    merger = PdfMerger()
    try:
        for p in pdf_paths:
            if not p:
                continue
            p = Path(p)
            if p.exists() and p.is_file():
                merger.append(str(p))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            merger.write(f)

        return output_path
    finally:
        merger.close()
