"""
Assembles the ResearchPipeline from settings.

The pipeline is built once and cached: loading the embedding model and fitting the
density estimator on the reference manifold takes several seconds.
"""
import logging
import threading
from typing import Optional

import numpy as np

from app.config import ConfigurationError, Settings
from app.services.algo.density import DensityEstimator
from app.services.algo.embeddings import EmbeddingService
from app.services.algo.engine import CoreResearchEngine
from app.services.algo.nli import LLMNLIAdapter
from app.services.algo.uncertainty import SimilarityDistributionEntropy
from app.services.analysis.calibration import ConformalCalibrator
from app.services.analysis.explanation import ExplanationService
from app.services.analysis.temporal import TemporalAnalysisService
from app.services.claim_service import ClaimService
from app.services.cache import ResultCache
from app.services.pipeline import ResearchPipeline
from app.services.providers.openrouter import OpenRouterProvider
from app.services.ranking_service import EvidenceRankingService
from app.services.retrieval_service import CompositeRetrievalService, OpenAlexRetrievalService
from app.services.wikipedia_service import WikipediaRetrievalService
from app.services.algo.stance import NullNLIAdapter, StanceService

log = logging.getLogger("syntheticsilence")

_lock = threading.Lock()
_pipeline: Optional[ResearchPipeline] = None
_error: Optional[str] = None
_info: dict = {}


def build_pipeline(settings: Settings) -> ResearchPipeline:
    if not settings.openrouter_api_key:
        raise ConfigurationError(
            "OPENROUTER_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
        )

    # The density estimator is only meaningful once fitted on a reference manifold.
    # An unfitted estimator returns zeros, which would read as "perfectly supported",
    # so refuse to serve rather than fabricate the signal.
    if not settings.reference_manifold.is_file():
        raise ConfigurationError(
            f"Reference manifold not found at {settings.reference_manifold}. "
            "Set SS_REFERENCE_MANIFOLD or restore data/manifolds/fever_train_v1.npy."
        )
    reference = np.load(settings.reference_manifold)
    if reference.ndim != 2 or len(reference) < 2:
        raise ConfigurationError(f"Reference manifold has unexpected shape {reference.shape}.")

    embedder = EmbeddingService()
    dim = embedder.get_embeddings(["dimension probe"]).shape[1]
    if reference.shape[1] != dim:
        raise ConfigurationError(
            f"Reference manifold has {reference.shape[1]} dimensions but the embedding model produces {dim}."
        )

    # Same estimator and defaults as scripts/run_experiment.py, so the served score
    # is the one that was evaluated.
    density = DensityEstimator()
    density.fit(reference)

    llm = OpenRouterProvider(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
    )

    if settings.verdict_mode not in ("pooled", "stance"):
        raise ConfigurationError(f"SS_VERDICT_MODE must be 'pooled' or 'stance', got {settings.verdict_mode!r}.")
    use_stance = settings.verdict_mode == "stance"
    rank = settings.rank_evidence if settings.rank_evidence is not None else use_stance

    # In stance mode support/conflict come from per-source stance, so the pooled NLI call is skipped.
    engine = CoreResearchEngine(
        embedding_service=embedder,
        density_estimator=density,
        uncertainty_module=SimilarityDistributionEntropy(),
        nli_service=NullNLIAdapter() if use_stance else LLMNLIAdapter(llm),
    )

    log.info(
        "Pipeline ready: %d reference vectors, model=%s, verdict_mode=%s, retrievers=%s",
        len(reference), settings.openrouter_model, settings.verdict_mode, ",".join(settings.retrievers),
    )
    # Anything that can change a result belongs in the cache key.
    fingerprint = {
        "model": settings.openrouter_model,
        "mode": settings.verdict_mode,
        "retrievers": sorted(settings.retrievers),
        "rank": bool(rank),
        "cutoff": settings.temporal_cutoff_year,
    }
    cache = None
    if settings.cache_enabled:
        cache = ResultCache(
            settings.cache_path, max_entries=settings.cache_max_entries,
            ttl_seconds=settings.cache_ttl_hours * 3600,
        )
    global _info
    _info = {
        "verdict_mode": settings.verdict_mode,
        "retrievers": list(settings.retrievers),
        "openalex_key": bool(settings.openalex_api_key),
        "model": settings.openrouter_model,
        "cache": settings.cache_enabled,
    }
    return ResearchPipeline(
        claim_service=ClaimService(llm),
        retrieval_service=_build_retriever(settings),
        ranking_service=EvidenceRankingService(embedder=embedder if rank else None),
        core_engine=engine,
        temporal_service=TemporalAnalysisService(cutoff_year=settings.temporal_cutoff_year),
        calibrator=ConformalCalibrator(),  # never fitted here: scores are reported NOT_CALIBRATED
        explanation_service=ExplanationService(llm),
        max_claims=settings.max_claims,
        stance_service=StanceService(llm) if use_stance else None,
        cache=cache,
        cache_fingerprint=fingerprint,
    )


def _build_retriever(settings: Settings):
    available = {
        "openalex": lambda: OpenAlexRetrievalService(api_key=settings.openalex_api_key),
        "wikipedia": lambda: WikipediaRetrievalService(),
    }
    unknown = [r for r in settings.retrievers if r not in available]
    if unknown or not settings.retrievers:
        raise ConfigurationError(f"SS_RETRIEVERS has unknown or no entries: {settings.retrievers!r}.")
    built = [available[name]() for name in settings.retrievers]
    return built[0] if len(built) == 1 else CompositeRetrievalService(built)


def get_pipeline(settings: Optional[Settings] = None) -> ResearchPipeline:
    """Blocking; call from a worker thread. Raises ConfigurationError on bad setup."""
    global _pipeline, _error
    with _lock:
        if _pipeline is None:
            try:
                _pipeline = build_pipeline(settings or Settings.from_env())
                _error = None
            except ConfigurationError as exc:
                _error = str(exc)
                raise
        return _pipeline


def status() -> dict:
    # `info` carries non-secret configuration so the extension can show what it is talking to.
    return {"pipeline_ready": _pipeline is not None, "pipeline_error": _error, "info": dict(_info) or None}


def reset() -> None:
    """Test hook."""
    global _pipeline, _error, _info
    with _lock:
        _pipeline, _error, _info = None, None, {}
