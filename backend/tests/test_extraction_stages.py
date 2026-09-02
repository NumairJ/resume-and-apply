"""Tests for the individual pipeline stages.

No test performs network I/O — the Greenhouse adapter is driven through
`httpx.MockTransport` against a captured response.
"""

import json
from pathlib import Path

import httpx
import pytest

from models.enums import ExtractionMethod
from services.extraction import ats, jsonld, scoring
from services.extraction.ats.greenhouse import GreenhouseAdapter
from services.extraction.clean import clean_page, html_to_text
from services.extraction.fetch import FetchError, fetch

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Greenhouse adapter -----------------------------------------------------


@pytest.fixture
def greenhouse_payload() -> dict:
    return json.loads(fixture("greenhouse_job.json"))


@pytest.fixture
def greenhouse_client(greenhouse_payload: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("pay_transparency") == "true", (
            "pay_input_ranges is absent from the response without this parameter"
        )
        return httpx.Response(200, json=greenhouse_payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "url, board, job",
    [
        ("https://job-boards.greenhouse.io/gitlab/jobs/8503792002", "gitlab", "8503792002"),
        # The legacy host still appears in saved links and aggregators; it 301s to the
        # canonical one, so we must recognise it rather than fall through to scraping.
        ("https://boards.greenhouse.io/anthropic/jobs/4461450008", "anthropic", "4461450008"),
        ("https://job-boards.greenhouse.io/acme/jobs/123?gh_src=abc", "acme", "123"),
    ],
)
def test_match_accepts_greenhouse_urls(url: str, board: str, job: str) -> None:
    assert GreenhouseAdapter().match(url) == {"board_token": board, "job_id": job}


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.lever.co/acme/abc-123",
        "https://example.com/careers/engineer",
        "https://job-boards.greenhouse.io/acme/jobs/not-a-number",
        "https://greenhouse.io/about",
    ],
)
def test_match_rejects_other_urls(url: str) -> None:
    assert GreenhouseAdapter().match(url) is None


def test_registry_finds_greenhouse() -> None:
    found = ats.find("https://job-boards.greenhouse.io/gitlab/jobs/8503792002")
    assert found is not None
    adapter, identifiers = found
    assert adapter.name == "greenhouse"
    assert identifiers["board_token"] == "gitlab"

    assert ats.find("https://example.com/careers/engineer") is None


def test_greenhouse_parses_captured_response(
    greenhouse_client: httpx.Client, greenhouse_payload: dict
) -> None:
    adapter = GreenhouseAdapter()
    url = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008"

    posting = adapter.parse(url, adapter.match(url), greenhouse_client)

    assert posting.company == greenhouse_payload["company_name"]
    assert posting.title == greenhouse_payload["title"]
    assert posting.location == greenhouse_payload["location"]["name"]
    assert posting.extraction_method is ExtractionMethod.ATS_GREENHOUSE
    # Greenhouse has no separate requirements field; inventing a split would be guesswork.
    assert posting.requirements is None


def test_greenhouse_description_is_decoded_exactly_once(
    greenhouse_client: httpx.Client, greenhouse_payload: dict
) -> None:
    """The bug the published docs would have caused.

    Greenhouse's docs render `content` as `&amp;lt;p&amp;gt;` and read as though it
    were double-encoded. It is escaped exactly once: unescaping twice would corrupt
    any literal ampersand, unescaping zero times leaves tags in the output.
    """
    assert "&lt;" in greenhouse_payload["content"], "fixture should hold escaped markup"

    adapter = GreenhouseAdapter()
    url = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008"
    posting = adapter.parse(url, adapter.match(url), greenhouse_client)

    assert posting.description
    for residue in ("&lt;", "&gt;", "&amp;", "&quot;", "&nbsp;", "<p>", "<div>"):
        assert residue not in posting.description, f"{residue!r} survived decoding"


def test_greenhouse_formats_salary_from_cents(greenhouse_client: httpx.Client) -> None:
    adapter = GreenhouseAdapter()
    url = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008"
    posting = adapter.parse(url, adapter.match(url), greenhouse_client)

    # min_cents 22280000 is $222,800 — not $22,280,000.
    assert posting.salary_range == "222,800 - 290,000 USD"


def test_greenhouse_http_error_becomes_fetch_error() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    )
    adapter = GreenhouseAdapter()
    url = "https://job-boards.greenhouse.io/acme/jobs/1"

    with pytest.raises(FetchError):
        adapter.parse(url, adapter.match(url), client)


# --- fetch ------------------------------------------------------------------


