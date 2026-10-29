from typing import Optional
from pydantic import BaseModel
from app.models.schemas import InsufficiencySignal
from app.services.llm_provider import LLMProvider

class ExplanationOutput(BaseModel):
    explanation: str

def _fmt(value: Optional[float]) -> str:
    return "unavailable" if value is None else f"{value:.2f}"

class ExplanationService:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def generate_explanation(
        self, signal: InsufficiencySignal, claim_text: str, verdict_summary: Optional[str] = None
    ) -> str:
        """
        Generates a natural-language explanation of the score breakdown.
        verdict_summary is the already-decided verdict; the explanation must agree with it.
        """
        decided = (
            f"The verdict has already been decided: {verdict_summary}. Your explanation must be consistent with it.\n"
            if verdict_summary
            else ""
        )
        prompt = (
            decided +
            "You are explaining how well retrieved sources support a claim, using only the numbers below. "
            "Do not invent facts about the claim itself.\n"
            f"Claim: <text>{claim_text}</text>\n\n"
            "Signal breakdown (0 to 1):\n"
            f"- Evidence Coverage: {_fmt(signal.evidence_coverage)}\n"
            f"- Semantic Support (NLI Entailment): {_fmt(signal.semantic_support)}\n"
            f"- Contradiction Level: {_fmt(signal.contradiction_level)}\n"
            f"- Retrieval Confidence (Inverse Density): {_fmt(signal.retrieval_confidence)}\n"
            f"- Temporal Coverage (Post-Cutoff Ratio): {_fmt(signal.temporal_coverage)}\n"
            f"- Information Uncertainty (InfoNCE): {_fmt(signal.uncertainty)}\n"
            f"- Estimated Insufficiency Type (heuristic): {signal.construction_family_estimate}\n\n"
            "Write 2 sentences in plain language for a non-expert. State whether the sources back the claim up, "
            "push against it, or leave it unsettled, and name the main reason (for example high contradiction, "
            "mostly recent sources, or no sources found). Do not mention the numbers by name."
        )

        result = await self.llm_provider.generate_structured_output(prompt, ExplanationOutput)
        return result.explanation
