import sys
from pathlib import Path

# Set up paths so the backend application is discoverable
root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app as fastapi_app  # noqa: E402


async def app(scope, receive, send):
    """
    ASGI middleware wrapper for Vercel serverless functions.
    Restores the original request URL path from Vercel's x-matched-path header
    or strips the function entrypoint prefix (/api/index.py) to prevent 404s.
    """
    if scope.get("type") == "http":
        headers = dict(scope.get("headers", []))
        matched_path = headers.get(b"x-matched-path")
        if matched_path:
            raw = matched_path.decode("utf-8").split("?")[0]
            scope["path"] = raw if raw.startswith("/") else f"/{raw}"
        elif scope.get("path", "").startswith("/api/index.py"):
            stripped = scope["path"][len("/api/index.py"):]
            scope["path"] = stripped if stripped.startswith("/") else (f"/{stripped}" if stripped else "/")
    await fastapi_app(scope, receive, send)

