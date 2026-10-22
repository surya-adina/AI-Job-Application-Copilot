import os

import pytest
from fastapi.testclient import TestClient

import main
from routes.resume_review import ResumeSuggestionDraft, ground_suggestion
from skills.claim_verifier import Claim, extract_numbers, verify_claim
from skills.resume_chunks import chunk_resume
from skills.safe_fetch import FetchError, RawResponse, fetch_page, html_to_text, resolve_target
from tests.conftest import TEST_SERVICE_TOKEN
from tests.fakes import FakeClient, ok
from tools import REGISTRY, ToolContext, ToolError, invoke

RESUME = """Jordan Lee
EXPERIENCE
- Built FastAPI microservices handling 2M requests/day for shipment tracking.
- Designed PostgreSQL schemas and cut p95 query latency by 40% with indexing.
- Containerized services with Docker and deployed to AWS ECS.
No experience with Kubernetes.
- 3 years of Python in production.
"""

LLM_KWARGS = dict(model="gpt-4o-mini", max_retries=1, sleep=lambda _s: None)

PUBLIC = {"jobs.example.com": ["93.184.216.34"]}


def fake_resolver(table):
    def resolve(hostname, _port):
        return table[hostname]

    return resolve


def page(status=200, body=b"", headers=None):
    return RawResponse(status=status, headers=headers or {"content-type": "text/html; charset=utf-8"}, chunks=[body])


# ---------- SSRF guard ----------


@pytest.mark.parametrize(
    "url, code",
    [
        ("file:///etc/passwd", "unsupported_scheme"),
        ("gopher://jobs.example.com/", "unsupported_scheme"),
        ("http://user:pw@jobs.example.com/", "credentials_in_url"),
        ("http://jobs.example.com:22/", "port_not_allowed"),
        ("http:///nohost", "missing_host"),
    ],
)
def test_url_shape_is_validated(url, code):
    with pytest.raises(FetchError) as caught:
        resolve_target(url, fake_resolver(PUBLIC))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.1.2.3"],
        ["172.16.0.9"],
        ["192.168.1.1"],
        ["169.254.169.254"],  # cloud metadata
        ["100.64.0.1"],  # carrier-grade NAT
        ["::1"],
        ["::ffff:127.0.0.1"],  # IPv4-mapped loopback
        ["fd00::1"],
        ["93.184.216.34", "10.0.0.1"],  # one bad answer is enough
    ],
)
def test_non_public_addresses_are_blocked(addresses):
    with pytest.raises(FetchError) as caught:
        resolve_target("http://jobs.example.com/", fake_resolver({"jobs.example.com": addresses}))
    assert caught.value.code == "blocked_address"


def test_connection_is_pinned_to_the_validated_ip():
    seen = []

    def opener(target):
        seen.append(target)
        return page(body=b"<p>" + b"Job text. " * 30 + b"</p>")

    fetch_page("https://jobs.example.com/role?id=7", resolver=fake_resolver(PUBLIC), opener=opener)
    assert (seen[0].ip, seen[0].hostname, seen[0].path) == ("93.184.216.34", "jobs.example.com", "/role?id=7")


def test_redirect_to_internal_address_is_blocked():
    table = {**PUBLIC, "internal.corp": ["10.0.0.5"]}

    def opener(target):
        return page(status=302, headers={"location": "http://internal.corp/admin"})

    with pytest.raises(FetchError) as caught:
        fetch_page("https://jobs.example.com/", resolver=fake_resolver(table), opener=opener)
    assert caught.value.code == "blocked_address"


def test_redirect_limit_and_size_and_content_type():
    loop = lambda _t: page(status=301, headers={"location": "/again"})  # noqa: E731
    with pytest.raises(FetchError, match="redirects"):
        fetch_page("https://jobs.example.com/", resolver=fake_resolver(PUBLIC), opener=loop)

    huge = lambda _t: RawResponse(200, {"content-type": "text/html"}, [b"x" * 1_000_000] * 3)  # noqa: E731
    with pytest.raises(FetchError) as caught:
        fetch_page("https://jobs.example.com/", resolver=fake_resolver(PUBLIC), opener=huge)
    assert caught.value.code == "too_large"

    pdf = lambda _t: page(headers={"content-type": "application/pdf"})  # noqa: E731
    with pytest.raises(FetchError) as caught:
        fetch_page("https://jobs.example.com/", resolver=fake_resolver(PUBLIC), opener=pdf)
    assert caught.value.code == "unsupported_content_type"


