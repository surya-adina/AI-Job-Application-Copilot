import os

import pytest

from llm import LLMCallError, RunMetadata
from routes.analysis import AnalyzeRequest, run_skill_matching
from skills.extractor import canonical_skill, extract_known_skills
from skills.skill_matcher import (
    DEFAULT_CONFIG,
    SkillClaim,
    VerifierConfig,
    build_evidence,
    check_claims,
    decide,
    match_skills,
    merge_claims,
)
from tests.fakes import FakeClient, ok

RESUME = (
    "Backend engineer. Built FastAPI services on Postgres and containerized them with Docker. "
    "Deployed to AWS ECS. No professional experience with Kubernetes. Currently learning Rust."
)

LLM_KWARGS = dict(model="gpt-4o-mini", max_retries=1, sleep=lambda _s: None)


class FakeSimilarity:
    def __init__(self, skill_scores=None, text_scores=None):
        self.skill_scores = skill_scores or {}
        self.text_scores = text_scores or {}
        self.closed = False

    def best_candidate_matches(self, pairs):
        best = {}
        for skill, candidate in pairs:
            score = self.skill_scores.get((skill, candidate), 0.0)
            if skill not in best or score > best[skill][1]:
                best[skill] = (candidate, score)
        return best

    def text_similarity(self, skill_texts):
        return {pair: self.text_scores.get(pair[0], 0.0) for pair in skill_texts}

    def close(self):
        self.closed = True


def claim(skill, in_resume, evidence=None, priority="required"):
    return SkillClaim(skill=skill, priority=priority, in_resume=in_resume, resume_evidence=evidence)


# ---------- extractor ----------


def test_extractor_matches_symbol_suffixed_skills_and_skips_go_to():
    assert extract_known_skills("C#, C++ and .NET") == ["C#", "C++"]
    assert "Go" not in extract_known_skills("The go-to person for releases")


def test_machine_learning_does_not_hedge_the_next_skill():
    assert "PyTorch" in extract_known_skills("Machine learning with PyTorch")


def test_ambiguous_aliases_can_be_excluded():
    assert "Go" in extract_known_skills("ready to go")
    assert "Go" not in extract_known_skills("ready to go", include_ambiguous=False)


def test_canonical_skill():
    assert canonical_skill("LLM APIs") == "LLM"
    assert canonical_skill("Apache Kafka") == "Kafka"
    assert canonical_skill("Firebase") == "Firebase"


# ---------- claims and verification ----------


def test_merge_claims_canonicalizes_and_prefers_required_and_positive():
    merged = merge_claims(
        [
            claim("Postgres", False, priority="preferred"),
            claim("PostgreSQL", True, "FastAPI services on Postgres"),
        ]
    )
    assert len(merged) == 1
    assert merged[0].skill == "PostgreSQL"
    assert merged[0].priority == "required"
    assert merged[0].in_resume is True


def test_verification_rejects_invented_and_hedged_quotes():
    checks = check_claims(
        [
            claim("Kafka", True, "Built Kafka consumers"),  # not in the resume
            claim("Kubernetes", True, "Kubernetes"),  # preceded by "no professional experience with"
            claim("Docker", True, "containerized them with Docker"),
        ],
        RESUME,
        FakeSimilarity(),
    )
    verdicts = {check.skill: decide(check, "verified") for check in checks}

    assert verdicts["Kafka"] == (False, "rejected_quote_not_in_resume")
    assert verdicts["Kubernetes"] == (False, "rejected_hedged_context")
    assert verdicts["Docker"] == (True, "evidence_alias")

    # The LLM-only arm keeps whatever the model said.
    assert all(decide(check, "llm")[0] for check in checks)


def test_semantic_support_uses_thresholds():
    checks = check_claims(
        [claim("GCP", True, "Deployed to AWS ECS")],
        RESUME,
        FakeSimilarity(skill_scores={("GCP", "AWS"): 0.4}, text_scores={"GCP": 0.55}),
    )
    check = checks[0]
    assert check.nearest_evidence_skill == "AWS"

    strict = VerifierConfig(skill_similarity=0.78, evidence_similarity=0.6, resume_alias_overrides=False)
    loose = VerifierConfig(skill_similarity=0.78, evidence_similarity=0.5, resume_alias_overrides=False)
    assert decide(check, "verified", strict) == (False, "rejected_unsupported_by_quote")
    assert decide(check, "verified", loose) == (True, "evidence_semantic_text")


