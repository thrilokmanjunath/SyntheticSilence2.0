import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import container
from app.api import routes
from app.config import ConfigurationError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("syntheticsilence")


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the pipeline in the background so the first request is not slow and
    # /health can report readiness. The server accepts connections immediately.
    async def warm() -> None:
        try:
            await asyncio.to_thread(container.get_pipeline)
        except ConfigurationError as exc:
            log.error("Pipeline not ready: %s", exc)
        except Exception:  # noqa: BLE001
            log.exception("Pipeline warm-up failed")

    task = asyncio.create_task(warm())
    yield
    task.cancel()


app = FastAPI(
    title="SyntheticSilence2.0 Backend",
    description="Evidence Insufficiency Engine API",
    version="1.0.0",
    lifespan=lifespan,
)

# Only the Chrome extension (and local tools) need to call this API. Requests from
# extension pages with host permissions bypass CORS; this covers content scripts.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://[a-z]+|http://(127\.0\.0\.1|localhost)(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(routes.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", **container.status()}
