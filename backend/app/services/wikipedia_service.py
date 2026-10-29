import asyncio
from typing import Dict, List, Optional

import httpx

from app.models.claim import NormalizedClaim
from app.models.schemas import ConstructionFamily, Evidence
from app.services.retrieval_service import RetrievalError

USER_AGENT = (
    "SyntheticSilence2.0/1.0 (research prototype; "
    "https://github.com/thrilokmanjunath/SyntheticSilence2.0)"
)
EXTRACT_CHARS = 1000


class WikipediaRetrievalService:
    """
    Encyclopedic evidence from the English Wikipedia (MediaWiki search + lead-section extracts).

    Two queries per claim: the normalised sentence, and the core entity so the entity's own article is found.
    """
    name = "wikipedia"

    def __init__(
        self,
        base_url: str = "https://en.wikipedia.org/w/api.php",
        timeout: float = 15.0,
        per_query: int = 4,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = base_url
        self.per_query = per_query
        self.client = client or httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT})

    async def retrieve_evidence(self, claim: NormalizedClaim, max_results: int = 8) -> List[Evidence]:
        queries: List[str] = []
        for q in (claim.normalized_text, claim.core_entity):
            q = (q or "").strip()
            if q and q.lower() not in {x.lower() for x in queries}:
                queries.append(q)
        if not queries:
            return []

        batches = await asyncio.gather(*(self._search(q) for q in queries))

        # Keep the best (lowest) rank for a page that several queries found.
        best: Dict[int, Dict] = {}
        for batch in batches:
            for page in batch:
                current = best.get(page["pageid"])
                if current is None or page.get("index", 99) < current.get("index", 99):
                    best[page["pageid"]] = page

        evidence: List[Evidence] = []
        for page in sorted(best.values(), key=lambda p: p.get("index", 99)):
            text = (page.get("extract") or "").strip()
            if not text or text.endswith("may refer to:"):
                continue  # empty page or a disambiguation stub
            url = f"https://en.wikipedia.org/?curid={page['pageid']}"
            evidence.append(
                Evidence(
                    id=url,
                    text=text,
                    source_url=url,
                    publication_year=None,
                    construction_family=ConstructionFamily.ambiguous_claim,
                    kind="encyclopedia",
                    title=page.get("title"),
                )
            )
            if len(evidence) >= max_results:
                break
        return evidence

    async def _search(self, query: str) -> List[Dict]:
        params = {
            "action": "query", "format": "json", "formatversion": 2,
            "generator": "search", "gsrsearch": query, "gsrlimit": self.per_query,
            "prop": "extracts", "exintro": 1, "explaintext": 1,
            "exlimit": self.per_query, "exchars": EXTRACT_CHARS,
        }
        for attempt in (0, 1):
            try:
                response = await self.client.get(self.base_url, params=params)
            except httpx.HTTPError as exc:
                raise RetrievalError(f"Wikipedia search failed ({type(exc).__name__}).") from exc
            if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                await asyncio.sleep(1.0)
                continue
            try:
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RetrievalError(f"Wikipedia search failed ({type(exc).__name__}).") from exc
            return list((body.get("query") or {}).get("pages") or [])
        raise RetrievalError("Wikipedia search failed.")  # pragma: no cover

    async def aclose(self) -> None:
        await self.client.aclose()
