"""Route logic tests. Each route exposes a run_* function that takes the
request model plus llm kwargs, so these run without a server or API key."""

from routes.analysis import AnalyzeRequest, run_analysis
from routes.cover_letter import CoverLetterRequest, run_cover_letter
from routes.interview_prep import InterviewPrepRequest, run_interview_prep
from skills.llm_job_requirements import extract_job_requirements_llm
from tests.fakes import FakeClient, ok

RESUME = (
    "Software engineer. Built a FastAPI service with PostgreSQL and pgvector for semantic search. "
    "Shipped a Next.js dashboard used by 40 internal users. Wrote evaluation pipelines for LLM prompts."
)
JOB = (
    "Applied AI Engineer. Requirements: Python, FastAPI, PostgreSQL, LLM evaluation. "
    "Preferred: Kubernetes, AWS. You will build agentic workflows with tool calling."
)

LLM_KWARGS = dict(model="gpt-4o-mini", max_retries=1, sleep=lambda _s: None)


def stub_skill_matcher(resume_text, job_description, **_kwargs):
    from llm import RunMetadata
    from skills.skill_matcher import SkillEvidence

    metadata = RunMetadata(
        endpoint="skill:match", model="gpt-4o-mini", prompt_version="skill_match_v1", latency_ms=1,
        tokens_in=1, tokens_out=1, total_tokens=2, retries=0, status="SUCCESS",
    )
    return SkillEvidence(mode="llm", required_skills=["Python"]), metadata


def test_analysis_clamps_score_and_dedupes():
    client = FakeClient(
        ok(
            {
                "score": 140,
                "matched_skills": ["Python", "python", " FastAPI "],
                "missing_skills": ["Kubernetes"],
                "strengths": ["a", "b", "c", "d"],
                "weaknesses": [],
                "recommendations": ["x"],
            }
        )
    )

    response = run_analysis(
        AnalyzeRequest(resume_text=RESUME, job_description=JOB), skill_matcher=stub_skill_matcher, client=client, **LLM_KWARGS
    )

    assert response.analysis.score == 100
    assert response.analysis.matched_skills == ["Python", "FastAPI"]
    assert len(response.analysis.strengths) == 3
    assert response.evidence.required_skills == ["Python"]
    assert [run.endpoint for run in response.runs] == ["skill:match"]
    assert response.metadata.endpoint == "/analyze"


def test_cover_letter_assembles_and_flags_invented_quotes():
    client = FakeClient(
        ok(
            {
                "paragraphs": [
                    {
                        "text": "I'm applying for the Applied AI Engineer role.",
                        "supporting_resume_quotes": [],
                    },
                    {
                        "text": "I built a FastAPI service with pgvector search.",
                        "supporting_resume_quotes": ["Built a FastAPI service with PostgreSQL and pgvector"],
                    },
                    {
                        "text": "I have led Kubernetes migrations at [Company].",
                        "supporting_resume_quotes": ["Led Kubernetes migrations"],
                    },
                ],
                "closing_sentence": "Thank you for your time.",
            }
        )
    )

    response = run_cover_letter(CoverLetterRequest(resume_text=RESUME, job_description=JOB), client=client, **LLM_KWARGS)

    assert response.content.startswith("Dear Hiring Manager,\n\n")
    assert response.content.endswith("Thank you for your time.")
    assert response.grounding.quotes_checked == 2
    assert response.grounding.unsupported_quotes == ["Led Kubernetes migrations"]
    assert response.grounding.placeholders == ["[Company]"]
    assert response.metadata.prompt_version == "cover_letter_v2"


def test_interview_prep_trims_to_expected_counts():
    question = {"question": "q", "why_it_matters": "w", "suggested_focus": "f"}
    client = FakeClient(
        ok(
            {
                "technical_questions": [question] * 7,
                "behavioral_questions": [question] * 3,
                "project_questions": [question] * 3,
                "preparation_tips": ["t"] * 6,
            }
        )
    )

    response = run_interview_prep(InterviewPrepRequest(resume_text=RESUME, job_description=JOB), client=client, **LLM_KWARGS)

    assert len(response.technical_questions) == 5
    assert len(response.preparation_tips) == 5


def test_llm_requirements_removes_case_insensitive_overlap():
    client = FakeClient(ok({"required_skills": ["Python", "Go Lang"], "preferred_skills": ["python", "AWS"]}))

    requirements = extract_job_requirements_llm(JOB, client=client, **LLM_KWARGS)

    assert requirements == {"required_skills": ["Python", "Go"], "preferred_skills": ["AWS"]}


def test_resume_review_returns_shared_metadata():
    from routes.resume_review import ResumeReviewRequest, run_resume_review

    client = FakeClient(
        ok(
            {
                "summary": "Solid backend fit.",
                "suggestions": [
                    {
                        "priority": "HIGH",
                        "title": "Quantify the evaluation work",
                        "target_section": "Experience",
                        "why": "The job emphasizes LLM evaluation.",
                        "evidence": ["Wrote evaluation pipelines for LLM prompts."],
                        "action": "Add how many prompts or cases the pipeline covered.",
                    }
                ],
                "growth_areas": ["Kubernetes"],
                "warnings": [],
            }
        )
    )

    response = run_resume_review(
        ResumeReviewRequest(resume_text=RESUME, job_description=JOB, analysis={}, evidence={}),
        client=client,
        **LLM_KWARGS,
    )

    assert response.review.suggestions[0].priority == "HIGH"
    assert response.metadata.endpoint == "/resume-review"
    assert response.metadata.retries == 0


def test_unknown_or_path_like_prompt_version_returns_400():
    from fastapi.testclient import TestClient

    import main

    from tests.conftest import TEST_SERVICE_TOKEN

    client = TestClient(main.app, headers={"X-Service-Token": TEST_SERVICE_TOKEN})

    for version in ["analysis_v99", "../prompts/analysis_v1"]:
        response = client.post(
            "/analyze",
            json={"resume_text": RESUME, "job_description": JOB, "prompt_version": version},
        )
        assert response.status_code == 400
        assert "Unknown prompt version" in response.json()["detail"]["message"]
