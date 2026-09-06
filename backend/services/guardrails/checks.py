"""The validation chain run after every generation.

Every check here is hardcoded, never LLM-judged. That is deliberate: asking a model
whether another model fabricated something inherits the same failure mode. Set
membership, token overlap and year membership are decidable, and decidable is what makes
the anti-fabrication claim checkable rather than aspirational.

Each check returns structured `Violation`s rather than a boolean, because the retry has
to tell the model precisely what it got wrong.

**What is deliberately not checked: organisation names in free text.** A scan for
capitalised phrases used to live here, rejecting any that were not mined from the
profile. It was the only check that ever produced a false rejection, and it produced
them constantly — a single live run was refused three times for "naming" RESTful API,
Team Builder and Convolutional Neural Network, every one of them typed by the user. The
shape of the check guaranteed more of the same, because ordinary capitalised English is
indistinguishable from an invented employer under a string match. It is gone, and the
consequence is stated honestly: a summary reading "previously at Goldman Sachs" would
not be caught. The structural guarantee is untouched — the model has no field in which
to write an employer — and bullets remain anchored to a cited source below.
"""

import re
from dataclasses import dataclass
from datetime import date

from schemas.profile import Profile
from schemas.resume import TailoredBullet, TailoredResume
from services.guardrails.references import ProfileIndex, numbers_in

# A rewrite has to keep this share of its source bullet's meaningful words. Low enough
# that genuine rephrasing survives, high enough that a new claim does not.
#
# Lowered from 0.35: the figures inside a bullet are now checked directly, which catches
# the drift that actually matters — an inflated metric wrapped in faithful words — and
# leaves this measure to do the one job it is good at, catching wholesale invention. An
# unrelated sentence still scores near zero.
MIN_BULLET_OVERLAP = 0.25

# Words carrying no evidence of shared content, excluded before measuring overlap so
# two sentences aren't judged similar for both containing "the".
STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    to was were will with we our i my""".split()
)

_WORD = re.compile(r"[a-z0-9]+")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class Violation:
    check: str
    message: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.message}"


def run_all(resume: TailoredResume, profile: Profile) -> list[Violation]:
    """Run every check. An empty list means the draft is accepted."""
    index = ProfileIndex(profile)
    violations: list[Violation] = []
    for check in (
        check_references,
        check_bullet_traceability,
        check_numbers,
        check_skills,
        check_dates,
    ):
        violations.extend(check(resume, index))
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
    violations = []
    for bullet, source in _sourced_bullets(resume, index):
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


def check_numbers(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """Every figure asserted must be a figure the candidate actually recorded.

    This is the check traceability cannot do. "Reduced payment errors by 86%" rewritten
    from a bullet saying "from 2.1% to 0.3%" keeps almost every meaningful word, so word
    overlap waves it through — and 86% is a claim the candidate never made, arrived at
    by arithmetic the model performed on their behalf. An inflated metric is the single
    most damaging thing a tailored resume can carry, because it is the one a reference
    check disproves outright.

    A bullet's figures are checked against **its own source bullet**, not the profile at
    large. A number lifted from a sibling bullet is a mixed claim even though both
    bullets are real. The summary has no single source, so it is checked against every
    figure in the profile — the same known weakness `check_dates` documents for years.
    """
    violations = []
    for bullet, source in _sourced_bullets(resume, index):
        if source is None:
            continue  # already reported by check_references
        for number in sorted(numbers_in(bullet.text) - numbers_in(source)):
            violations.append(
                Violation(
                    "metrics",
                    f"bullet {bullet.source!r} claims {number!r}, which is not in the "
                    f"bullet it was rewritten from. Keep the original's figures or "
                    f"leave them out. Original: {source!r}",
                )
            )

    for number in sorted(numbers_in(resume.summary) - index.numbers):
        violations.append(
            Violation(
                "metrics",
                f"the summary claims {number!r}, which appears nowhere in the profile",
            )
        )
    return violations


def check_skills(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """A skill must be one the candidate claims somewhere — not necessarily a skill row.

    Surfacing a buried skill is the legitimate core of tailoring: a technology named in
    a project's stack or worked into a bullet is something the candidate genuinely did,
    and requiring it to have been typed a second time under Settings rejected honest
    output. Introducing one because the posting asked for it is still fabrication, and
    still caught — the profile's own text is the whole of what is allowed.
    """
    return [
        Violation(
            "skills",
            f"skill {skill!r} does not appear anywhere in the profile",
        )
        for skill in resume.skills
        if not index.mentions(skill)
    ]


def check_dates(resume: TailoredResume, index: ProfileIndex) -> list[Violation]:
    """No future years, and no year a claim could not plausibly refer to.

    The structured dates are copied from the profile at assembly time and cannot drift,
    so this polices dates asserted in prose.

    A bullet is checked against **its own experience's date range**, not the profile as
    a whole. That distinction matters: "led payments since 2015" on a job that ran
    2021-2024 is a shifted date, even though 2015 is a real year elsewhere in the
    profile (a degree, say). Checking against the whole profile would wave it through.

    The summary has no such context, so it is checked against every year the profile
    contains. **A shifted date in the summary that happens to land on another real
    profile year is not caught** — a known limit of a context-free set membership test,
    and the reason the bullet-level check is scoped tighter.
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


def _sourced_bullets(
    resume: TailoredResume, index: ProfileIndex
) -> list[tuple[TailoredBullet, str | None]]:
    """Every rewritten bullet paired with the original text it cites.

    Shared by the two checks that compare a rewrite against its source, so they cannot
    disagree about which bullets those are.
    """
    return [
        (bullet, index.bullet(bullet.source))
        for experience in resume.experiences
        for bullet in experience.bullets
    ] + [
        (bullet, index.project_bullet(bullet.source))
        for project in resume.projects
        for bullet in project.bullets
    ]


def _dated_text(
    resume: TailoredResume, index: ProfileIndex
) -> list[tuple[str, str, set[int]]]:
    """Free text paired with the years each piece is allowed to mention."""
    everywhere = index.years
    items: list[tuple[str, str, set[int]]] = [
        ("the summary", resume.summary, everywhere)
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
