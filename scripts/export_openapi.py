"""Write frontend/openapi.json. Run after changing backend/schemas.py, then `npm run types`."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENVIRONMENT", "development")

from backend.main import app  # noqa: E402

(ROOT / "frontend" / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print("frontend/openapi.json updated")
