"""Reference labels, the index that resolves them, and the comparisons the checks use.

The labelling scheme lives here and **only** here. The prompt renderer and the guardrail
chain both import it, so the labels the model is shown are by construction the same
labels the checks resolve. If these two ever drifted apart, every generation would look
like fabrication.

    E1      the first experience
    E1B2    the second bullet of the first experience
    P1      the first project
    P1B2    the second bullet of the first project

Labels are 1-based because they appear in a prompt, and a model reading "E0" as the
first item is an avoidable stumble.

The other half of this module is the profile's own text, folded for comparison. Two
checks ask questions of it — "is this skill something the candidate actually claims?"
and "is this figure one they actually recorded?" — and both are answered against what
the user wrote rather than against a curated list, because a curated list is exactly
what kept rejecting their own words.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from schemas.profile import ExperienceRead, Profile, ProjectRead

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# A figure with optional currency mark, thousands separators, decimals, and a magnitude
# or unit suffix: 40%, 1.2M, $500k, 3x, 12,000.
_NUMERIC = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:%|[kKmMbB]\b|[xX]\b)?")

_MAGNITUDES = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}

# Figures that assert nothing on their own, excluded so the metric check stays signal.
# Small counts turn up incidentally ("2 of the 3 services"), and four-digit years belong
# to `check_dates`, which knows the range each claim may fall in — reporting them here
# too would raise two violations for one mistake and hand the model a contradictory
# retry note.
_TRIVIAL = frozenset(str(n) for n in range(0, 11))
_YEAR_VALUE = re.compile(r"^(19|20)\d{2}$")


def experience_label(index: int) -> str:
    return f"E{index + 1}"


def bullet_label(experience_index: int, bullet_index: int) -> str:
    return f"{experience_label(experience_index)}B{bullet_index + 1}"


def project_label(index: int) -> str:
    return f"P{index + 1}"


def project_bullet_label(project_index: int, bullet_index: int) -> str:
    return f"{project_label(project_index)}B{bullet_index + 1}"


def fold(value: str) -> str:
    """Lowercase, strip accents, collapse everything else to single spaces.

    Accent stripping is not cosmetic here. The old normaliser kept only `[a-z0-9]`, so
    "Pokémon" became "pok mon" and a résumé spelling it "Pokemon" compared unequal to
    the profile's own project name. Decomposing first and dropping the combining marks
    makes the two the same string.
    """
    decomposed = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM.sub(" ", stripped.lower()).strip()


def numbers_in(text: str) -> set[str]:
    """Every non-trivial figure in `text`, normalised for comparison."""
    found = set()
    for match in _NUMERIC.finditer(text or ""):
        value = _normalize_number(match.group())
        if value and value not in _TRIVIAL and not _YEAR_VALUE.match(value):
            found.add(value)
    return found


def _normalize_number(token: str) -> str:
    """`$1,200.00` and `1200` compare equal, and so do `40,000` and `40k`.

    Magnitude suffixes are expanded rather than kept as text, which is the one place
    this departs from the reference implementation it came from. Leaving "40k" as "40k"
    would flag a rewrite that merely shortened a figure the user really did record as
    "40,000" — a false rejection of exactly the tightening tailoring is meant to do.

    `%` and `x` are units, not magnitudes, so they stay: "40%" is not the figure "40".
    """
    token = token.strip().lower().replace(",", "").replace("$", "").replace(" ", "")
    for unit in ("%", "x"):
        if token.endswith(unit):
            return _trim(token[:-1]) + unit
    for suffix, factor in _MAGNITUDES.items():
        if token.endswith(suffix):
            try:
                return _trim(f"{Decimal(token[:-1]) * factor:f}")
            except InvalidOperation:
                return token
    return _trim(token)


def _trim(number: str) -> str:
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number or "0"


@dataclass
class ProfileIndex:
    """Everything the checks need to answer "is this in the profile?" quickly."""

    profile: Profile
    _experiences: dict[str, ExperienceRead] = field(default_factory=dict)
    _bullets: dict[str, str] = field(default_factory=dict)
    _projects: dict[str, ProjectRead] = field(default_factory=dict)
    _project_bullets: dict[str, str] = field(default_factory=dict)
    years: set[int] = field(default_factory=set)
    numbers: set[str] = field(default_factory=set)
    corpus: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for position, experience in enumerate(self.profile.experiences):
            self._experiences[experience_label(position)] = experience
            for bullet_position, bullet in enumerate(experience.bullets):
                self._bullets[bullet_label(position, bullet_position)] = bullet.text

        for position, project in enumerate(self.profile.projects):
            self._projects[project_label(position)] = project
            for bullet_position, bullet in enumerate(project.bullets):
                self._project_bullets[
                    project_bullet_label(position, bullet_position)
                ] = bullet.text

        for start, end in self._date_pairs():
            for value in (start, end):
                if value:
                    self.years.add(value.year)

        texts = self._profile_text()
        self.corpus = [folded for folded in (fold(text) for text in texts) if folded]
        self.numbers = {number for text in texts for number in numbers_in(text)}

    def _profile_text(self) -> list[str]:
        """Every string the profile contains, kept as separate fields on purpose.

        Joining them into one document would let a phrase match across the seam between
        two unrelated rows — a project called "Portfolio Site" followed by a stack
        beginning "Next.js" would make "Site Next" findable. Each field is matched whole.
        """
        return [
            self.profile.full_name,
            self.profile.summary or "",
            *(e.company for e in self.profile.experiences),
            *(e.title for e in self.profile.experiences),
            *(e.location or "" for e in self.profile.experiences),
            *self._bullets.values(),
            *(e.school for e in self.profile.education),
            *(e.degree for e in self.profile.education),
            *(e.field_of_study or "" for e in self.profile.education),
            *(s.name for s in self.profile.skills),
            *(p.name for p in self.profile.projects),
            *(p.tech_stack or "" for p in self.profile.projects),
            *self._project_bullets.values(),
            *(link.label for link in self.profile.links),
        ]

    def mentions(self, value: str) -> bool:
        """Whether the candidate wrote `value` anywhere in their own profile.

        Matched on whole words, not raw substring: "Go" must appear as the word Go, or
        every profile mentioning Django would be taken to claim it.
        """
        folded = fold(value)
        if not folded:
            return False
        needle = f" {folded} "
        return any(needle in f" {text} " for text in self.corpus)

    def experience(self, label: str) -> ExperienceRead | None:
        return self._experiences.get(label)

    def bullet(self, label: str) -> str | None:
        """The original text of a bullet, or None if the label resolves to nothing."""
        return self._bullets.get(label)

    def project(self, label: str) -> ProjectRead | None:
        return self._projects.get(label)

    def project_bullet(self, label: str) -> str | None:
        return self._project_bullets.get(label)

    def years_for(self, experience: ExperienceRead) -> set[int]:
        """Every year one experience spans, so its bullets can be date-checked in context.

        An ongoing role (no end date) runs to the present.
        """
        end = experience.end_date.year if experience.end_date else date.today().year
        return set(range(experience.start_date.year, end + 1))

    def _date_pairs(self) -> list[tuple]:
        return [
            *((e.start_date, e.end_date) for e in self.profile.experiences),
            *((e.start_date, e.end_date) for e in self.profile.education),
            *((p.start_date, p.end_date) for p in self.profile.projects),
        ]
