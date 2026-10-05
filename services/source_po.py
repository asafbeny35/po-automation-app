"""Resolve an original customer PO before any fiscal documents are created."""
import base64
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PyPDF2 import PdfReader


def resolve_source_po(data, upload_dir, download_file=None):
    encoded = str(data.get("source_file_base64") or "").strip()
    raw_path = str(data.get("source_file_path") or "").strip()
    drive_id = str(data.get("source_drive_file_id") or "").strip()
    if not (encoded or raw_path or drive_id):
        return None
    destination = Path(upload_dir) / f"{uuid4().hex}_original-po.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if encoded:
            content = base64.b64decode(encoded, validate=True)
        elif raw_path and Path(raw_path).is_file():
            content = Path(raw_path).read_bytes()
        elif drive_id:
            if download_file is None:
                from services.google_drive_sync import download_file
            download_file(drive_id, destination)
            content = destination.read_bytes()
        else:
            raise ValueError("Original PO upload is no longer available")
        if not content.startswith(b"%PDF-") or not PdfReader(BytesIO(content)).pages:
            raise ValueError("Original PO is not a readable PDF")
        destination.write_bytes(content)
        return destination
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise ValueError("לא ניתן לצרף את הזמנת הרכש המקורית. בחר שוב את קובץ ה-PDF לפני הפקת המסמכים.") from exc
