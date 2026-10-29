import sys
from pathlib import Path

# Set up paths so the backend application is discoverable
root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402, F401
