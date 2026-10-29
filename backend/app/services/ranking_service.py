from typing import List, Optional

import numpy as np

from app.models.schemas import Evidence


class EvidenceRankingService:
    def __init__(
        self,
        embedder=None,
        top_k: int = 6,
        similarity_floor: float = 0.15,
        min_keep: int = 2,
    ):
        """
        embedder: object with get_embeddings(list[str]) -> ndarray (the shared EmbeddingService).
        Without an embedder, or without a claim text, ranking is a pass-through.
        """
        self.embedder = embedder
        self.top_k = top_k
        self.similarity_floor = similarity_floor
        self.min_keep = min_keep

    async def filter_and_rank(self, evidence_list: List[Evidence], claim_text: Optional[str] = None) -> List[Evidence]:
        """
        Deduplicates, ranks, and filters evidence by quality metrics (source type, venue, recency).
        """
        deduplicated = self._deduplicate(evidence_list)
        filtered = self._filter_quality(deduplicated)
        ranked = self._rank(filtered, claim_text)
        return ranked

    def _deduplicate(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """
        Simple exact-text deduplication.
        """
        seen_texts = set()
        deduped = []
        for ev in evidence_list:
            # We lowercase and strip for basic deduping to catch obvious duplicates
            normalized_text = ev.text.lower().strip()
            if normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                deduped.append(ev)
        return deduped

    def _filter_quality(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """
        Filter by source type, venue, recency.
        (Currently a pass-through stub. Real implementation requires mapping metadata
         from OpenAlex to Evidence schema extensions for filtering).
        """
        # Placeholder for actual quality logic
        return evidence_list

    def _rank(self, evidence_list: List[Evidence], claim_text: Optional[str]) -> List[Evidence]:
        """
        Rank by claim-source cosine similarity. Keeps the top_k, and drops sources below the floor
        only beyond the first min_keep, so a poor embedding match alone cannot empty the list
        (an empty list would be read downstream as "no sources exist").
        """
        if self.embedder is None or not claim_text or len(evidence_list) == 0:
            return evidence_list

        claim_vec = np.asarray(self.embedder.get_embeddings([claim_text]), dtype=float)
        ev_vecs = np.asarray(self.embedder.get_embeddings([e.text for e in evidence_list]), dtype=float)
        if claim_vec.size == 0 or ev_vecs.size == 0:
            return evidence_list

        claim_unit = claim_vec / (np.linalg.norm(claim_vec, axis=1, keepdims=True) + 1e-12)
        ev_unit = ev_vecs / (np.linalg.norm(ev_vecs, axis=1, keepdims=True) + 1e-12)
        sims = (ev_unit @ claim_unit.T).ravel()

        order = np.argsort(-sims, kind="stable")
        kept: List[Evidence] = []
        for rank, idx in enumerate(order):
            if len(kept) >= self.top_k:
                break
            if rank >= self.min_keep and sims[idx] < self.similarity_floor:
                break
            ev = evidence_list[int(idx)].model_copy(update={"relevance": float(sims[idx])})
            kept.append(ev)
        return kept
