from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class ConfigurationError(RuntimeError):
    """Raised when the service cannot be assembled from the current environment."""


def load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader. Existing environment variables win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str | None
    openrouter_model: str
    openrouter_base_url: str
    reference_manifold: Path
    temporal_cutoff_year: int
    max_claims: int
    max_source_chars: int
    # "stance": per-source stance drives the verdict. "pooled": v1 single NLI score over pooled sources.
    verdict_mode: str = "pooled"
    # Order does not matter; all listed retrievers are queried concurrently.
    retrievers: tuple = ("wikipedia", "openalex")
    openalex_api_key: str | None = None
    # None means: rank (embedding similarity, keep top 6) in stance mode, pass through in pooled mode,
    # so the pooled configuration keeps reproducing the v1 baseline.
    rank_evidence: bool | None = None
    cache_enabled: bool = True
    cache_path: Path = BACKEND_DIR / ".cache" / "results.sqlite3"
    cache_max_entries: int = 500
    cache_ttl_hours: int = 168

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_DIR / ".env")
        manifold = os.environ.get("SS_REFERENCE_MANIFOLD")
        return cls(
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
            openrouter_model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            openrouter_base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            # Same manifold the E0 experiments were fitted on.
            reference_manifold=Path(manifold) if manifold else REPO_ROOT / "data" / "manifolds" / "fever_train_v1.npy",
            temporal_cutoff_year=int(os.environ.get("SS_TEMPORAL_CUTOFF_YEAR", "2023")),
            max_claims=int(os.environ.get("SS_MAX_CLAIMS", "6")),
            max_source_chars=int(os.environ.get("SS_MAX_SOURCE_CHARS", "8000")),
            verdict_mode=os.environ.get("SS_VERDICT_MODE", "pooled"),
            retrievers=tuple(
                r.strip() for r in os.environ.get("SS_RETRIEVERS", "wikipedia,openalex").split(",") if r.strip()
            ),
            openalex_api_key=os.environ.get("OPENALEX_API_KEY") or None,
            rank_evidence=(
                os.environ["SS_RANK_EVIDENCE"].lower() in ("1", "true", "on")
                if "SS_RANK_EVIDENCE" in os.environ else None
            ),
            cache_enabled=os.environ.get("SS_CACHE", "on").lower() not in ("0", "off", "false", "no"),
            cache_path=Path(os.environ.get("SS_CACHE_PATH") or (BACKEND_DIR / ".cache" / "results.sqlite3")),
            cache_max_entries=int(os.environ.get("SS_CACHE_MAX_ENTRIES", "500")),
            cache_ttl_hours=int(os.environ.get("SS_CACHE_TTL_HOURS", "168")),
        )
