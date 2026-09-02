import html
import re

import httpx

from models.enums import ExtractionMethod
from schemas.application import JobPostingCreate
from services.extraction.ats.base import ATSAdapter
from services.extraction.clean import html_to_text
from services.extraction.fetch import FetchError

API_BASE = "https://boards-api.greenhouse.io/v1/boards"

# job-boards.greenhouse.io is canonical; boards.greenhouse.io 301-redirects to it but
# is still what most saved links and job aggregators contain.
URL_PATTERN = re.compile(
    r"^https?://(?:job-)?boards\.greenhouse\.io/(?P<board_token>[^/]+)/jobs/(?P<job_id>\d+)",
    re.IGNORECASE,
)

# Greenhouse has no employment-type field; boards that publish one do it as a custom
# metadata entry, so match on the field's name.
EMPLOYMENT_TYPE_NAMES = {"employment type", "job type", "employment status"}


class GreenhouseAdapter(ATSAdapter):
    name = "greenhouse"
    method = ExtractionMethod.ATS_GREENHOUSE

    def match(self, url: str) -> dict[str, str] | None:
        found = URL_PATTERN.match(url.strip())
        return found.groupdict() if found else None

    def parse(
        self, url: str, identifiers: dict[str, str], client: httpx.Client
    ) -> JobPostingCreate:
        endpoint = (
            f"{API_BASE}/{identifiers['board_token']}/jobs/{identifiers['job_id']}"
        )
        try:
            # pay_transparency is opt-in; without it pay_input_ranges is absent entirely.
            response = client.get(endpoint, params={"pay_transparency": "true"})
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise FetchError(
                f"Greenhouse returned {exc.response.status_code} for this posting"
            ) from exc
        except httpx.HTTPError as exc:
            raise FetchError(f"could not reach the Greenhouse API: {exc}") from exc
        except ValueError as exc:
            raise FetchError("Greenhouse returned a malformed response") from exc

        description = _description(payload.get("content"))

        return JobPostingCreate(
            company=payload.get("company_name") or identifiers["board_token"],
            title=payload.get("title") or "Untitled role",
            location=(payload.get("location") or {}).get("name"),
            employment_type=_employment_type(payload.get("metadata")),
            description=description,
            # Greenhouse ships one HTML blob with no separate requirements field.
            # Splitting it heuristically would be guesswork presented as structure.
            requirements=None,
            salary_range=_salary_range(payload.get("pay_input_ranges")),
            source_url=payload.get("absolute_url") or url,
            raw_text=description,
            extraction_method=self.method,
        )


def _description(content: str | None) -> str | None:
    """Decode Greenhouse's `content` field into plain text.

    The field is HTML with its entities escaped exactly once, arriving as
    `&lt;p&gt;Text&lt;/p&gt;`. Greenhouse's published docs render this as
    `&amp;lt;p&amp;gt;` and read as though it were double-encoded; unescaping twice on
    that basis mangles any literal ampersand in the posting.

    `html_to_text` does the single unescape — the same handling schema.org
    descriptions need, so it lives in one place rather than being repeated per source.
    """
    if not content:
        return None
    return html_to_text(content)


def _employment_type(metadata: list[dict] | None) -> str | None:
    for field in metadata or []:
        if str(field.get("name", "")).strip().lower() in EMPLOYMENT_TYPE_NAMES:
            value = field.get("value")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if value:
                return str(value)
    return None


def _salary_range(ranges: list[dict] | None) -> str | None:
    """Format the first pay range. Amounts are in cents, not currency units."""
    if not ranges:
        return None
    first = ranges[0]
    minimum, maximum = first.get("min_cents"), first.get("max_cents")
    if minimum is None and maximum is None:
        return None

    currency = first.get("currency_type") or ""
    parts = [f"{value / 100:,.0f}" for value in (minimum, maximum) if value is not None]
    return f"{' - '.join(parts)} {currency}".strip()