def test_fetch_rejects_oversized_pages_while_streaming() -> None:
    """The cap has to bite during streaming, not after the body is already in memory."""
    huge = b"<html>" + b"x" * 3_000_000

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=huge, headers={"content-type": "text/html"}
            )
        )
    )
    with pytest.raises(FetchError, match="exceeds"):
        fetch("https://example.com", client)


def test_fetch_rejects_non_html() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"a": 1}, headers={"content-type": "application/json"}
            )
        )
    )
    with pytest.raises(FetchError, match="expected HTML"):
        fetch("https://example.com", client)


def test_fetch_raises_on_upstream_error() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    )
    with pytest.raises(FetchError, match="503"):
        fetch("https://example.com", client)


# --- cleaning ---------------------------------------------------------------


def test_clean_strips_chrome_and_collapses_whitespace() -> None:
    markup = """
      <html><head><style>body{color:red}</style></head>
      <body>
        <nav>Home About Careers</nav>
        <script>track()</script>
        <!-- a comment -->
        <main><h1>Engineer</h1><p>Build     things.</p></main>
        <footer>© 2026 Example</footer>
      </body></html>
    """
    text = clean_page(markup)

    assert "Engineer" in text
    assert "Build things." in text
    for noise in ("track()", "color:red", "Home About Careers", "© 2026", "a comment"):
        assert noise not in text


def test_clean_bounds_a_real_page() -> None:
    """The cost argument for the LLM stage: a real page reduces to a few thousand tokens."""
    raw = fixture("careers_index.html")
    text = clean_page(raw)

    assert len(text) < len(raw) / 3
    # ~4 chars per token, so this is roughly a 6k-token ceiling.
    assert len(text) < 25_000


def test_html_to_text_resolves_entities() -> None:
    assert html_to_text("<p>Go &amp; Rust</p>") == "Go & Rust"


# --- JSON-LD ----------------------------------------------------------------


def test_jsonld_extracts_posting_from_graph() -> None:
    posting = jsonld.parse(fixture("jsonld_posting.html"), "https://example.com/x")

    assert posting is not None
    assert posting.company == "Northwind Systems, Inc."
    assert posting.title == "Senior Platform Engineer"
    assert posting.location == "Toronto, Ontario, CA"
    assert posting.employment_type == "FULL_TIME, CONTRACTOR"
    assert posting.salary_range == "145,000 - 185,000 CAD per year"
    assert posting.extraction_method is ExtractionMethod.JSONLD
    # url on the posting wins over the URL we were handed.
    assert posting.source_url.endswith("/senior-platform-engineer")


def test_jsonld_description_and_requirements_are_plain_text() -> None:
    posting = jsonld.parse(fixture("jsonld_posting.html"), "https://example.com/x")

    assert posting.description and "Kubernetes platform" in posting.description
    assert posting.requirements and "distributed systems" in posting.requirements
    for field in (posting.description, posting.requirements):
        assert "&lt;" not in field and "<li>" not in field


def test_jsonld_survives_a_malformed_sibling_block() -> None:
    """A broken analytics blob must not cost us a valid posting elsewhere on the page."""
    markup = """
      <script type="application/ld+json">{ "broken": , }</script>
      <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting","title":"Engineer",
         "hiringOrganization":{"name":"Acme"}}
      </script>
    """
    posting = jsonld.parse(markup, "https://example.com/x")
    assert posting is not None
    assert posting.company == "Acme"


def test_jsonld_returns_none_without_a_posting() -> None:
    assert jsonld.parse(fixture("blog_post.html"), "https://example.com/x") is None
    assert jsonld.parse("<html><body>nothing</body></html>", "https://x") is None


# --- scoring ----------------------------------------------------------------


def test_real_posting_passes_the_gate() -> None:
    markup = fixture("jsonld_posting.html")
    result = scoring.score(markup, clean_page(markup))

    assert result.passed
    assert result.reasons


@pytest.mark.parametrize("name", ["blog_post.html", "careers_index.html"])
def test_negatives_are_rejected_with_named_reasons(name: str) -> None:
    """The point of the gate: these must never reach the model."""
    markup = fixture(name)
    result = scoring.score(markup, clean_page(markup))

    assert not result.passed, f"{name} scored {result.total}, above the threshold"
    assert result.missing, "a rejection must say what was missing"


def test_short_page_fails_on_length() -> None:
    markup = "<html><body><p>Apply now</p></body></html>"
    result = scoring.score(markup, clean_page(markup))

    assert not result.passed
    assert any("body length" in reason for reason in result.missing)
