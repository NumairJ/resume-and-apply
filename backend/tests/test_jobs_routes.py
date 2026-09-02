"""Route and pipeline tests for job extraction.

Every outbound request is served by an `httpx.MockTransport`, so nothing here touches
the network.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import User
from repositories.application import ApplicationRepository, JobPostingRepository
from routers.jobs import get_http_client, get_optional_provider
from services.extraction.llm import ExtractedJob
from services.llm.fake import FakeLLMProvider

FIXTURES = Path(__file__).parent / "fixtures"

GREENHOUSE_URL = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008"
GREENHOUSE_API = "boards-api.greenhouse.io"

# Passes the scoring gate but carries no JSON-LD, so it can only be read by the model.
LLM_ONLY_PAGE = """
<html><head><title>Widget Engineer</title></head><body>
  <h1>Widget Engineer</h1>
  <h2>Responsibilities</h2>
  <p>{filler}</p>
  <h2>Qualifications</h2>
  <p>{filler}</p>
  <a href="/apply">Apply now</a>
</body></html>
""".format(filler="You will build and maintain widgets for our customers. " * 30)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def mock_client(pages: dict[str, str] | None = None) -> httpx.Client:
    """Serve the Greenhouse API from the captured fixture, and pages from `pages`."""
    pages = pages or {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == GREENHOUSE_API:
            return httpx.Response(200, json=json.loads(fixture("greenhouse_job.json")))
        body = pages.get(str(request.url))
        if body is None:
            return httpx.Response(404)
        return httpx.Response(
            200, text=body, headers={"content-type": "text/html; charset=utf-8"}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def wired(client: TestClient):
    """Attach a mock transport, and let a test swap in pages or a provider."""

    def configure(
        pages: dict[str, str] | None = None, provider: FakeLLMProvider | None = None
    ) -> TestClient:
        http = mock_client(pages)
        client.app.dependency_overrides[get_http_client] = lambda: http
        client.app.dependency_overrides[get_optional_provider] = lambda: provider
        return client

    return configure


# --- the ATS path -----------------------------------------------------------


def test_extract_greenhouse_posting(wired) -> None:
    response = wired().post("/jobs/extract", json={"url": GREENHOUSE_URL})
    assert response.status_code == 200

    job = response.json()["job"]
    assert job["company"] == "Anthropic"
    assert job["extraction_method"] == ExtractionMethod.ATS_GREENHOUSE.value
    assert job["salary_range"] == "222,800 - 290,000 USD"
    assert response.json()["duplicate"] is None
    assert response.json()["cached"] is False


def test_extracted_description_carries_no_markup(wired) -> None:
    """Guards the encoding trap Greenhouse's own docs would have led us into."""
    response = wired().post("/jobs/extract", json={"url": GREENHOUSE_URL})
    description = response.json()["job"]["description"]

    assert description
    for residue in ("&lt;", "&gt;", "&amp;", "<p>", "<div>"):
        assert residue not in description


def test_extraction_sets_a_provisional_ttl(wired, session: Session) -> None:
    wired().post("/jobs/extract", json={"url": GREENHOUSE_URL})

    posting = JobPostingRepository(session).get_by_source_url(GREENHOUSE_URL)
    assert posting is not None
    assert posting.expires_at is not None
    # Provisional until an application references it.
    assert posting.expires_at > datetime.now(timezone.utc) + timedelta(hours=23)


# --- caching ----------------------------------------------------------------


def test_second_extract_of_the_same_url_is_cached(wired, session: Session) -> None:
    """The row keyed by source URL *is* the extraction cache — re-pasting costs nothing."""
    test_client = wired()

    first = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()
    second = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()

    assert first["cached"] is False
    assert second["cached"] is True
    assert first["job"]["id"] == second["job"]["id"]
    assert len(JobPostingRepository(session).list()) == 1


