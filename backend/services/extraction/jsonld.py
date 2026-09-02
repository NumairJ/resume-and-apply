"""schema.org/JobPosting extraction.

When a page publishes JSON-LD it is authoritative — the site is telling us its own
structured data — so this path needs no model and costs nothing.
"""

import json
from typing import Any

from bs4 import BeautifulSoup

from models.enums import ExtractionMethod
from schemas.application import JobPostingCreate
from services.extraction.clean import html_to_text


def parse(markup: str, source_url: str) -> JobPostingCreate | None:
    """The first JobPosting block on the page, or None if there isn't one."""
    for block in _blocks(markup):
        if posting := _find_job_posting(block):
            return _to_schema(posting, source_url)
    return None


def _blocks(markup: str) -> list[Any]:
    """Every parseable ld+json block.

    Malformed blocks are skipped rather than fatal: pages routinely carry several, and
    one broken analytics blob shouldn't cost us a valid posting elsewhere on the page.
    """
    soup = BeautifulSoup(markup, "html.parser")
    parsed = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            parsed.append(json.loads(script.string or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return parsed


def _find_job_posting(node: Any) -> dict | None:
    """Walk a block looking for @type JobPosting, unwrapping @graph and arrays."""
    if isinstance(node, list):
        for item in node:
            if found := _find_job_posting(item):
                return found
        return None

    if not isinstance(node, dict):
        return None

    node_type = node.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if any(str(t).lower() == "jobposting" for t in types if t):
        return node

    return _find_job_posting(node.get("@graph", []))


def _to_schema(posting: dict, source_url: str) -> JobPostingCreate:
    description = posting.get("description")
    # description is routinely an HTML string even inside JSON-LD.
    text = html_to_text(description) if isinstance(description, str) else None

    return JobPostingCreate(
        company=_organisation(posting) or "Unknown",
        title=str(posting.get("title") or "Untitled role"),
        location=_location(posting),
        employment_type=_employment_type(posting),
        description=text,
        requirements=_text_or_none(posting.get("qualifications"))
        or _text_or_none(posting.get("experienceRequirements")),
        salary_range=_salary(posting.get("baseSalary")),
        source_url=str(posting.get("url") or source_url),
        raw_text=text,
        extraction_method=ExtractionMethod.JSONLD,
    )


def _text_or_none(value: Any) -> str | None:
    return html_to_text(value) if isinstance(value, str) and value.strip() else None


def _organisation(posting: dict) -> str | None:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        return _text_or_none(org.get("name"))
    return _text_or_none(org)


def _location(posting: dict) -> str | None:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return _text_or_none(location)

    address = location.get("address")
    if not isinstance(address, dict):
        return _text_or_none(address)

    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry")
        if isinstance(address.get("addressCountry"), str)
        else None,
    ]
    joined = ", ".join(str(part) for part in parts if part)
    return joined or None


def _employment_type(posting: dict) -> str | None:
    value = posting.get("employmentType")
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or None
    return _text_or_none(value)


def _salary(salary: Any) -> str | None:
    if not isinstance(salary, dict):
        return None

    currency = salary.get("currency") or ""
    value = salary.get("value")
    if not isinstance(value, dict):
        return f"{value} {currency}".strip() if value else None

    parts = [value.get("minValue"), value.get("maxValue")]
    present = [f"{part:,.0f}" if isinstance(part, int | float) else str(part) for part in parts if part is not None]
    if not present:
        single = value.get("value")
        return f"{single} {currency}".strip() if single else None

    unit = value.get("unitText")
    formatted = f"{' - '.join(present)} {currency}".strip()
    return f"{formatted} per {str(unit).lower()}" if unit else formatted
