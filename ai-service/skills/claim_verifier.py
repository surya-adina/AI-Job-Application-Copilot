"""Deterministic verification of claims against a resume.

A claim is a sentence about the candidate plus the verbatim resume quotes that
support it. A claim is supported only when:
  * every cited quote appears in the resume and is not hedged
    ("currently learning", "no experience with");
  * every known skill the claim names appears in those quotes;
  * every number the claim states ("40%", "2M", "3 years") appears in those quotes.

What this cannot catch: invented qualities without a skill or number in them
("secure", "led the team"). Those need a model-based judge; this layer is the
cheap check that never hallucinates itself.
"""

import re

from pydantic import BaseModel, Field

from skills.extractor import WEAK_CONTEXT_PHRASES, extract_known_skills, hedge_window
from skills.grounding import normalize_for_match


class Claim(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list, description="Verbatim quotes from the resume.")


class ClaimVerdict(BaseModel):
    text: str
    supported: bool
    reasons: list[str]
    skills: list[str]
    numbers: list[str]


NUMBER_PATTERN = re.compile(r"(?<![\w.])\$?\d+(?:[.,]\d+)*(?:\s?(?:%|percent|[kmb]\b|x\b|million|billion))?", re.IGNORECASE)


def extract_numbers(text: str) -> list[str]:
    numbers = []
    for match in NUMBER_PATTERN.finditer(text):
        value = match.group(0).strip()
        if value not in numbers:
            numbers.append(value)
    return numbers


def number_key(value: str) -> str:
    """'40 %', '40%' and '40 percent' compare equal; so do '2M' and '2 m'."""
    value = value.lower().replace(",", "").replace("$", "").replace("percent", "%").replace(" ", "")
    return value


def quote_problem(quote: str, resume_text: str) -> str | None:
    normalized_resume = normalize_for_match(resume_text)
    normalized_quote = normalize_for_match(quote)

    if not normalized_quote:
        return "empty_quote"

    index = normalized_resume.find(normalized_quote)
    if index < 0:
        return f"quote_not_in_resume: {quote}"

    context = hedge_window(normalized_resume, index) + normalized_quote
    if any(phrase in context for phrase in WEAK_CONTEXT_PHRASES):
        return f"quote_is_hedged: {quote}"

    return None


def verify_claim(claim: Claim, resume_text: str, require_evidence: bool = True) -> ClaimVerdict:
    # Ambiguous aliases ("go", "rag") are skipped in the claim text so ordinary
    # words are not treated as skill claims.
    skills = extract_known_skills(claim.text, ignore_weak_context=False, include_ambiguous=False)
    numbers = extract_numbers(claim.text)
    reasons = []

    valid_quotes = []
    for quote in claim.evidence:
        problem = quote_problem(quote, resume_text)
        if problem:
            reasons.append(problem)
        else:
            valid_quotes.append(quote)

    if not claim.evidence and (require_evidence or skills or numbers):
        reasons.append("no_evidence")

    evidence_text = " ".join(valid_quotes)
    evidence_skills = set(extract_known_skills(evidence_text, ignore_weak_context=False))
    evidence_numbers = {number_key(value) for value in extract_numbers(evidence_text)}

    if claim.evidence:
        reasons += [f"skill_not_in_evidence: {skill}" for skill in skills if skill not in evidence_skills]
        reasons += [f"number_not_in_evidence: {value}" for value in numbers if number_key(value) not in evidence_numbers]

    return ClaimVerdict(text=claim.text, supported=not reasons, reasons=reasons, skills=skills, numbers=numbers)


def verify_claims(claims: list[Claim], resume_text: str, require_evidence: bool = True) -> list[ClaimVerdict]:
    return [verify_claim(claim, resume_text, require_evidence) for claim in claims]


def skills_missing_from_resume(text: str, resume_text: str) -> list[str]:
    """Skills named in `text` (unambiguous aliases only) that the resume does not show."""
    resume_skills = set(extract_known_skills(resume_text))
    return [
        skill
        for skill in extract_known_skills(text, ignore_weak_context=False, include_ambiguous=False)
        if skill not in resume_skills
    ]
