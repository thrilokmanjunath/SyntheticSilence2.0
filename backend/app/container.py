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
from app.services.providers.gemini import GeminiProvider
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
_shared_embedder: Optional[EmbeddingService] = None
_shared_density: Optional[DensityEstimator] = None


def _get_shared_manifold_components(settings: Settings):
    global _shared_embedder, _shared_density
    if _shared_embedder is not None and _shared_density is not None:
        return _shared_embedder, _shared_density

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

    density = DensityEstimator()
    density.fit(reference)
    _shared_embedder = embedder
    _shared_density = density
    return embedder, density


def build_pipeline(settings: Settings, custom_llm: Optional[object] = None) -> ResearchPipeline:
    embedder, density = _get_shared_manifold_components(settings)

    if custom_llm is not None:
        llm = custom_llm
        model_name = getattr(custom_llm, "model", "custom")
    elif settings.openrouter_api_key:
        llm = OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        )
        model_name = settings.openrouter_model
    elif settings.gemini_api_key:
        llm = GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        model_name = settings.gemini_model
    else:
        raise ConfigurationError(
            "OPENROUTER_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
        )

    if settings.verdict_mode not in ("pooled", "stance"):
        raise ConfigurationError(f"SS_VERDICT_MODE must be 'pooled' or 'stance', got {settings.verdict_mode!r}.")
    use_stance = settings.verdict_mode == "stance"
    rank = settings.rank_evidence if settings.rank_evidence is not None else use_stance

    engine = CoreResearchEngine(
        embedding_service=embedder,
        density_estimator=density,
        uncertainty_module=SimilarityDistributionEntropy(),
        nli_service=NullNLIAdapter() if use_stance else LLMNLIAdapter(llm),
    )

    log.info(
        "Pipeline initialized: model=%s, verdict_mode=%s, retrievers=%s",
        model_name, settings.verdict_mode, ",".join(settings.retrievers),
    )
    fingerprint = {
        "model": model_name,
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
        "model": model_name,
        "cache": settings.cache_enabled,
    }
    return ResearchPipeline(
        claim_service=ClaimService(llm),
        retrieval_service=_build_retriever(settings),
        ranking_service=EvidenceRankingService(embedder=embedder if rank else None),
        core_engine=engine,
        temporal_service=TemporalAnalysisService(cutoff_year=settings.temporal_cutoff_year),
        calibrator=ConformalCalibrator(),
        explanation_service=ExplanationService(llm),
        max_claims=settings.max_claims,
        stance_service=StanceService(llm) if use_stance else None,
        cache=cache,
        cache_fingerprint=fingerprint,
    )


def build_ephemeral_pipeline(provider_name: str, api_key: str, settings: Optional[Settings] = None) -> ResearchPipeline:
    """Builds an isolated, ephemeral pipeline for a specific user-supplied request credential."""
    cfg = settings or Settings.from_env()
    if provider_name == "gemini":
        llm = GeminiProvider(api_key=api_key, model=cfg.gemini_model)
    elif provider_name == "openrouter":
        llm = OpenRouterProvider(api_key=api_key, model=cfg.openrouter_model, base_url=cfg.openrouter_base_url)
    else:
        raise ConfigurationError(f"Unsupported provider: {provider_name}")
    return build_pipeline(cfg, custom_llm=llm)


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


def is_ready() -> bool:
    return _pipeline is not None


def status() -> dict:
    return {"pipeline_ready": _pipeline is not None, "pipeline_error": _error, "info": dict(_info) or None}


def reset() -> None:
    """Test hook."""
    global _pipeline, _error, _info, _shared_embedder, _shared_density
    with _lock:
        _pipeline, _error, _info = None, None, {}
        _shared_embedder, _shared_density = None, None
