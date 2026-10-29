import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app import container
from app.config import ConfigurationError
from app.models.api_schemas import AnalyzeRequest, AnalyzeResponse, ClaimResult, EvidenceItem
from app.services.pipeline import ClaimErrorEvent, ClaimEvent, ClaimOutcome, ClaimsEvent, ResearchPipeline
from app.services.providers.openrouter import LLMProviderError
from app.services.retrieval_service import RetrievalBudgetError, RetrievalError

log = logging.getLogger("syntheticsilence")
router = APIRouter()


async def get_pipeline() -> ResearchPipeline:
    """Returns the shared pipeline, building it off the event loop on first use."""
    try:
        return await asyncio.to_thread(container.get_pipeline)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_text(request: AnalyzeRequest, pipeline: ResearchPipeline = Depends(get_pipeline)):
    """
    Receives raw text from the Chrome Extension, runs it through the Research Pipeline,
    and returns the extracted claims with their insufficiency signals and explanations.
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
    Same analysis as /analyze, streamed as newline-delimited JSON so the first claim can be shown
    while others are still running. Events:
      {"type":"claims","claims":[...],"truncated":bool}      claims found, before any scoring
      {"type":"claim","index":i,"result":ClaimResult}        one claim finished
      {"type":"claim_error","index":i,"error":{kind,message}} one claim failed; the others continue
      {"type":"error","error":{kind,message}}                 nothing could be analysed
      {"type":"done"}                                         always the last line of a normal run
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