def test_expired_row_is_re_extracted(wired, session: Session) -> None:
    test_client = wired()
    test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL})

    repo = JobPostingRepository(session)
    posting = repo.get_by_source_url(GREENHOUSE_URL)
    repo.update(posting, expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    session.commit()

    again = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()
    assert again["cached"] is False


# --- the JSON-LD path -------------------------------------------------------


def test_extract_uses_jsonld_without_a_provider(wired) -> None:
    """No provider configured, and it still works — the free stages carry it."""
    url = "https://careers.example.com/jobs/platform"
    response = wired(pages={url: fixture("jsonld_posting.html")}).post(
        "/jobs/extract", json={"url": url}
    )

    assert response.status_code == 200
    job = response.json()["job"]
    assert job["extraction_method"] == ExtractionMethod.JSONLD.value
    assert job["company"] == "Northwind Systems, Inc."


# --- the gate ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["blog_post.html", "careers_index.html"])
def test_non_posting_is_rejected_before_the_model(wired, name: str) -> None:
    url = f"https://example.com/{name}"
    provider = FakeLLMProvider()

    response = wired(pages={url: fixture(name)}, provider=provider).post(
        "/jobs/extract", json={"url": url}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["reasons"], "the user should be told what was missing"
    # The whole point of the gate: no tokens were spent.
    assert provider.prompts == []


def test_unreachable_page_is_a_502(wired) -> None:
    response = wired().post("/jobs/extract", json={"url": "https://example.com/gone"})
    assert response.status_code == 502


# --- the LLM path -----------------------------------------------------------


def test_llm_stage_used_when_nothing_cheaper_works(wired) -> None:
    url = "https://example.com/widget-engineer"
    provider = FakeLLMProvider(
        [ExtractedJob(company="Widget Co", title="Widget Engineer", location="Remote")]
    )

    response = wired(pages={url: LLM_ONLY_PAGE}, provider=provider).post(
        "/jobs/extract", json={"url": url}
    )

    assert response.status_code == 200
    job = response.json()["job"]
    assert job["company"] == "Widget Co"
    assert job["extraction_method"] == ExtractionMethod.LLM.value
    # The prompt received cleaned text, not raw markup.
    assert len(provider.prompts) == 1
    assert "<html>" not in provider.prompts[0]


def test_page_needing_the_model_without_one_is_a_503(wired) -> None:
    """Distinct from 422 and 502 — the page was fine, we just can't read it."""
    url = "https://example.com/widget-engineer"
    response = wired(pages={url: LLM_ONLY_PAGE}).post("/jobs/extract", json={"url": url})

    assert response.status_code == 503
    assert "provider" in response.json()["detail"].lower()


# --- duplicates -------------------------------------------------------------


def test_duplicate_warning_names_the_prior_application(
    wired, session: Session, user: User
) -> None:
    test_client = wired()
    first = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()

    posting = JobPostingRepository(session).get(first["job"]["id"])
    ApplicationRepository(session).create(
        user_id=user.id,
        job_posting_id=posting.id,
        status=ApplicationStatus.REJECTED,
    )
    session.commit()

    again = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()

    assert again["duplicate"] is not None
    assert again["duplicate"]["status"] == ApplicationStatus.REJECTED.value
    assert again["duplicate"]["company"] == "Anthropic"


def test_no_warning_without_an_application(wired, session: Session) -> None:
    """An extracted-but-abandoned posting is not something the user applied to."""
    test_client = wired()
    test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL})

    again = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()
    assert again["duplicate"] is None


def test_old_application_does_not_warn(wired, session: Session, user: User) -> None:
    """Beyond the window it is silent — reapplying after a rejection is legitimate."""
    test_client = wired()
    first = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()

    posting = JobPostingRepository(session).get(first["job"]["id"])
    application = ApplicationRepository(session).create(
        user_id=user.id, job_posting_id=posting.id, status=ApplicationStatus.REJECTED
    )
    application.created_at = datetime.now(timezone.utc) - timedelta(days=120)
    session.commit()

    again = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()
    assert again["duplicate"] is None


# --- sweep and corrections --------------------------------------------------


def test_extract_sweeps_expired_unreferenced_postings(
    wired, session: Session, user: User
) -> None:
    repo = JobPostingRepository(session)
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    common = {
        "company": "Ghost",
        "title": "Engineer",
        "extraction_method": ExtractionMethod.LLM,
        "fingerprint": "ghost",
    }
    abandoned = repo.create(**common, source_url="https://x.test/abandoned", expires_at=stale)
    kept = repo.create(**common, source_url="https://x.test/kept", expires_at=stale)
    ApplicationRepository(session).create(user_id=user.id, job_posting_id=kept.id)
    session.commit()

    wired().post("/jobs/extract", json={"url": GREENHOUSE_URL})

    session.expire_all()
    assert repo.get(abandoned.id) is None
    assert repo.get(kept.id) is not None, "a referenced posting must survive"


def test_patch_applies_user_corrections(wired) -> None:
    test_client = wired()
    job = test_client.post("/jobs/extract", json={"url": GREENHOUSE_URL}).json()["job"]

    response = test_client.patch(
        f"/jobs/{job['id']}", json={"title": "Corrected Title", "location": "Toronto"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Corrected Title"
    assert response.json()["location"] == "Toronto"


def test_patch_unknown_job_is_404(wired) -> None:
    response = wired().patch(
        "/jobs/11111111-1111-1111-1111-111111111111", json={"title": "x"}
    )
    assert response.status_code == 404
