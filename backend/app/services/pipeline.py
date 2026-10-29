import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional, Union
from app.models.claim import ExtractedClaim, NormalizedClaim
from app.models.schemas import Evidence, InsufficiencySignal
from app.services.claim_service import ClaimService
from app.services.ranking_service import EvidenceRankingService
from app.services.algo.engine import CoreResearchEngine
from app.services.algo.stance import AssessedSource, StanceService
from app.services.analysis.temporal import TemporalAnalysisService
from app.services.analysis.calibration import ConformalCalibrator
from app.services.analysis.explanation import ExplanationService
from app.services.cache import ResultCache, make_key
from app.services.verdict import Verdict, pooled_verdict


@dataclass
class ClaimAssessment:
    claim: ExtractedClaim
    normalized: NormalizedClaim
    signal: InsufficiencySignal
    evidence: List[Evidence]
    verdict: Verdict = "insufficient"
    leaning: Optional[str] = None
    sources_relevant: int = 0
    # Present only when per-source stance assessment ran; aligned with `evidence` order.
    assessed: Optional[List[AssessedSource]] = None


@dataclass
class ClaimOutcome:
    claim: ExtractedClaim
    signal: InsufficiencySignal
    explanation: str
    evidence: List[Evidence]
    verdict: Verdict = "insufficient"
    leaning: Optional[str] = None
    sources_relevant: int = 0
    assessed: Optional[List[AssessedSource]] = None


def outcome_to_dict(o: "ClaimOutcome") -> dict:
    """JSON-safe form for the result cache. Stance rows are stored by evidence index."""
    index_of = {id(e): i for i, e in enumerate(o.evidence)}
    assessed = None
    if o.assessed is not None:
        assessed = [
            {"i": index_of[id(a.evidence)], "stance": a.stance, "confidence": a.confidence, "quote": a.quote}
            for a in o.assessed
        ]
    return {
        "signal": o.signal.model_dump(),
        "explanation": o.explanation,
        "evidence": [e.model_dump() for e in o.evidence],
        "verdict": o.verdict,
        "leaning": o.leaning,
        "sources_relevant": o.sources_relevant,
        "assessed": assessed,
    }


def outcome_from_dict(claim: ExtractedClaim, d: dict) -> "ClaimOutcome":
    evidence = [Evidence(**e) for e in d["evidence"]]
    assessed = None
    if d.get("assessed") is not None:
        assessed = [
            AssessedSource(evidence[a["i"]], a["stance"], a["confidence"], a.get("quote"))
            for a in d["assessed"]
        ]
    return ClaimOutcome(
        claim=claim,
        signal=InsufficiencySignal(**d["signal"]),
        explanation=d["explanation"],
        evidence=evidence,
        verdict=d["verdict"],
        leaning=d.get("leaning"),
        sources_relevant=d.get("sources_relevant", len(evidence)),
        assessed=assessed,
    )


@dataclass
class PipelineRun:
    outcomes: List[ClaimOutcome] = field(default_factory=list)
    truncated: bool = False


@dataclass
class ClaimsEvent:
    claims: List[ExtractedClaim]
    truncated: bool = False


@dataclass
class ClaimEvent:
    index: int
    outcome: ClaimOutcome


@dataclass
class ClaimErrorEvent:
    index: int
    error: BaseException


StreamEvent = Union[ClaimsEvent, ClaimEvent, ClaimErrorEvent]


