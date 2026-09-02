"""The extraction pipeline, staged cheapest-first.

    1. ATS adapter        free    string match on the URL
    2. fetch              network one capped request
    3. JSON-LD            free    the site's own structured data
    4. scoring gate       free    stops here if this isn't a posting
    5. clean              free    bounds what stage 6 costs
    6. LLM                $$      last resort

Note that stage 1 runs *before* the fetch, inverting the order the spec describes. The
spec lists fetching first, but matching a domain is a string comparison and fetching is
a network round trip — and a recognised ATS URL never needs the HTML at all, because the
adapter calls the platform's JSON API directly. Fetching first would buy nothing.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from models.application import JobPosting
from repositories.application import JobPostingRepository
from schemas.application import JobPostingCreate
from services import fingerprint as fingerprint_service
from services.extraction import ats, jsonld, llm, scoring
from services.extraction.clean import clean_page
from services.extraction.fetch import FetchError, build_client, fetch
from services.llm.base import LLMProvider

TTL = timedelta(hours=24)
DUPLICATE_WINDOW = timedelta(days=90)


class NotAJobPosting(ValueError):
    """The page was retrieved but does not look like a job posting."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("This page does not look like a job posting")
        self.reasons = reasons


@dataclass
class ExtractionResult:
    posting: JobPosting
    duplicate: object | None = None
    cached: bool = False


def parse_url(
    url: str, provider: LLMProvider | None, client: httpx.Client
) -> JobPostingCreate:
    """Run the stages until one produces a posting."""
    if match := ats.find(url):
        adapter, identifiers = match
        return adapter.parse(url, identifiers, client)

    markup = fetch(url, client)

    if posting := jsonld.parse(markup, url):
        return posting

    text = clean_page(markup)
    result = scoring.score(markup, text)
    if not result.passed:
        raise NotAJobPosting(result.missing)

    if provider is None:
        # Reached only when every free stage has declined. The router turns this into
        # a 503 rather than pretending extraction failed.
        raise LLMUnavailable()

    return llm.extract(text, url, provider)


class LLMUnavailable(RuntimeError):
    """This page needs the model, and no provider is configured."""


def extract(
    session: Session,
    url: str,
    user_id: uuid.UUID,
    provider: LLMProvider | None = None,
    client: httpx.Client | None = None,
) -> ExtractionResult:
    """Extract, persist, and report any duplicate — the operation behind POST /jobs/extract."""
    repo = JobPostingRepository(session)

    # Opportunistic cleanup instead of a scheduler. This endpoint runs a few times a
    # day at most, and sweep-on-write has no background machinery to fail silently.
    repo.sweep_expired()

    now = datetime.now(timezone.utc)

    # The row keyed by source URL, still inside its TTL, *is* the extraction cache —
    # re-pasting a URL or refreshing the page costs nothing.
    existing = repo.get_by_source_url(url)
    if existing is not None and (
        existing.expires_at is None or existing.expires_at > now
    ):
        return ExtractionResult(
            posting=existing,
            duplicate=_find_duplicate(repo, user_id, existing.fingerprint, now),
            cached=True,
        )

    owns_client = client is None
    client = client or build_client()
    try:
        parsed = parse_url(url, provider, client)
    finally:
        if owns_client:
            client.close()

    posting = repo.create(
        **parsed.model_dump(),
        fingerprint=fingerprint_service.fingerprint(
            parsed.company, parsed.title, parsed.location
        ),
        # Provisional until something references it. Saving an application clears this.
        expires_at=now + TTL,
    )

    return ExtractionResult(
        posting=posting,
        duplicate=_find_duplicate(repo, user_id, posting.fingerprint, now),
    )


def _find_duplicate(
    repo: JobPostingRepository,
    user_id: uuid.UUID,
    fingerprint: str,
    now: datetime,
) -> object | None:
    """The most recent matching application inside the warning window.

    Only applications count — an extracted-but-abandoned posting is not something the
    user "already applied to". Older than the window is allowed silently, because
    reapplying after a rejection is legitimate.
    """
    cutoff = now - DUPLICATE_WINDOW
    for application in repo.find_duplicates_for_user(user_id, fingerprint):
        if application.created_at and application.created_at >= cutoff:
            return application
    return None


__all__ = [
    "DUPLICATE_WINDOW",
    "ExtractionResult",
    "FetchError",
    "LLMUnavailable",
    "NotAJobPosting",
    "TTL",
    "extract",
    "parse_url",
]
