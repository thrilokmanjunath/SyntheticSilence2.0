"""
Per-source stance assessment.

Instead of asking an LLM for one entailment score over ten pooled abstracts, each retrieved
source gets its own stance towards the claim, with a verbatim supporting quote. The verdict is
then derived by deterministic rules (below), so it can be unit-tested and audited without a
second model call.

Verdict rules (thresholds are module constants):
- counted  : a supports/refutes stance with confidence >= CONFIDENCE_FLOOR AND a verbatim quote.
- qualifies: a side has >= 2 counted sources, or 1 counted source with confidence >= STRONG_SINGLE.
- mixed    : both sides have counted sources and at least one side qualifies.
- supported / refuted: only that side qualifies.
- insufficient: sources exist but nothing qualifies. `leaning` names a side that has a counted source.
- no_sources: nothing retrieved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.models.schemas import Evidence
from app.services.llm_provider import LLMProvider
from app.services.verdict import Verdict

Stance = Literal["supports", "refutes", "neutral", "irrelevant"]

CONFIDENCE_FLOOR = 0.5
STRONG_SINGLE = 0.8
SOURCE_CHARS_FOR_PROMPT = 600


class SourceStance(BaseModel):
    index: int
    stance: Stance
    confidence: float = Field(ge=0.0, le=1.0)
    quote: str = ""


class StanceList(BaseModel):
    stances: List[SourceStance]


@dataclass
class AssessedSource:
    evidence: Evidence
    stance: Stance
    confidence: float
    quote: Optional[str]


@dataclass
class StanceResult:
    sources: List[AssessedSource] = field(default_factory=list)
    verdict: Verdict = "no_sources"
    leaning: Optional[Literal["supports", "refutes"]] = None
    support: float = 0.0   # confidence-weighted share of relevant sources that support
    conflict: float = 0.0  # confidence-weighted share of relevant sources that refute
    relevant: int = 0      # supports + refutes + neutral


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_source(quote: str, source_text: str) -> bool:
    q = _norm(quote)
    return len(q) >= 8 and q in _norm(source_text)


def aggregate(sources: List[AssessedSource]) -> StanceResult:
    """Deterministic verdict from per-source stances. See module docstring for the rules."""
    if not sources:
        return StanceResult(verdict="no_sources")

    def counted(side: str) -> List[AssessedSource]:
        return [s for s in sources if s.stance == side and s.confidence >= CONFIDENCE_FLOOR and s.quote]

    def qualifies(items: List[AssessedSource]) -> bool:
        return len(items) >= 2 or (len(items) == 1 and items[0].confidence >= STRONG_SINGLE)

    sup, ref = counted("supports"), counted("refutes")
    sup_ok, ref_ok = qualifies(sup), qualifies(ref)

    verdict: Verdict
    leaning: Optional[Literal["supports", "refutes"]] = None
    if sup and ref and (sup_ok or ref_ok):
        verdict = "mixed"
    elif sup_ok:
        verdict = "supported"
    elif ref_ok:
        verdict = "refuted"
    else:
        verdict = "insufficient"
        if sup and not ref:
            leaning = "supports"
        elif ref and not sup:
            leaning = "refutes"

    relevant = [s for s in sources if s.stance != "irrelevant"]
    total_w = sum(s.confidence for s in relevant)
    support = sum(s.confidence for s in relevant if s.stance == "supports") / total_w if total_w else 0.0
    conflict = sum(s.confidence for s in relevant if s.stance == "refutes") / total_w if total_w else 0.0

    return StanceResult(
        sources=sources, verdict=verdict, leaning=leaning,
        support=support, conflict=conflict, relevant=len(relevant),
    )


class StanceService:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def assess(self, claim_text: str, evidence: List[Evidence]) -> StanceResult:
        if not evidence:
            return StanceResult(verdict="no_sources")

        listing = "\n".join(
            f'<evidence index="{i}">{e.text[:SOURCE_CHARS_FOR_PROMPT]}</evidence>' for i, e in enumerate(evidence)
        )
        prompt = (
            "Decide, for each numbered source, what it says about the claim exactly as written.\n"
            f"<text>{claim_text}</text>\n"
            f"{listing}\n\n"
            "Stance values:\n"
            "- supports: the source confirms EVERY specific detail of the claim (names, dates, places, "
            "numbers, and categories such as film vs television vs book vs radio).\n"
            "- refutes: the source states something that conflicts with a specific detail of the claim, "
            "for example a different year, place, creator or category.\n"
            "- neutral: the source is about the same subject but does not confirm or conflict with the "
            "claim's specific details.\n"
            "- irrelevant: the source is about a different subject.\n"
            "Do not infer or round. A different year or category is a conflict, not support. If a detail "
            "of the claim is not covered by the source, the stance is at most neutral.\n"
            "confidence is 0 to 1. quote is a short verbatim span (at most 200 characters) copied exactly "
            "from the source that contains the facts settling your stance; leave it empty for neutral and "
            "irrelevant. "
            'Return {"stances": [{"index": 0, "stance": "...", "confidence": 0.0, "quote": ""}, ...]} '
            "with exactly one entry per source."
        )
        result = await self.llm_provider.generate_structured_output(prompt, StanceList)

        by_index = {s.index: s for s in result.stances if 0 <= s.index < len(evidence)}
        assessed: List[AssessedSource] = []
        for i, ev in enumerate(evidence):
            s = by_index.get(i)
            if s is None:
                # The model skipped this source: do not guess a stance for it.
                assessed.append(AssessedSource(ev, "neutral", 0.0, None))
                continue
            stance, quote = s.stance, (s.quote or "").strip()
            if stance in ("supports", "refutes"):
                if not quote_in_source(quote, ev.text):
                    # Unverifiable justification: keep the source but do not let it decide anything.
                    stance, quote = "neutral", ""
            else:
                quote = ""
            assessed.append(AssessedSource(ev, stance, s.confidence, quote or None))
        return aggregate(assessed)


class NullNLIAdapter:
    """Stand-in for the pooled NLI call when stance assessment supplies support/conflict instead."""

    async def verify_entailment(self, claim_text: str, evidence_texts: List[str]) -> Tuple[float, float]:
        return 0.0, 0.0
