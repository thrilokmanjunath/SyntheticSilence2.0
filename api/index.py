import sys
from pathlib import Path
from urllib.parse import parse_qs

# Set up paths so the backend application is discoverable
root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app as fastapi_app  # noqa: E402


async def app(scope, receive, send):
    """
    ASGI middleware wrapper for Vercel serverless functions.
    Restores the exact client request path from the query string (__path__)
    populated during Vercel route rewriting, ensuring FastAPI routes match accurately.
    """
    if scope.get("type") == "http":
        raw_qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
        qs = parse_qs(raw_qs)
        if "__path__" in qs and qs["__path__"]:
            scope["path"] = qs["__path__"][0]
        elif scope.get("path", "").startswith("/api/index.py"):
            stripped = scope["path"][len("/api/index.py"):]
            scope["path"] = stripped if stripped.startswith("/") else (f"/{stripped}" if stripped else "/")
    await fastapi_app(scope, receive, send)