def test_html_to_text_drops_scripts_and_keeps_title():
    title, text = html_to_text(
        "<html><head><title> Backend Engineer </title><script>var x=1</script></head>"
        "<body><h1>Role</h1><p>Build APIs.</p><style>p{}</style><ul><li>Python</li></ul></body></html>"
    )
    assert title == "Backend Engineer"
    assert text == "Role\nBuild APIs.\nPython"


# ---------- claim verifier ----------


@pytest.mark.parametrize(
    "claim, supported, reason",
    [
        (Claim(text="Built FastAPI services handling 2M requests a day.", evidence=["Built FastAPI microservices handling 2M requests/day"]), True, None),
        (Claim(text="Cut PostgreSQL latency by 50%.", evidence=["Designed PostgreSQL schemas and cut p95 query latency by 40% with indexing"]), False, "number_not_in_evidence: 50%"),
        (Claim(text="Ran Kubernetes clusters.", evidence=["Kubernetes"]), False, "quote_is_hedged: Kubernetes"),
        (Claim(text="Experienced with Docker.", evidence=["Built FastAPI microservices"]), False, "skill_not_in_evidence: Docker"),
        (Claim(text="Led a Kafka migration.", evidence=["Led a Kafka migration"]), False, "quote_not_in_resume: Led a Kafka migration"),
        (Claim(text="3 years of Python.", evidence=["3 years of Python in production"]), True, None),
        (Claim(text="Shipped many services.", evidence=[]), False, "no_evidence"),
    ],
)
def test_verify_claim(claim, supported, reason):
    verdict = verify_claim(claim, RESUME)
    assert verdict.supported is supported
    if reason:
        assert reason in verdict.reasons


def test_claims_without_facts_can_skip_evidence():
    assert verify_claim(Claim(text="I am excited about this role.", evidence=[]), RESUME, require_evidence=False).supported
    assert not verify_claim(Claim(text="I know Docker.", evidence=[]), RESUME, require_evidence=False).supported


def test_extract_numbers_ignores_version_suffixes():
    assert extract_numbers("cut latency 40 % across v2 APIs, saving $1,200") == ["40 %", "$1,200"]


# ---------- resume chunks ----------


def test_chunk_resume_keeps_exact_offsets_and_skips_headings():
    chunks = chunk_resume(RESUME)
    assert all(RESUME[chunk.start : chunk.end] == chunk.text for chunk in chunks)
    assert chunks[0].text.startswith("Built FastAPI")
    assert "EXPERIENCE" not in [chunk.text for chunk in chunks]


def test_long_lines_are_split_into_sentences():
    text = "Summary line. " + ("Built reliable data pipelines for analytics teams. " * 12)
    chunks = chunk_resume(text)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 400 for chunk in chunks)


# ---------- resume review grounding ----------


def test_review_suggestion_for_missing_skill_gets_caveat():
    suggestion = ResumeSuggestionDraft(
        priority="HIGH", title="Add Kubernetes", target_section="Skills", why="Required.", evidence=["JD"],
        action="Get hands-on Kubernetes practice.",
    )
    grounded = ground_suggestion(suggestion, RESUME)
    assert grounded.unsupported_skills == ["Kubernetes"]
    assert "Only add Kubernetes" in grounded.action


def test_review_suggestion_using_go_as_a_word_is_left_alone():
    suggestion = ResumeSuggestionDraft(
        priority="LOW", title="Go beyond tool lists", target_section="Experience", why="w", evidence=["e"],
        action="Describe outcomes.",
    )
    grounded = ground_suggestion(suggestion, RESUME)
    assert grounded.unsupported_skills == []
    assert grounded.title == "Go beyond tool lists"


# ---------- registry and tools ----------


def test_every_tool_has_input_and_output_schemas():
    assert set(REGISTRY) == {
        "fetch_job_posting", "extract_requirements", "match_skills", "search_resume_evidence", "draft_section", "verify_claims",
    }
    for tool in REGISTRY.values():
        schema = tool.schema()
        assert schema["description"]
        assert schema["input_schema"]["type"] == "object"
        assert schema["output_schema"]["type"] == "object"


