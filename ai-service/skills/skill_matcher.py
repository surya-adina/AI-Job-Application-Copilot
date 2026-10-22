"""Skill-level resume/job matching: an LLM proposes, deterministic checks verify.

1. One structured LLM call lists each job skill with its priority, whether the
   resume shows it, and a verbatim resume quote as evidence.
2. `check_claims` measures each claim against the resume: is the quote really
   in the resume, is it hedged ("currently learning", "no experience with"),
   does the quote name the skill (taxonomy alias), and how close is the skill
   to the quote in embedding space (pgvector, see semantic_matcher.py).
3. `decide` turns those measurements into matched/missing. Mode "llm" trusts
   the model's in_resume flag; mode "verified" requires the checks to pass.

Both modes read the same LLM output, so comparing them isolates the effect of
verification. Verifier settings are tuned on the dev split only
(evals/skill_matching_ab.py).
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, Field

from llm import RunMetadata, call_structured
from prompt_loader import load_prompt
from skills.extractor import WEAK_CONTEXT_PHRASES, canonical_skill, extract_known_skills, hedge_window
from skills.grounding import normalize_for_match
from skills.taxonomy import KNOWN_SKILLS

PROMPT_VERSION = "skill_match_v1"
ENDPOINT = "skill:match"

Mode = Literal["llm", "verified"]


class SkillClaim(BaseModel):
    skill: str
    priority: Literal["required", "preferred"]
    in_resume: bool
    resume_evidence: str | None


class SkillMatchLLMOutput(BaseModel):
    skills: list[SkillClaim]


class SkillDecision(BaseModel):
    skill: str
    priority: Literal["required", "preferred"]
    present: bool
    basis: str
    evidence: str | None = None


class SkillEvidence(BaseModel):
    mode: str = "none"
    resume_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    semantic_matches: list[dict] = Field(default_factory=list)
    skills: list[SkillDecision] = Field(default_factory=list)


@dataclass(frozen=True)
class VerifierConfig:
    # Skill name vs. a different skill named in the quote (e.g. "Postgres" vs "PostgreSQL").
    skill_similarity: float
    # Skill name vs. the whole quote sentence.
    evidence_similarity: float
    # Count a skill as present when an unambiguous taxonomy alias appears in the
    # resume outside hedged context, even if the model said it is missing.
    resume_alias_overrides: bool


# Chosen on the dev split by evals/skill_matching_ab.py (run 2026-10-22, gpt-4.1-mini,
# 3 repeats). skill_similarity 1.01 disables that check: it never helped on dev.
# On holdout this config scored F1 0.975 vs 0.984 for LLM-only, so the default
# mode stays "llm".
DEFAULT_CONFIG = VerifierConfig(skill_similarity=1.01, evidence_similarity=0.40, resume_alias_overrides=False)


class Similarity(Protocol):
    def best_candidate_matches(self, pairs: list[tuple[str, str]]) -> dict[str, tuple[str, float]]: ...

    def text_similarity(self, skill_texts: list[tuple[str, str]]) -> dict[tuple[str, str], float]: ...

    def close(self) -> None: ...


@dataclass
class ClaimCheck:
    skill: str
    priority: str
    llm_in_resume: bool
    evidence: str | None
    quote_found: bool = False
    weak_context: bool = False
    alias_in_evidence: bool = False
    # Found by an unambiguous taxonomy alias anywhere in the resume, outside hedged context.
    alias_in_resume: bool = False
    nearest_evidence_skill: str | None = None
    evidence_skill_similarity: float | None = None
    evidence_text_similarity: float | None = None


def get_mode() -> Mode:
    mode = os.getenv("SKILL_MATCH_MODE", "llm")
    return "verified" if mode == "verified" else "llm"


def skill_vocabulary() -> list[str]:
    return sorted(set(KNOWN_SKILLS.values()))


def merge_claims(claims: list[SkillClaim]) -> list[SkillClaim]:
    """Canonicalize names and merge duplicates: required beats preferred, and a
    positive claim with evidence beats a negative one."""
    merged: dict[str, SkillClaim] = {}

    for claim in claims:
        name = canonical_skill(claim.skill)
        if not name:
            continue

        claim = claim.model_copy(update={"skill": name})
        key = name.lower()
        existing = merged.get(key)

        if existing is None:
            merged[key] = claim
            continue

        priority = "required" if "required" in (existing.priority, claim.priority) else "preferred"
        positive = existing if existing.in_resume else claim
        merged[key] = positive.model_copy(update={"priority": priority})

    return list(merged.values())


def extract_skill_claims(resume_text: str, job_description: str, **llm_kwargs) -> tuple[list[SkillClaim], RunMetadata]:
    result = call_structured(
        endpoint=ENDPOINT,
        prompt_version=PROMPT_VERSION,
        system=load_prompt(PROMPT_VERSION),
        user=json.dumps(
            {
                "resume_text": resume_text,
                "job_description": job_description,
                "preferred_skill_names": skill_vocabulary(),
            }
        ),
        schema=SkillMatchLLMOutput,
        temperature=0,
        max_output_tokens=2000,
        **llm_kwargs,
    )
    return merge_claims(result.parsed.skills), result.metadata


def quote_context(quote: str, resume_text: str) -> str | None:
    """The quote plus up to 80 characters before it, or None if the quote is not in the resume."""
    normalized_resume = normalize_for_match(resume_text)
    normalized_quote = normalize_for_match(quote)

    if not normalized_quote:
        return None

    index = normalized_resume.find(normalized_quote)
    if index < 0:
        return None

    return hedge_window(normalized_resume, index) + normalized_quote


def check_claims(
    claims: list[SkillClaim],
    resume_text: str,
    similarity: Similarity | None = None,
) -> list[ClaimCheck]:
    resume_skills = set(extract_known_skills(resume_text, ignore_weak_context=True, include_ambiguous=False))
    checks = []

    for claim in claims:
        check = ClaimCheck(
            skill=claim.skill,
            priority=claim.priority,
            llm_in_resume=claim.in_resume,
            evidence=claim.resume_evidence if claim.in_resume else None,
            alias_in_resume=claim.skill in resume_skills,
        )

        if check.evidence:
            context = quote_context(check.evidence, resume_text)
            check.quote_found = context is not None
            check.weak_context = context is not None and any(phrase in context for phrase in WEAK_CONTEXT_PHRASES)
            check.alias_in_evidence = claim.skill in extract_known_skills(
                check.evidence, ignore_weak_context=False, include_ambiguous=True
            )

        checks.append(check)

    if similarity is not None:
        add_similarity(checks, similarity)

    return checks


def add_similarity(checks: list[ClaimCheck], similarity: Similarity) -> None:
    pending = [check for check in checks if check.quote_found and not check.weak_context]
    if not pending:
        return

    pairs = [
        (check.skill, candidate)
        for check in pending
        for candidate in extract_known_skills(check.evidence, ignore_weak_context=False)
        if candidate != check.skill
    ]
    nearest = similarity.best_candidate_matches(pairs)
    text_scores = similarity.text_similarity([(check.skill, check.evidence) for check in pending])

    for check in pending:
        if check.skill in nearest:
            check.nearest_evidence_skill, check.evidence_skill_similarity = nearest[check.skill]
        check.evidence_text_similarity = text_scores.get((check.skill, check.evidence))


def decide(check: ClaimCheck, mode: Mode, config: VerifierConfig = DEFAULT_CONFIG) -> tuple[bool, str]:
    if mode == "llm":
        return check.llm_in_resume, "llm"

    if config.resume_alias_overrides and check.alias_in_resume:
        return True, "resume_alias"
    if not check.llm_in_resume:
        return False, "not_in_resume"
    if not check.quote_found:
        return False, "rejected_quote_not_in_resume"
    if check.weak_context:
        return False, "rejected_hedged_context"
    if check.alias_in_evidence:
        return True, "evidence_alias"
    if (check.evidence_skill_similarity or 0) >= config.skill_similarity:
        return True, "evidence_semantic_skill"
    if (check.evidence_text_similarity or 0) >= config.evidence_similarity:
        return True, "evidence_semantic_text"
    return False, "rejected_unsupported_by_quote"


def build_evidence(
    checks: list[ClaimCheck],
    resume_text: str,
    mode: str,
    config: VerifierConfig = DEFAULT_CONFIG,
) -> SkillEvidence:
    decision_mode: Mode = "llm" if mode == "llm" else "verified"
    decisions = []
    semantic_matches = []

    for check in checks:
        present, basis = decide(check, decision_mode, config)
        decisions.append(
            SkillDecision(skill=check.skill, priority=check.priority, present=present, basis=basis, evidence=check.evidence)
        )

        if basis == "evidence_semantic_skill":
            semantic_matches.append(
                {
                    "job_skill": check.skill,
                    "resume_skill": check.nearest_evidence_skill,
                    "similarity": round(check.evidence_skill_similarity or 0, 3),
                }
            )
        elif basis == "evidence_semantic_text":
            semantic_matches.append(
                {
                    "job_skill": check.skill,
                    "resume_skill": check.evidence,
                    "similarity": round(check.evidence_text_similarity or 0, 3),
                }
            )

    def names(priority: str, present: bool | None = None) -> list[str]:
        return [
            decision.skill
            for decision in decisions
            if decision.priority == priority and (present is None or decision.present == present)
        ]

    return SkillEvidence(
        mode=mode,
        resume_skills=extract_known_skills(resume_text),
        required_skills=names("required"),
        preferred_skills=names("preferred"),
        missing_required_skills=names("required", present=False),
        missing_preferred_skills=names("preferred", present=False),
        semantic_matches=semantic_matches,
        skills=decisions,
    )


def default_similarity() -> Similarity:
    from skills.semantic_matcher import PgVectorSimilarity

    return PgVectorSimilarity()


def match_skills(
    resume_text: str,
    job_description: str,
    mode: Mode | None = None,
    similarity_factory: Callable[[], Similarity] = default_similarity,
    **llm_kwargs,
) -> tuple[SkillEvidence, RunMetadata]:
    mode = mode or get_mode()
    claims, metadata = extract_skill_claims(resume_text, job_description, **llm_kwargs)

    similarity = None
    effective_mode = mode
    if mode == "verified":
        try:
            similarity = similarity_factory()
        except Exception:
            # Without pgvector the alias and quote checks still run.
            effective_mode = "verified_without_vectors"

    try:
        checks = check_claims(claims, resume_text, similarity)
    except Exception:
        checks = check_claims(claims, resume_text, None)
        effective_mode = "verified_without_vectors"
    finally:
        if similarity is not None:
            similarity.close()

    return build_evidence(checks, resume_text, effective_mode), metadata


def check_to_dict(check: ClaimCheck) -> dict:
    return asdict(check)
