"""Write the backend's OpenAPI schema as JSON. Used to generate the extension's API types.

    python scripts/export_openapi.py extension/src/models/openapi.json
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + trailing newline keep the committed file stable for drift checks
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
