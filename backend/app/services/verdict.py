"""
User-facing verdict rules. Single source of truth for backend, evaluation harness and API.

The verdict is derived from what the sources say about the claim (stance / NLI), never from the
density-based "gap score": the research finding for this project is that the density signal does
not generalise across constructions.
"""
from typing import Literal

Verdict = Literal["supported", "refuted", "mixed", "insufficient", "no_sources"]

# v1 display bins over a pooled NLI score pair. Presentation choices, not calibrated thresholds.
POOLED_SUPPORT_MIN = 0.6
POOLED_CONFLICT_MIN = 0.5

# Verdict -> FEVER label used by the evaluation harness. "mixed" is reported separately.
VERDICT_TO_FEVER = {
    "supported": "SUPPORTS",
    "refuted": "REFUTES",
    "insufficient": "NOT ENOUGH INFO",
    "no_sources": "NOT ENOUGH INFO",
    "mixed": "MIXED",
}


def pooled_verdict(support: float, conflict: float, source_count: int) -> Verdict:
    """v1 behaviour: one NLI score pair over the pooled evidence. Conflict is checked first."""
    if source_count == 0:
        return "no_sources"
    if conflict >= POOLED_CONFLICT_MIN:
        return "refuted"
    if support >= POOLED_SUPPORT_MIN:
        return "supported"
    return "insufficient"
