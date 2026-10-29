import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Protocol, Sequence

import httpx

from app.models.claim import NormalizedClaim
from app.models.schemas import Evidence, ConstructionFamily

log = logging.getLogger("syntheticsilence")

# Abstracts can be very long; the stance prompt includes every evidence text, so cap each one.
MAX_EVIDENCE_CHARS = 1500

# A 429 that asks us to wait longer than this is a spent budget, not a blip: do not sleep on it.
MAX_INLINE_WAIT_S = 5.0


class RetrievalError(RuntimeError):
    """Evidence retrieval failed. Distinct from "no evidence found", which is a valid result."""


class RetrievalBudgetError(RetrievalError):
    """The search provider's request budget is spent. Retrying now will not help."""


class EvidenceRetriever(Protocol):
    name: str

    async def retrieve_evidence(self, claim: NormalizedClaim, max_results: int = 10) -> List[Evidence]: ...


def _hours(seconds: float) -> str:
    return f"{max(seconds, 0) / 3600:.0f}h" if seconds >= 3600 else f"{max(seconds, 0) / 60:.0f}min"


class OpenAlexRetrievalService:
    name = "openalex"

    def __init__(
        self,
        base_url: str = "https://api.openalex.org",
        timeout: float = 20.0,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        concurrency: int = 2,
    ):
        self.base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.has_key = bool(api_key)
        self.client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._gate = asyncio.Semaphore(concurrency)
        self._blocked_until = 0.0

    async def retrieve_evidence(self, claim: NormalizedClaim, max_results: int = 10) -> List[Evidence]:
        """
        Retrieves evidence strictly from OpenAlex using the normalized claim.
        One request per claim: anonymous use shares a small daily budget per IP.
        """
        # Construct a search query based on the core entity and predicate.
        query = f"{claim.core_entity} {claim.core_predicate}".strip()
        if not query:
            return []

        remaining = self._blocked_until - time.monotonic()
        if remaining > 0:
            raise RetrievalBudgetError(self._budget_message(remaining))

        # OpenAlex Works API: search across title, abstract, and fulltext
        params = {
            "search": query,
            "per-page": max_results,
            "select": "id,title,abstract_inverted_index,doi,publication_year,primary_location"
        }

        data = await self._get_json("/works", params)

        evidence_list = []
        for work in data.get("results", []):
            # Reconstruct the abstract from the inverted index, fallback to title
            abstract_text = self._reconstruct_abstract(work.get("abstract_inverted_index"))
            text = abstract_text if abstract_text else (work.get("title") or "")

            if not text:
                continue

            source_url = work.get("doi")
            if not source_url and work.get("primary_location"):
                source_url = (work.get("primary_location") or {}).get("landing_page_url")

            year = work.get("publication_year")

            # Defaulting to a baseline construction family; will be updated by later pipeline stages
            evidence = Evidence(
                id=work["id"],
                text=text[:MAX_EVIDENCE_CHARS],
                source_url=source_url,
                publication_year=year if isinstance(year, int) else None,
                construction_family=ConstructionFamily.ambiguous_claim,
                kind="scholarly",
                title=work.get("title"),
            )
            evidence_list.append(evidence)

        return evidence_list

    async def _get_json(self, path: str, params: Dict) -> Dict:
        async with self._gate:
            for attempt in (0, 1):
                try:
                    response = await self.client.get(path, params=params, headers=self._headers)
                except httpx.HTTPError as exc:
                    raise RetrievalError(f"OpenAlex search failed ({type(exc).__name__}).") from exc

                if response.status_code == 429:
                    wait = _retry_after(response)
                    if wait > MAX_INLINE_WAIT_S:
                        self._blocked_until = time.monotonic() + wait
                        raise RetrievalBudgetError(self._budget_message(wait))
                    if attempt == 0:
                        await asyncio.sleep(max(wait, 0.5))
                        continue
                    raise RetrievalError("OpenAlex is rate limiting requests. Try again shortly.")

                try:
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise RetrievalError(f"OpenAlex search failed ({type(exc).__name__}).") from exc
        raise RetrievalError("OpenAlex search failed.")  # pragma: no cover

    def _budget_message(self, wait_s: float) -> str:
        hint = "" if self.has_key else " Add a free OPENALEX_API_KEY to backend/.env for your own budget."
        return f"OpenAlex search budget is used up (resets in about {_hours(wait_s)}).{hint}"

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        if not inverted_index:
            return ""

        # Inverted index format: {"word1": [pos1, pos2], "word2": [pos3]}
        words = []
        for word, positions in inverted_index.items():
            for pos in positions:
                words.append((pos, word))

        words.sort(key=lambda x: x[0])
        return " ".join([word for _, word in words])

    async def aclose(self) -> None:
        await self.client.aclose()


def _retry_after(response: httpx.Response) -> float:
    try:
        return float(response.headers.get("retry-after", "1"))
    except ValueError:
        return 1.0


def _fingerprint(ev: Evidence) -> str:
    return re.sub(r"\W+", " ", ev.text.lower()).strip()[:200]


class CompositeRetrievalService:
    """
    Queries several retrievers concurrently and merges their evidence.

    A failing retriever is tolerated only while another one produced evidence. If every retriever
    failed, or one failed and nothing else was found, the call raises: an outage must not be
    reported to the user as "no sources exist".
    """
    name = "composite"

    def __init__(self, retrievers: Sequence[EvidenceRetriever]):
        if not retrievers:
            raise ValueError("CompositeRetrievalService needs at least one retriever")
        self.retrievers = list(retrievers)

    async def retrieve_evidence(self, claim: NormalizedClaim, max_results: int = 10) -> List[Evidence]:
        results = await asyncio.gather(
            *(r.retrieve_evidence(claim, max_results) for r in self.retrievers), return_exceptions=True
        )

        merged: List[Evidence] = []
        seen: set = set()
        failures: List[BaseException] = []
        for retriever, result in zip(self.retrievers, results):
            if isinstance(result, BaseException):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                failures.append(result)
                log.warning("retriever %s failed: %s", getattr(retriever, "name", "?"), result)
                continue
            for ev in result:
                key = (ev.id, _fingerprint(ev))
                if ev.id in seen or key[1] in seen:
                    continue
                seen.add(ev.id)
                seen.add(key[1])
                merged.append(ev)

        if failures and not merged:
            budget = next((f for f in failures if isinstance(f, RetrievalBudgetError)), None)
            raise budget or (failures[0] if isinstance(failures[0], RetrievalError) else RetrievalError(str(failures[0])))
        return merged
