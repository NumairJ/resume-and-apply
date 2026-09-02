"""The gate that decides whether a page is worth sending to a model.

This exists to stop the pipeline before it spends tokens on a blog post or a careers
index. Each signal carries a weight and a human-readable reason, so a rejection can
tell the user *what was missing* rather than failing generically.
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

THRESHOLD = 3

# A posting invites an action, but "apply" is ordinary English — an article about
# machine learning says "apply to" constantly. Searching the body text for it scored a
# real blog post above the threshold. So the signal is *structural*: an actual link or
# button whose own label is an invitation to apply. Prose can't fake that.
APPLY_PATTERN = re.compile(
    r"\b(apply|submit (?:your )?application)\b",
    re.IGNORECASE,
)
# Control labels are short. A longer match is a sentence that happens to contain the
# word, not a button.
MAX_CONTROL_TEXT = 40
# Headings a posting has and an article does not.
SECTION_PATTERN = re.compile(
    r"\b(responsibilities|qualifications|requirements|what you.{0,3}ll do|"
    r"what we.{0,3}re looking for|about the role|who you are|your impact|"
    r"minimum qualifications|preferred qualifications|benefits)\b",
    re.IGNORECASE,
)
MIN_LENGTH = 600
MAX_LENGTH = 60_000


@dataclass
class Score:
    total: int = 0
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total >= THRESHOLD


def score(markup: str, text: str) -> Score:
    """Weigh the signals. `text` is the cleaned page body."""
    result = Score()
    soup = BeautifulSoup(markup, "html.parser")

    _award(
        result,
        weight=2,
        matched=_has_apply_control(soup),
        present="has an apply link or button",
        absent="no apply link or button",
    )

    sections = {match.group(0).lower() for match in SECTION_PATTERN.finditer(text)}
    _award(
        result,
        # Two or more posting-shaped headings is a strong signal; one is weak.
        weight=2 if len(sections) >= 2 else (1 if sections else 0),
        matched=bool(sections),
        present=f"has posting sections ({', '.join(sorted(sections)[:3])})",
        absent="no responsibilities or qualifications sections",
    )

    og_type = soup.find("meta", attrs={"property": "og:type"})
    _award(
        result,
        weight=1,
        matched=bool(og_type and "job" in str(og_type.get("content", "")).lower()),
        present="og:type declares a job",
        absent="og:type does not declare a job",
    )

    length = len(text)
    _award(
        result,
        weight=1,
        matched=MIN_LENGTH <= length <= MAX_LENGTH,
        present=f"body length {length} is plausible for a posting",
        absent=f"body length {length} is outside {MIN_LENGTH}-{MAX_LENGTH}",
    )

    return result


def _has_apply_control(soup: BeautifulSoup) -> bool:
    """A link or button actually labelled as an application action."""
    for control in soup.find_all(["a", "button"]):
        label = " ".join(control.get_text(" ").split())
        if label and len(label) <= MAX_CONTROL_TEXT and APPLY_PATTERN.search(label):
            return True
    return False


def _award(
    result: Score, *, weight: int, matched: bool, present: str, absent: str
) -> None:
    if matched and weight:
        result.total += weight
        result.reasons.append(present)
    else:
        result.missing.append(absent)
