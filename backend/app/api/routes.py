import asyncio
import json
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from app import container
from app.config import ConfigurationError
from app.models.api_schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ClaimResult,
    EvidenceItem,
    ProviderValidateRequest,
    ProviderValidateResponse,
)
from app.services.pipeline import ClaimErrorEvent, ClaimEvent, ClaimOutcome, ClaimsEvent, ResearchPipeline
from app.services.llm_provider import LLMProviderError
from app.services.retrieval_service import RetrievalBudgetError, RetrievalError

log = logging.getLogger("syntheticsilence")
router = APIRouter()


async def get_pipeline(
    x_provider_key: Optional[str] = Header(None, alias="X-Provider-Key"),
    x_provider_name: Optional[str] = Header(None, alias="X-Provider-Name"),
) -> ResearchPipeline:
    """
    Returns the appropriate research pipeline.
    If ephemeral provider credentials are sent in request headers, an isolated
    ephemeral pipeline is constructed in memory for this request without persistence.
    Otherwise, returns the shared pipeline initialized from server environment variables.
    """
    if x_provider_key and x_provider_name:
        try:
            return await asyncio.to_thread(
                container.build_ephemeral_pipeline,
                x_provider_name.lower().strip(),
                x_provider_key.strip(),
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid ephemeral provider configuration: {exc}") from exc
        except Exception as exc:
            log.warning("Ephemeral pipeline construction failed: %s", type(exc).__name__)
            raise HTTPException(status_code=500, detail="Failed to initialize requested provider.") from exc

    try:
        return await asyncio.to_thread(container.get_pipeline)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/provider/validate", response_model=ProviderValidateResponse)
async def validate_provider(req: ProviderValidateRequest):
    """
    Validates a model provider API key with a minimal, bounded, non-generating check.
    Never persists, writes to disk/database, or echoes the credential in logs or responses.
    """
    key = req.api_key.strip()
    if not key:
        return ProviderValidateResponse(
            valid=False,
            provider=req.provider,
            message="API key cannot be empty.",
        )

    if req.provider == "openrouter":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if res.status_code == 200:
                    return ProviderValidateResponse(
                        valid=True,
                        provider="openrouter",
                        message="OpenRouter credentials verified successfully.",
                    )
                elif res.status_code in (401, 403):
                    return ProviderValidateResponse(
                        valid=False,
                        provider="openrouter",
                        message="Authentication failed: Invalid or expired OpenRouter API key.",
                    )
                else:
                    return ProviderValidateResponse(
                        valid=False,
                        provider="openrouter",
                        message=f"OpenRouter returned HTTP status {res.status_code}.",
                    )
        except httpx.RequestError as exc:
            return ProviderValidateResponse(
                valid=False,
                provider="openrouter",
                message=f"Unable to reach OpenRouter validation service ({type(exc).__name__}).",
            )

    elif req.provider == "gemini":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": key, "pageSize": 1},
                )
                if res.status_code == 200:
                    return ProviderValidateResponse(
                        valid=True,
                        provider="gemini",
                        message="Google Gemini credentials verified successfully.",
                    )
                elif res.status_code in (400, 403):
                    return ProviderValidateResponse(
                        valid=False,
                        provider="gemini",
                        message="Authentication failed: Invalid or unauthorized Google Gemini API key.",
                    )
                else:
                    return ProviderValidateResponse(
                        valid=False,
                        provider="gemini",
                        message=f"Google Gemini returned HTTP status {res.status_code}.",
                    )
        except httpx.RequestError as exc:
            return ProviderValidateResponse(
                valid=False,
                provider="gemini",
                message=f"Unable to reach Google Gemini validation service ({type(exc).__name__}).",
            )

    return ProviderValidateResponse(
        valid=False,
        provider=req.provider,
        message=f"Unsupported provider: {req.provider}",
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_text(request: AnalyzeRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """
    Runs text through the Research Pipeline and returns extracted claims with
    their insufficiency signals, empirical evidence, and explanations.
    """
    if not request.source_text.strip():
        raise HTTPException(status_code=422, detail="source_text is empty.")

    try:
        run = await pipeline.run(request.source_text)
    except RetrievalError as exc:
        raise HTTPException(status_code=502, detail=f"{exc} The source search service may be down.") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed ({type(exc).__name__}).") from exc

    return AnalyzeResponse(
        results=[to_claim_result(o) for o in run.outcomes],
        truncated=run.truncated,
    )


def describe_error(exc: BaseException) -> dict:
    """Maps an exception to a client-safe {kind, message}. Internal errors never leak details."""
    if isinstance(exc, RetrievalBudgetError):
        return {"kind": "retrieval_budget", "message": str(exc)}
    if isinstance(exc, RetrievalError):
        return {"kind": "retrieval", "message": f"{exc} The source search service may be down."}
    if isinstance(exc, LLMProviderError):
        return {"kind": "llm", "message": str(exc)}
    return {"kind": "internal", "message": f"Analysis failed ({type(exc).__name__})."}


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """
    Streamed analysis as newline-delimited JSON.
    """
    if not request.source_text.strip():
        raise HTTPException(status_code=422, detail="source_text is empty.")

    async def body():
        try:
            async for event in pipeline.run_stream(request.source_text):
                if isinstance(event, ClaimsEvent):
                    yield _line({
                        "type": "claims",
                        "claims": [c.model_dump() for c in event.claims],
                        "truncated": event.truncated,
                    })
                elif isinstance(event, ClaimEvent):
                    yield _line({
                        "type": "claim",
                        "index": event.index,
                        "result": to_claim_result(event.outcome).model_dump(mode="json"),
                    })
                elif isinstance(event, ClaimErrorEvent):
                    if not isinstance(event.error, (RetrievalError, LLMProviderError)):
                        log.error("claim %s failed", event.index, exc_info=event.error)
                    yield _line({"type": "claim_error", "index": event.index, "error": describe_error(event.error)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if not isinstance(exc, (RetrievalError, LLMProviderError)):
                log.exception("Streaming pipeline failed")
            yield _line({"type": "error", "error": describe_error(exc)})
            return
        yield _line({"type": "done"})

    return StreamingResponse(body(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


def to_claim_result(o: ClaimOutcome) -> ClaimResult:
    stances = {id(s.evidence): s for s in (o.assessed or [])}
    items = []
    for e in o.evidence:
        s = stances.get(id(e))
        items.append(
            EvidenceItem(
                id=e.id, text=e.text, title=e.title, source_url=e.source_url,
                publication_year=e.publication_year, kind=e.kind, relevance=e.relevance,
                stance=s.stance if s else None,
                confidence=s.confidence if s else None,
                quote=s.quote if s else None,
            )
        )
    return ClaimResult(
        claim=o.claim,
        signal=o.signal,
        explanation=o.explanation,
        evidence=items,
        verdict=o.verdict,
        leaning=o.leaning,  # type: ignore[arg-type]
        sources_considered=len(o.evidence),
        sources_relevant=o.sources_relevant,
    )
