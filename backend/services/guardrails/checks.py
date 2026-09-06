"""The validation chain run after every generation.

Every check here is hardcoded, never LLM-judged. That is deliberate: asking a model
whether another model fabricated something inherits the same failure mode. Set
membership and token overlap are decidable, and decidable is what makes the
anti-fabrication claim checkable rather than aspirational.

Each check returns structured `Violation`s rather than a boolean, because the retry has
to tell the model precisely what it got wrong.
"""

import re
from dataclasses import dataclass
from datetime import date

from schemas.profile import Profile
from schemas.resume import TailoredResume
from services.guardrails.references import PROPER_PHRASE, ProfileIndex

# A rewrite has to keep this share of its source bullet's meaningful words. Low enough
# that genuine rephrasing survives, high enough that a new claim does not.
MIN_BULLET_OVERLAP = 0.35

# Words carrying no evidence of shared content, excluded before measuring overlap so
# two sentences aren't judged similar for both containing "the".
STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    to was were will with we our i my""".split()
)

# Tics that read as machine-written. Not fabrication, but they make a resume worse.
FORBIDDEN_PHRASES = [
    "delve into",
    "tapestry",
    "testament to",
    "it is worth noting",
    "in today's fast-paced",
    "leverage synergies",
    "passionate about leveraging",
    "results-driven professional",
    "wear many hats",
]

_WORD = re.compile(r"[a-z0-9]+")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")

# Capitalised phrases that are ordinary English rather than organisation names.
_PROPER_ALLOWLIST = frozenset(
    {
        "computer science",
        "machine learning",
        "data science",
        "software engineering",
        "web development",
        "open source",
        "full stack",
        "united states",
        "new york",
        "san francisco",
    }
)


@dataclass(frozen=True)
class Violation:
    check: str
    message: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.message}"


def run_all(
    resume: TailoredResume,
    profile: Profile,
    posting_vocabulary: set[str] | None = None,
) -> list[Violation]:
    """Run every check. `posting_vocabulary` is what the *rationale* may also name.

    The rationale explains how the candidate matches this posting, so it legitimately
    mentions the target company and role. A live run rejected a perfectly good
    rationale for naming "Account Executive" — the job being applied to. The resume
    itself gets no such licence: its summary and bullets may only draw on the profile.
    """
    index = ProfileIndex(profile)
    violations: list[Violation] = []
    for check in (
        check_references,
        check_bullet_traceability,
        check_skills,
        check_dates,
    ):
        violations.extend(check(resume, index))
    violations.extend(
        check_forbidden_content(resume, index, posting_vocabulary or set())
    )
    return violations


def check_references(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """Every label must resolve to a real profile row.

    In this schema an unresolvable label *is* an invented employer: the model cannot
    write a company name, so inventing one means citing an experience that isn't there.
    """
    violations = []
    seen: set[str] = set()

    for experience in resume.experiences:
        if index.experience(experience.source) is None:
            violations.append(
                Violation(
                    "references",
                    f"experience {experience.source!r} is not in the profile",
                )
            )
            continue
        if experience.source in seen:
            violations.append(
                Violation(
                    "references",
                    f"experience {experience.source!r} appears more than once",
                )
            )
        seen.add(experience.source)

        for bullet in experience.bullets:
            source = index.bullet(bullet.source)
            if source is None:
                violations.append(
                    Violation(
                        "references",
                        f"bullet {bullet.source!r} is not in the profile",
                    )
                )
            elif not bullet.source.startswith(experience.source + "B"):
                violations.append(
                    Violation(
                        "references",
                        f"bullet {bullet.source!r} belongs to a different experience "
                        f"than {experience.source!r}",
                    )
                )

    seen_projects: set[str] = set()
    for project in resume.projects:
        if index.project(project.source) is None:
            violations.append(
                Violation(
                    "references",
                    f"project {project.source!r} is not in the profile",
                )
            )
            continue
        if project.source in seen_projects:
            violations.append(
                Violation(
                    "references",
                    f"project {project.source!r} appears more than once",
                )
            )
        seen_projects.add(project.source)

        for bullet in project.bullets:
            if index.project_bullet(bullet.source) is None:
                violations.append(
                    Violation(
                        "references",
                        f"project bullet {bullet.source!r} is not in the profile",
                    )
                )
            elif not bullet.source.startswith(project.source + "B"):
                violations.append(
                    Violation(
                        "references",
                        f"project bullet {bullet.source!r} belongs to a different "
                        f"project than {project.source!r}",
                    )
                )

    return violations


def check_bullet_traceability(
    resume: TailoredResume, index: ProfileIndex
) -> list[Violation]:
    """A rewrite must still be recognisably the bullet it came from.

    Rephrasing is the whole point of tailoring, so this cannot demand equality. It
    demands evidence: enough shared meaningful words that the claim is the same claim.

    Project bullets are measured the same way and by the same threshold. They briefly
    were not: while a project was one long `description`, a one-line resume entry could
    retain at most a fifth of a sixty-word paragraph, so this measure was unpassable and
    a separate containment check existed for them. Storing project bullets as rows
    removed that mismatch — they are the same length as experience bullets now — and the
    special case went with it.
    """
    pairs = [
        (bullet, index.bullet(bullet.source))
        for experience in resume.experiences
        for bullet in experience.bullets
    ] + [
        (bullet, index.project_bullet(bullet.source))
        for project in resume.projects
        for bullet in project.bullets
    ]

    violations = []
    for bullet, source in pairs:
        if source is None:
            continue  # already reported by check_references

        ratio = overlap_ratio(bullet.text, source)
        if ratio < MIN_BULLET_OVERLAP:
            violations.append(
                Violation(
                    "traceability",
                    f"bullet {bullet.source!r} keeps only {ratio:.0%} of its source "
                    f"wording (minimum {MIN_BULLET_OVERLAP:.0%}). Rewrite the "
                    f"original rather than writing a new claim. "
                    f"Original: {source!r}",
                )
            )
    return violations


def check_skills(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """A set-membership test, not a judgement call."""
    return [
        Violation(
            "skills",
            f"skill {skill!r} is not in the profile",
        )
        for skill in resume.skills
        if _normalize(skill) not in index.skills
    ]


def check_dates(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """No future years, and no year a claim could not plausibly refer to.

    The structured dates are copied from the profile at assembly time and cannot drift,
    so this polices dates asserted in prose.

    A bullet is checked against **its own experience's date range**, not the profile as
    a whole. That distinction matters: "led payments since 2015" on a job that ran
    2021-2024 is a shifted date, even though 2015 is a real year elsewhere in the
    profile (a degree, say). Checking against the whole profile would wave it through.

    The summary, the rationale and project descriptions have no such context, so they are
    checked against every year the profile contains. **A shifted date in the summary that
    happens to land on another real profile year is not caught** — a known limit of a
    context-free set membership test, and the reason the bullet-level check is scoped
    tighter.
    """
    violations = []
    this_year = date.today().year

    for label, text, allowed in _dated_text(resume, index):
        for match in _YEAR.finditer(text):
            year = int(match.group(0))
            if year > this_year:
                violations.append(
                    Violation("dates", f"{label} claims a future year {year}")
                )
            elif year not in allowed:
                violations.append(
                    Violation(
                        "dates",
                        f"{label} mentions {year}, which does not fall within the "
                        f"dates recorded for it",
                    )
                )
    return violations


def check_forbidden_content(
    resume: TailoredResume,
    index: ProfileIndex,
    posting_vocabulary: set[str] | None = None,
) -> list[Violation]:
    """LLM tics, and organisation names the profile has never heard of.

    The proper-noun half is **best effort**. It catches "led engineering at Northwind
    Systems" when Northwind isn't in the profile, but free-text organisation invention
    is not fully solvable by string matching, and this will both miss cases and
    occasionally flag an innocent capitalised phrase. The real defence is structural:
    the model has no field in which to write an employer. This is a second net, not the
    first one.
    """
    violations = []
    # Only the rationale may name the posting; the resume itself may not.
    rationale_extra = posting_vocabulary or set()

    for label, text in _free_text(resume):
        allowed = index.vocabulary | (
            rationale_extra if label == "the rationale" else set()
        )
        lowered = text.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in lowered:
                violations.append(
                    Violation("style", f"{label} contains the phrase {phrase!r}")
                )

        for match in PROPER_PHRASE.finditer(text):
            phrase = match.group(1)
            if _phrase_allowed(phrase, allowed):
                continue
            violations.append(
                Violation(
                    "fabrication",
                    f"{label} names {phrase!r}, which is not in the profile",
                )
            )
    return violations


def _phrase_allowed(phrase: str, allowed: set[str]) -> bool:
    """Whether a capitalised phrase, or any suffix of it, is known.

    Suffixes matter because a sentence-initial word gets swept into the match: "The
    Account Executive role..." captures "The Account Executive", which is not in any
    vocabulary even though "Account Executive" is. Trying each suffix strips the
    incidental leading words without loosening the check — an invented name still
    matches nothing at any offset.
    """
    tokens = phrase.split()
    for start in range(len(tokens)):
        candidate = _normalize(" ".join(tokens[start:]))
        if candidate and (candidate in allowed or candidate in _PROPER_ALLOWLIST):
            return True
    return False


def overlap_ratio(rewrite: str, source: str) -> float:
    """How much of the **source** bullet survives in the rewrite.

    Deliberately measured against the source, not the rewrite. Dividing by the
    rewrite's length punishes exactly the behaviour we want: a live run rejected
    "Built Python dashboards giving the analytics team direct visibility into
    conversion" because the added framing diluted the ratio, even though every word of
    the original was still present. Traceability asks "is the original claim still
    here?", and that is a question about the source.

    Wholesale invention still fails, because an unrelated sentence covers none of the
    source's words.
    """
    original = _content_words(source)
    if not original:
        return 0.0
    return len(original & _content_words(rewrite)) / len(original)


def _content_words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in STOPWORDS}


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))


def _free_text(resume: TailoredResume) -> list[tuple[str, str]]:
    """Every field the model wrote freely, labelled for error messages."""
    texts = [("the summary", resume.summary), ("the rationale", resume.rationale)]
    texts += [
        (f"bullet {bullet.source}", bullet.text)
        for experience in resume.experiences
        for bullet in experience.bullets
    ]
    texts += [
        (f"project bullet {bullet.source}", bullet.text)
        for project in resume.projects
        for bullet in project.bullets
    ]
    return texts


def _dated_text(
    resume: TailoredResume, index: ProfileIndex
) -> list[tuple[str, str, set[int]]]:
    """Free text paired with the years each piece is allowed to mention."""
    everywhere = index.years
    items: list[tuple[str, str, set[int]]] = [
        ("the summary", resume.summary, everywhere),
        ("the rationale", resume.rationale, everywhere),
    ]

    for experience in resume.experiences:
        source = index.experience(experience.source)
        # An unresolvable experience is already a reference violation; fall back to the
        # whole profile so this check doesn't pile on a second, confusing complaint.
        allowed = index.years_for(source) if source else everywhere
        items += [
            (f"bullet {bullet.source}", bullet.text, allowed)
            for bullet in experience.bullets
        ]

    # Project bullets get the summary's treatment — every year the profile contains —
    # rather than a per-project range. Project rows very often carry no dates at all, and
    # a range built from two NULLs would reject every year a bullet mentions, including
    # the correct one. Same known limit as the summary: a shifted date that happens to
    # land on another real profile year is not caught.
    items += [
        (f"project bullet {bullet.source}", bullet.text, everywhere)
        for project in resume.projects
        for bullet in project.bullets
    ]
    return items