def test_draft_section_maps_evidence_ids_to_text():
    client = FakeClient(
        ok(
            {
                "text": "Built FastAPI microservices handling 2M requests/day.",
                "claims": [{"text": "Built FastAPI services handling 2M requests/day.", "evidence_ids": [0, 9]}],
            }
        )
    )
    result = invoke(
        "draft_section",
        {
            "section": "resume_bullet",
            "instructions": "Highlight API scale.",
            "job_description": "Backend engineer building high-volume FastAPI services with PostgreSQL.",
            "evidence": [{"id": 0, "text": "Built FastAPI microservices handling 2M requests/day for shipment tracking."}],
        },
        ToolContext(llm_kwargs=dict(client=client, **LLM_KWARGS)),
    )

    assert result.output.unknown_evidence_ids == [9]
    assert result.output.claims[0].evidence == ["Built FastAPI microservices handling 2M requests/day for shipment tracking."]
    assert [run.endpoint for run in result.runs] == ["tool:draft_section"]


def test_fetch_job_posting_rejects_pages_without_text():
    from skills.safe_fetch import FetchedPage

    fetcher = lambda url: FetchedPage(url=url, content_type="text/html", title="App", text="Loading...", bytes_read=10, redirects=0)  # noqa: E731
    with pytest.raises(ToolError) as caught:
        invoke("fetch_job_posting", {"url": "https://jobs.example.com/1"}, ToolContext(fetcher=fetcher))
    assert caught.value.code == "no_text"


# ---------- HTTP routes ----------

http = TestClient(main.app, headers={"X-Service-Token": TEST_SERVICE_TOKEN})


def test_tools_route_lists_tools():
    response = http.get("/tools")
    assert response.status_code == 200
    assert len(response.json()) == 6


def test_tools_route_runs_verify_claims():
    response = http.post(
        "/tools/verify_claims",
        json={
            "resume_text": RESUME,
            "claims": [
                {"text": "Cut latency by 40%.", "evidence": ["cut p95 query latency by 40% with indexing"]},
                {"text": "Ran Kafka in production.", "evidence": []},
            ],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["output"]["supported_count"] == 1
    assert body["output"]["verdicts"][1]["reasons"] == ["no_evidence"]


def test_tools_route_errors():
    assert http.post("/tools/nope", json={}).status_code == 404
    assert http.post("/tools/verify_claims", json={"claims": []}).status_code == 422

    blocked = http.post("/tools/fetch_job_posting", json={"url": "http://127.0.0.1/"})
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "blocked_address"


# ---------- pgvector resume search (needs a local database) ----------


@pytest.mark.skipif(not os.getenv("PGVECTOR_TEST_DATABASE_URL"), reason="set PGVECTOR_TEST_DATABASE_URL to run")
def test_resume_search_is_scoped_and_ordered(monkeypatch):
    import psycopg

    from skills import resume_chunks

    vectors = {"python": [1.0, 0.0, 0.0], "docker": [0.0, 1.0, 0.0], "postgres": [0.0, 0.0, 1.0]}

    def fake_embed(texts):
        result = []
        for text in texts:
            lowered = text.lower()
            key = next((name for name in vectors if name in lowered), "python")
            result.append(vectors[key])
        return result

    monkeypatch.setattr(resume_chunks, "embed", fake_embed)
    connection = psycopg.connect(os.environ["PGVECTOR_TEST_DATABASE_URL"], autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute(
            'CREATE TEMP TABLE "ResumeChunk" (id text, "resumeId" text, "chunkIndex" int, text text, '
            '"startOffset" int, "endOffset" int, "contentHash" text, embedding vector(3))'
        )

    resume = "Wrote Python services for billing.\nPackaged everything with Docker images.\nTuned Postgres queries for reports.\n"
    other = "Wrote Docker tooling for a different person entirely.\n"
    assert resume_chunks.index_resume(connection, "r1", resume) == 3
    assert resume_chunks.index_resume(connection, "r2", other) == 1

    matches = resume_chunks.search_resume(connection, "r1", "docker", k=2)
    connection.close()

    assert matches[0].text == "Packaged everything with Docker images."
    assert matches[0].similarity == pytest.approx(1.0)
    assert all("different person" not in match.text for match in matches)
