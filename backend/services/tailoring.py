"""Resume tailoring: render the prompt, generate, validate, retry, assemble."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from models.application import JobPosting
from schemas.profile import Profile
from schemas.resume import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeLink,
    ResumeProject,
    TailoredResume,
)
from services import guardrails
from services.guardrails import (
    Violation,
    bullet_label,
    experience_label,
    project_label,
)
from services.guardrails.references import ProfileIndex
from services.llm.base import LLMProvider

PROMPT_VERSION = "tailor_resume.v2"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_VERSION}.md"

# One initial attempt plus this many retries. Named rather than inlined because "up to
# two attempts" is ambiguous about whether the first one counts.
MAX_RETRIES = 2

# What fits on one page. The prompt states these limits and `assemble` enforces them by
# slicing, which is deliberate: they are a *budget*, not a correctness property, so
# rejecting an over-long draft would spend a whole extra API call to obtain output the
# server can produce itself. The model is told to order by relevance, so taking the first
# N takes the most relevant N. The density fit-loop in `render` handles the slack left
# over; these caps are what keep that loop from having to shrink the type to fit.
MAX_EXPERIENCES = 4
MAX_BULLETS = 4
MAX_PROJECTS = 3
MAX_SKILLS = 14

# Every rejected attempt is a whole extra model call. Logging them makes that cost, and
# the reason for it, visible — a generation reporting `attempts: 2` used to give no way
# to find out what the first draft got wrong.
logger = logging.getLogger(__name__)


@dataclass
class TailoringResult:
    resume: Resume
    rationale: str
    attempts: int


def generate(
    profile: Profile, posting: JobPosting, provider: LLMProvider
) -> TailoringResult:
    """Tailor a resume, retrying with named violations before giving up.

    Raises `GuardrailFailure` rather than returning output that failed validation —
    silently returning a resume with a fabricated claim is the one outcome this whole
    phase exists to prevent.
    """
    base_prompt = build_prompt(profile, posting)
    prompt = base_prompt
    violations: list[Violation] = []

    for attempt in range(1, MAX_RETRIES + 2):
        tailored = provider.generate_structured(prompt, TailoredResume)
        violations = guardrails.run_all(
            tailored, profile, posting_vocabulary=posting_vocabulary(posting)
        )

        if not violations:
            return TailoringResult(
                resume=assemble(tailored, profile),
                rationale=tailored.rationale,
                attempts=attempt,
            )

        logger.info(
            "Attempt %d rejected, retrying: %s",
            attempt,
            "; ".join(str(violation) for violation in violations),
        )

        # Name the specific violations. A bare "try again" gives the model nothing to
        # correct, and tends to produce the same output.
        prompt = f"{base_prompt}\n\n{_retry_note(violations)}"

    raise guardrails.GuardrailFailure(violations, attempts=MAX_RETRIES + 1)


def posting_vocabulary(posting: JobPosting) -> set[str]:
    """Proper nouns the rationale may name because they belong to the target job.

    The rationale's job is to compare the candidate to *this* posting, so naming the
    hiring company and the role is correct, not fabrication.
    """
    return {
        _normalize(value)
        for value in (posting.company, posting.title, posting.location)
        if value
    }


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def build_prompt(profile: Profile, posting: JobPosting) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        job_posting=render_posting(posting), profile=render_profile(profile)
    )


def render_posting(posting: JobPosting) -> str:
    lines = [
        f"Company: {posting.company}",
        f"Title: {posting.title}",
    ]
    if posting.location:
        lines.append(f"Location: {posting.location}")
    if posting.employment_type:
        lines.append(f"Employment type: {posting.employment_type}")
    if posting.description:
        lines.append(f"\nDescription:\n{posting.description}")
    if posting.requirements:
        lines.append(f"\nRequirements:\n{posting.requirements}")
    return "\n".join(lines)


def render_profile(profile: Profile) -> str:
    """The profile as the model sees it, with the labels it must cite.

    Labels come from `guardrails.references`, the same module the checks resolve them
    with, so the two cannot drift apart.
    """
    lines = [f"Name: {profile.full_name}"]
    if profile.summary:
        lines.append(f"Summary: {profile.summary}")

    lines.append("\n## Experience")
    for position, experience in enumerate(profile.experiences):
        label = experience_label(position)
        dates = _date_range(experience.start_date, experience.end_date)
        lines.append(
            f"\n[{label}] {experience.title} at {experience.company}"
            f"{f' ({experience.location})' if experience.location else ''} — {dates}"
        )
        for bullet_position, bullet in enumerate(experience.bullets):
            lines.append(
                f"  [{bullet_label(position, bullet_position)}] {bullet.text}"
            )
        if not experience.bullets:
            lines.append("  (no bullets recorded)")

    if profile.skills:
        # One skill per line, name first. An earlier version grouped these as
        # "Languages: Python, SQL" and a live run copied the whole line back as a
        # single skill named "Languages: Python, SQL" — which the guardrails correctly
        # rejected. The category is parenthetical so the name is unmistakable.
        lines.append(
            "\n## Skills — copy these names exactly into `skills`. "
            "Each line is one skill; the bracketed word is only its category."
        )
        for skill in profile.skills:
            category = f"  ({skill.category})" if skill.category else ""
            lines.append(f"  - {skill.name}{category}")

    if profile.education:
        lines.append("\n## Education")
        for entry in profile.education:
            field = f", {entry.field_of_study}" if entry.field_of_study else ""
            lines.append(f"  {entry.degree}{field} — {entry.school}")

    if profile.projects:
        # Labelled, like experiences. Before v2 these were listed unlabelled, which meant
        # the model could read about a project and had no way to put one on the resume —
        # they were prompt cost with no possible output.
        lines.append("\n## Projects")
        for position, project in enumerate(profile.projects):
            description = f": {project.description}" if project.description else ""
            lines.append(f"  [{project_label(position)}] {project.name}{description}")

    return "\n".join(lines)


def assemble(tailored: TailoredResume, profile: Profile) -> Resume:
    """Fill every factual field from the profile rows the labels resolved to.

    Nothing factual here comes from the model — it chose *which* rows, and rewrote
    bullet and project text. That is why an invented employer is impossible rather than
    merely detectable.

    This is also where the one-page budget is enforced, by slicing. The model was asked
    for the same limits and ordered its output by relevance, so the slice keeps what it
    ranked highest.
    """
    index = ProfileIndex(profile)

    experiences = []
    for selected in tailored.experiences[:MAX_EXPERIENCES]:
        source = index.experience(selected.source)
        if source is None:
            continue  # guardrails already rejected this; belt and braces
        experiences.append(
            ResumeExperience(
                company=source.company,
                title=source.title,
                location=source.location,
                start_date=source.start_date,
                end_date=source.end_date,
                bullets=[bullet.text for bullet in selected.bullets[:MAX_BULLETS]],
            )
        )

    projects = []
    for chosen in tailored.projects[:MAX_PROJECTS]:
        source = index.project(chosen.source)
        if source is None:
            continue
        projects.append(
            ResumeProject(
                name=source.name,
                url=source.url,
                start_date=source.start_date,
                end_date=source.end_date,
                # The rewrite when there is one, nothing when there isn't. The profile's
                # own description is not a fallback: the model was shown it and chose to
                # leave it out, and quietly reinstating it would put untailored text on a
                # tailored resume.
                description=chosen.text.strip() or None,
            )
        )

    return Resume(
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        summary=tailored.summary,
        experiences=experiences,
        projects=projects,
        education=[
            ResumeEducation(
                school=entry.school,
                degree=entry.degree,
                field_of_study=entry.field_of_study,
                start_date=entry.start_date,
                end_date=entry.end_date,
            )
            for entry in profile.education
        ],
        skills=list(tailored.skills[:MAX_SKILLS]),
        links=[ResumeLink(label=link.label, url=link.url) for link in profile.links],
    )


def _retry_note(violations: list[Violation]) -> str:
    listed = "\n".join(f"- {violation}" for violation in violations)
    return (
        "Your previous answer was rejected by automated validation for these reasons:\n"
        f"{listed}\n\n"
        "Produce a corrected resume that fixes every one of them. Do not restate the "
        "problems; return the corrected resume."
    )


def _date_range(start, end) -> str:
    started = start.strftime("%b %Y") if start else "?"
    return f"{started} – {end.strftime('%b %Y') if end else 'present'}"
