import asyncio
import contextlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app import container
from app.api import routes
from app.config import ConfigurationError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("syntheticsilence")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "production").lower()
IS_DEVELOPMENT = ENVIRONMENT in ("development", "dev", "local")


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the pipeline in the background so the first request is not slow and
    # /health can report readiness. The server accepts connections immediately.
    async def warm() -> None:
        try:
            await asyncio.to_thread(container.get_pipeline)
        except ConfigurationError as exc:
            log.info("Pipeline initialized without default provider key: %s", exc)
        except Exception:  # noqa: BLE001
            log.exception("Pipeline warm-up failed")

    task = asyncio.create_task(warm())
    yield
    task.cancel()


# In production, disable interactive Swagger / ReDoc / OpenAPI schemas to protect internal structure
app = FastAPI(
    title="SyntheticSilence2.0 Backend",
    description="Evidence Insufficiency Engine API",
    version="2.0.0",
    docs_url="/docs" if IS_DEVELOPMENT else None,
    redoc_url="/redoc" if IS_DEVELOPMENT else None,
    openapi_url="/openapi.json" if IS_DEVELOPMENT else None,
    redirect_slashes=False,
    lifespan=lifespan,
)


# Request Body Size Limiter (256 KB max to prevent buffer and memory exhaustion attacks)
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 262144:  # 256 KB
        return JSONResponse(status_code=413, content={"detail": "Payload too large. Max 256 KB permitted."})
    return await call_next(request)


# Production Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    )
    if not IS_DEVELOPMENT:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://openrouter.ai https://generativelanguage.googleapis.com https://en.wikipedia.org https://api.openalex.org http://127.0.0.1:* http://localhost:*; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    return response


# CORS Configuration
allowed_origins_env = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_env or [],
    allow_origin_regex=r"^(chrome-extension://[a-z]+|http://(127\.0\.0\.1|localhost)(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Provider-Key", "X-Provider-Name"],
)

app.include_router(routes.router, prefix="/api/v1")

INDEX_HTML = Path(__file__).parent / "static" / "index.html"


@app.get("/api/debug-headers")
async def debug_headers(request: Request):
    return {
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "headers": dict(request.headers),
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def serve_index(request: Request):
    # If the user requested /api/... or /health, do not return index HTML!
    req_path = request.headers.get("x-invoke-path") or request.headers.get("x-vercel-sc-path") or request.url.path
    if INDEX_HTML.is_file():
        return HTMLResponse(content=INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Synthetic Silence 2.0</h1><p>Engine API Active.</p>")


@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    """
    Sanitized health check endpoint: reports operational availability without leaking
    environment variable values, file paths, credentials, or stack traces.
    """
    return {"status": "healthy", **container.status()}
