from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.models.claim import ExtractedClaim
from app.models.schemas import InsufficiencySignal

class AnalyzeRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=8000)

class EvidenceItem(BaseModel):
    id: str
    text: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    publication_year: Optional[int] = None
    kind: Literal["scholarly", "encyclopedia"] = "scholarly"
    # Per-source stance; null when the backend runs in pooled mode.
    stance: Optional[Literal["supports", "refutes", "neutral", "irrelevant"]] = None
    confidence: Optional[float] = None
    quote: Optional[str] = None
    # Claim-source embedding similarity (0 to 1), for ordering and display.
    relevance: Optional[float] = None

class ClaimResult(BaseModel):
    claim: ExtractedClaim
    signal: InsufficiencySignal
    explanation: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    # User-facing verdict, derived from what the sources say (never from the density gap score).
    verdict: Literal["supported", "refuted", "mixed", "insufficient", "no_sources"] = "insufficient"
    # For "insufficient": a side with one counted but not qualifying source.
    leaning: Optional[Literal["supports", "refutes"]] = None
    sources_considered: int = 0
    sources_relevant: int = 0

class AnalyzeResponse(BaseModel):
    results: List[ClaimResult]
    # True when the text held more claims than the service analyses per request.
    truncated: bool = False
