"""Normalised fingerprint for soft duplicate detection.

The goal is that the same job, phrased differently across two sites, collides — while
two genuinely different roles at the same company do not. Erring toward collision is
the more damaging failure: it would warn a user away from a role they never applied to.
"""

import hashlib
import re

COMPANY_SUFFIXES = {
    "inc", "inc.", "llc", "l.l.c.", "ltd", "ltd.", "limited", "corp", "corp.",
    "corporation", "co", "co.", "company", "gmbh", "plc", "bv", "b.v.", "nv",
    "ab", "sa", "s.a.", "as", "oy", "pty", "pte", "srl", "spa", "group", "holdings",
}

# Rank and level noise. Two postings for the same work often differ only by these.
SENIORITY_TOKENS = {
    "senior", "sr", "sr.", "junior", "jr", "jr.", "staff", "principal", "lead",
    "entry", "entry-level", "mid", "mid-level", "associate", "i", "ii", "iii", "iv",
    "1", "2", "3", "4",
}

REMOTE_PATTERN = re.compile(r"\bremote\b|\banywhere\b|\bdistributed\b", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^\w\s-]")
_WHITESPACE = re.compile(r"\s+")


def normalize_company(company: str) -> str:
    tokens = _tokenize(company)
    # Only strip suffixes from the end — "Corp" leading a name is part of it.
    while tokens and tokens[-1] in COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_title(title: str) -> str:
    tokens = [token for token in _tokenize(title) if token not in SENIORITY_TOKENS]
    return " ".join(tokens)


def normalize_location(location: str | None) -> str:
    """A city token, or `remote`. Anything remote is remote regardless of the city."""
    if not location:
        return ""
    if REMOTE_PATTERN.search(location):
        return "remote"
    # "Toronto, Ontario, Canada" -> "toronto": the city is the discriminating part.
    city = location.split(",")[0]
    return " ".join(_tokenize(city))


def fingerprint(company: str, title: str, location: str | None) -> str:
    parts = [
        normalize_company(company),
        normalize_title(title),
        normalize_location(location),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _tokenize(value: str) -> list[str]:
    cleaned = _PUNCTUATION.sub(" ", value.lower())
    return _WHITESPACE.sub(" ", cleaned).strip().split()
