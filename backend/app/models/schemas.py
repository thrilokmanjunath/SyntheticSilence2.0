from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class ConstructionFamily(str, Enum):
    missing_evidence = "missing_evidence"
    retrieved_insufficient = "retrieved_insufficient"
    wrong_retrieval = "wrong_retrieval"
    contradictory = "contradictory"
    rare_valid = "rare_valid"
    long_tail = "long_tail"
    temporal_novelty = "temporal_novelty"
    ood = "ood"
    hallucination = "hallucination"
    ambiguous_claim = "ambiguous_claim"

class Evidence(BaseModel):
    id: str
    text: str
    source_url: Optional[str] = None
    publication_year: Optional[int] = None
    construction_family: ConstructionFamily
    # Where the source comes from; shown in the UI and used for dedupe across retrievers.
    kind: Literal["scholarly", "encyclopedia"] = "scholarly"
    title: Optional[str] = None
    # Claim-source embedding cosine similarity, set by the ranking stage.
    relevance: Optional[float] = None

class InsufficiencySignal(BaseModel):
    evidence_coverage: float
    semantic_support: float
    retrieval_confidence: Optional[float] = None
    contradiction_level: float
    temporal_coverage: Optional[float] = None
    representation_density: Optional[float] = None
    uncertainty: Optional[float] = None
    insufficiency_signal: Optional[float] = None
    construction_family_estimate: Optional[str] = None
    calibration_status: str = Field(default="NOT_CALIBRATED")