def test_resume_alias_override_is_configurable():
    check = check_claims([claim("Docker", False)], RESUME)[0]
    on = VerifierConfig(1.01, 1.01, resume_alias_overrides=True)
    off = VerifierConfig(1.01, 1.01, resume_alias_overrides=False)

    assert decide(check, "verified", on) == (True, "resume_alias")
    assert decide(check, "verified", off) == (False, "not_in_resume")


def test_build_evidence_splits_by_priority():
    checks = check_claims(
        [
            claim("FastAPI", True, "Built FastAPI services"),
            claim("Kubernetes", False),
            claim("Terraform", False, priority="preferred"),
        ],
        RESUME,
    )
    evidence = build_evidence(checks, RESUME, "llm")

    assert evidence.required_skills == ["FastAPI", "Kubernetes"]
    assert evidence.missing_required_skills == ["Kubernetes"]
    assert evidence.missing_preferred_skills == ["Terraform"]
    assert "Rust" not in evidence.resume_skills  # "currently learning"
    assert [skill.basis for skill in evidence.skills] == ["llm", "llm", "llm"]


# ---------- match_skills ----------

LLM_OUTPUT = {
    "skills": [
        {"skill": "FastAPI", "priority": "required", "in_resume": True, "resume_evidence": "Built FastAPI services"},
        {"skill": "Kafka", "priority": "preferred", "in_resume": True, "resume_evidence": "Kafka pipelines"},
    ]
}


def test_match_skills_verified_mode_uses_and_closes_similarity():
    similarity = FakeSimilarity()
    evidence, metadata = match_skills(
        RESUME, "Required: FastAPI. Preferred: Kafka.", mode="verified",
        similarity_factory=lambda: similarity, client=FakeClient(ok(LLM_OUTPUT)), **LLM_KWARGS,
    )

    assert evidence.mode == "verified"
    assert evidence.missing_preferred_skills == ["Kafka"]
    assert metadata.endpoint == "skill:match"
    assert similarity.closed


def test_match_skills_without_database_still_runs_quote_checks():
    def unavailable():
        raise RuntimeError("DATABASE_URL is not configured")

    evidence, _ = match_skills(
        RESUME, "Required: FastAPI. Preferred: Kafka.", mode="verified",
        similarity_factory=unavailable, client=FakeClient(ok(LLM_OUTPUT)), **LLM_KWARGS,
    )
    assert evidence.mode == "verified_without_vectors"
    assert evidence.missing_preferred_skills == ["Kafka"]


def test_skill_matching_failure_does_not_fail_analysis():
    metadata = RunMetadata(
        endpoint="skill:match", model="m", prompt_version="skill_match_v1", latency_ms=1,
        tokens_in=0, tokens_out=0, total_tokens=0, retries=2, status="FAILED", error_type="RateLimitError",
    )

    def failing(*_args, **_kwargs):
        raise LLMCallError("rate limited", "RateLimitError", metadata)

    evidence, runs = run_skill_matching(
        AnalyzeRequest(resume_text=RESUME, job_description=RESUME), skill_matcher=failing
    )
    assert evidence.mode == "failed"
    assert runs == [metadata]


def test_default_config_matches_dev_choice():
    assert DEFAULT_CONFIG.resume_alias_overrides is False


# ---------- pgvector (needs a local database; skipped otherwise) ----------


@pytest.mark.skipif(not os.getenv("PGVECTOR_TEST_DATABASE_URL"), reason="set PGVECTOR_TEST_DATABASE_URL to run")
def test_pgvector_best_match_query_runs_in_sql(monkeypatch):
    import psycopg

    from skills.semantic_matcher import PgVectorSimilarity

    connection = psycopg.connect(os.environ["PGVECTOR_TEST_DATABASE_URL"], autocommit=True)
    vectors = {"alpha": [1.0, 0.0], "alpha-ish": [0.9, 0.1], "beta": [0.0, 1.0]}

    with connection.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE \"SkillEmbedding\" (id text, skill text unique, embedding vector(2))")
        for skill, vector in vectors.items():
            cursor.execute(
                "INSERT INTO \"SkillEmbedding\" VALUES (gen_random_uuid()::text, %s, %s::vector)", (skill, str(vector))
            )

    monkeypatch.setattr("skills.semantic_matcher.ensure_skill_embeddings", lambda *_: None)
    similarity = PgVectorSimilarity(connection)
    best = similarity.best_candidate_matches([("alpha", "alpha-ish"), ("alpha", "beta")])
    similarity.close()

    assert best["alpha"][0] == "alpha-ish"
    assert best["alpha"][1] == pytest.approx(0.9939, abs=1e-3)
