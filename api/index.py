import sys
import os
from pathlib import Path

# Add project root to path so `from services import ...` works
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: F401 — Vercel picks up `app` as the ASGI handler