class ResearchPipeline:
    def __init__(
        self,
        claim_service: ClaimService,
        retrieval_service,
        ranking_service: EvidenceRankingService,
        core_engine: CoreResearchEngine,
        temporal_service: TemporalAnalysisService,
        calibrator: ConformalCalibrator,
        explanation_service: ExplanationService,
        max_claims: int = 6,
        concurrency: int = 3,
        stance_service: Optional[StanceService] = None,
        cache: Optional[ResultCache] = None,
        cache_fingerprint: Optional[dict] = None,
    ):
        self.claim_service = claim_service
        self.retrieval = retrieval_service
        self.ranking = ranking_service
        self.core = core_engine
        self.temporal = temporal_service
        self.calibrator = calibrator
        self.explanation = explanation_service
        self.max_claims = max_claims
        self.concurrency = max(1, concurrency)
        # When set, per-source stance drives support/conflict and the verdict.
        # When None, the engine's pooled NLI score is used (v1 behaviour).
        self.stance = stance_service
        self.cache = cache
        self.cache_fingerprint = cache_fingerprint or {}

    async def run(self, source_text: str) -> PipelineRun:
        """
        Executes the full pipeline:
        1. Extract & Normalize Claims
        2. Retrieve & Rank Evidence
        3. Core Algorithm (Density, Uncertainty) and stance / NLI
        4. Temporal Analysis
        5. Calibration
        6. Explanation Generation

        Claims are independent, so they are processed concurrently (bounded) and
        returned in the order they appear in the text. Any stage failure fails the
        whole run: a retrieval outage must not be reported as "no evidence found".
        """
        # 1. Extraction
        extracted_claims = await self.claim_service.extract_claims(source_text)
        truncated = len(extracted_claims) > self.max_claims
        extracted_claims = extracted_claims[: self.max_claims]

        gate = asyncio.Semaphore(self.concurrency)

        async def guarded(claim: ExtractedClaim) -> ClaimOutcome:
            async with gate:
                return await self._process_claim(claim)

        outcomes = await asyncio.gather(*(guarded(c) for c in extracted_claims))
        return PipelineRun(outcomes=list(outcomes), truncated=truncated)

    async def run_stream(self, source_text: str) -> AsyncIterator[StreamEvent]:
        """
        Same work as run(), but yields results as they finish so a client can render the first
        claim while the others are still being checked.

        Extraction failures raise (nothing can be shown). After extraction each claim fails on its
        own: its failure is an explicit ClaimErrorEvent, never an empty result, and the other
        claims still complete.
        """
        extracted = await self.claim_service.extract_claims(source_text)
        truncated = len(extracted) > self.max_claims
        extracted = extracted[: self.max_claims]
        yield ClaimsEvent(claims=extracted, truncated=truncated)

        queue: "asyncio.Queue[StreamEvent]" = asyncio.Queue()
        gate = asyncio.Semaphore(self.concurrency)

        async def worker(index: int, claim: ExtractedClaim) -> None:
            async with gate:
                try:
                    outcome = await self._process_claim(claim)
                    await queue.put(ClaimEvent(index=index, outcome=outcome))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001  isolate one claim's failure
                    await queue.put(ClaimErrorEvent(index=index, error=exc))

        tasks = [asyncio.create_task(worker(i, c)) for i, c in enumerate(extracted)]
        try:
            for _ in tasks:
                yield await queue.get()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_claim(self, claim: ExtractedClaim) -> ClaimOutcome:
        key = None
        if self.cache is not None:
            key = make_key(claim.original_text, self.cache_fingerprint)
            hit = self.cache.get(key)
            if hit is not None:
                try:
                    return outcome_from_dict(claim, hit)
                except Exception:  # noqa: BLE001  a stale or corrupt entry is just a miss
                    pass

        assessment = await self.assess_claim(claim)

        # 7. Explanation
        explanation_text = await self.explanation.generate_explanation(
            assessment.signal, claim.original_text, verdict_summary=self._summary(assessment)
        )

        outcome = ClaimOutcome(
            claim=claim,
            signal=assessment.signal,
            explanation=explanation_text,
            evidence=assessment.evidence,
            verdict=assessment.verdict,
            leaning=assessment.leaning,
            sources_relevant=assessment.sources_relevant,
            assessed=assessment.assessed,
        )
        if self.cache is not None and key is not None:
            self.cache.set(key, outcome_to_dict(outcome))
        return outcome

    @staticmethod
    def _summary(a: "ClaimAssessment") -> str:
        parts = [f"verdict={a.verdict}", f"sources={len(a.evidence)}", f"relevant={a.sources_relevant}"]
        if a.assessed is not None:
            counts = {s: sum(1 for x in a.assessed if x.stance == s) for s in ("supports", "refutes")}
            parts += [f"supporting={counts['supports']}", f"refuting={counts['refutes']}"]
        if a.leaning:
            parts.append(f"leaning={a.leaning}")
        return ", ".join(parts)

    async def assess_claim(self, claim: ExtractedClaim) -> "ClaimAssessment":
        """
        Everything except the explanation text: normalise, retrieve, rank, score, calibrate.
        Used by the API path and by the evaluation harness so both measure the same code.
        """
        # Normalization
        normalized = await self.claim_service.normalize_claim(claim)

        # 2. Retrieval
        raw_evidence = await self.retrieval.retrieve_evidence(normalized)
        # Ranking and stance use the claim exactly as written. Normalisation is lossy (it can drop the
        # very detail that makes a claim false) and is only suitable for building search queries.
        ranked_evidence = await self.ranking.filter_and_rank(raw_evidence, claim.original_text)

        # 3. Core Compute (density, uncertainty; NLI only when no stance service is configured)
        signal = await self.core.compute_signals(normalized, ranked_evidence)

        assessed = None
        leaning = None
        if self.stance is not None:
            stance_result = await self.stance.assess(claim.original_text, ranked_evidence)
            signal.semantic_support = stance_result.support
            signal.contradiction_level = stance_result.conflict
            verdict = stance_result.verdict
            leaning = stance_result.leaning
            relevant = stance_result.relevant
            assessed = stance_result.sources
        else:
            verdict = pooled_verdict(signal.semantic_support, signal.contradiction_level, len(ranked_evidence))
            relevant = len(ranked_evidence)

        # 4. Temporal Analysis
        temporal_coverage = self.temporal.compute_temporal_coverage(ranked_evidence)
        signal.temporal_coverage = temporal_coverage

        # 5. Classification Heuristic (Baseline Prototype)
        # This is a temporary placeholder heuristic, NOT a learned model.
        # Arbitrary weights/thresholds are used here strictly for architectural wiring.
        if self.temporal.extract_temporal_feature_ratio(temporal_coverage):
            signal.construction_family_estimate = "temporal_novelty"
        elif signal.contradiction_level > 0.7:
            signal.construction_family_estimate = "contradictory"
        elif signal.evidence_coverage == 0.0:
            signal.construction_family_estimate = "missing_evidence"
        else:
            signal.construction_family_estimate = "ambiguous_claim"

        # 6. Calibration
        calibrated_signal = self.calibrator.calibrate(signal)

        return ClaimAssessment(
            claim=claim,
            normalized=normalized,
            signal=calibrated_signal,
            evidence=ranked_evidence,
            verdict=verdict,
            leaning=leaning,
            sources_relevant=relevant,
            assessed=assessed,
        )
