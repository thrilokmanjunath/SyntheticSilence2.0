import uuid
from pydantic import BaseModel
from app.models.claim import ExtractedClaim, NormalizedClaim
from app.services.llm_provider import LLMProvider

class ClaimList(BaseModel):
    claims: list[ExtractedClaim]

class NormalizedResponse(BaseModel):
    normalized_text: str
    core_entity: str
    core_predicate: str

class ClaimService:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def extract_claims(self, source_text: str) -> list[ExtractedClaim]:
        """
        Extracts claims from raw source text using a structured LLM call.
        Opinions, questions and instructions are not claims and are skipped.
        """
        prompt = (
            "Extract the distinct, checkable factual claims from the text below.\n"
            "Rules:\n"
            "- A claim asserts something that could be confirmed or refuted from public sources.\n"
            "- Skip opinions, predictions, questions, instructions, greetings and vague statements.\n"
            "- Make each claim self-contained: replace pronouns and phrases like 'the company' or "
            "'this study' with the name they refer to, using the surrounding text. Never add facts "
            "that are not in the text.\n"
            "- Keep names, numbers and dates exactly as written. One assertion per claim; split "
            "'A and B did X' only when each part can be checked separately.\n"
            "- Do not repeat a claim.\n"
            "For each claim return: id (short unique string such as c1, c2), "
            "original_text (the self-contained claim), "
            "context (the sentence or clause it came from, verbatim). "
            'Return {"claims": []} when there are none.\n'
            f"<text>\n{source_text}\n</text>"
        )
        result = await self.llm_provider.generate_structured_output(prompt, ClaimList)

        # Do not trust model-provided ids: they must be unique and non-empty downstream.
        claims: list[ExtractedClaim] = []
        seen_texts: set[str] = set()
        for claim in result.claims:
            text = claim.original_text.strip()
            key = text.lower()
            if not text or key in seen_texts:
                continue
            seen_texts.add(key)
            claims.append(
                ExtractedClaim(id=f"c{len(claims) + 1}", original_text=text, context=claim.context.strip() or text)
            )
        return claims

    async def normalize_claim(self, claim: ExtractedClaim) -> NormalizedClaim:
        """
        Normalizes a claim's surface form to ensure cross-construction testing
        compares identical underlying semantic units.
        """
        prompt = (
            "Normalize the following claim to its simplest, most canonical form. "
            "Identify the core entity (the main subject) and core predicate "
            "(what is asserted about it). Keep both short, in plain words suitable "
            "for a literature search.\n"
            f"<text>\n{claim.original_text}\n</text>"
        )

        llm_response = await self.llm_provider.generate_structured_output(prompt, NormalizedResponse)

        return NormalizedClaim(
            id=str(uuid.uuid4()),
            extracted_claim_id=claim.id,
            normalized_text=llm_response.normalized_text,
            core_entity=llm_response.core_entity,
            core_predicate=llm_response.core_predicate
        )
