"""Sample data shared by the guardrail and tailoring suites.

Plain functions rather than fixtures so they can also be called mid-test to build a
variant, which most of the fabrication tests do.
"""

import uuid
from datetime import date

from schemas.profile import (
    EducationRead,
    ExperienceBulletRead,
    ExperienceRead,
    LinkRead,
    Profile,
    ProjectBulletRead,
    ProjectRead,
    SkillRead,
)
from schemas.resume import (
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def sample_profile() -> Profile:
    """A small but realistic profile: two employers, three bullets, two skills.

    The 2015 education start date is deliberate — it makes 2015 a real profile year, so
    the date checks have to be scoped per-experience to catch it being misused.
    """
    return Profile(
        id=_uuid(),
        full_name="Dana Reed",
        email="dana@example.com",
        location="Toronto",
        experiences=[
            ExperienceRead(
                id=_uuid(),
                company="Northwind Systems",
                title="Software Engineer",
                start_date=date(2021, 3, 1),
                end_date=date(2024, 6, 1),
                position=0,
                bullets=[
                    ExperienceBulletRead(
                        id=_uuid(),
                        position=0,
                        text=(
                            "Reduced payment service error rates by hardening the "
                            "retry path"
                        ),
                    ),
                    ExperienceBulletRead(
                        id=_uuid(),
                        position=1,
                        text=(
                            "Migrated the billing database to Postgres with no downtime"
                        ),
                    ),
                ],
            ),
            ExperienceRead(
                id=_uuid(),
                company="Contoso",
                title="Junior Developer",
                start_date=date(2019, 1, 1),
                end_date=date(2021, 2, 1),
                position=1,
                bullets=[
                    ExperienceBulletRead(
                        id=_uuid(),
                        position=0,
                        text="Built internal React dashboards for the support team",
                    )
                ],
            ),
        ],
        education=[
            EducationRead(
                id=_uuid(),
                school="State University",
                degree="BSc",
                field_of_study="Computer Science",
                start_date=date(2015, 9, 1),
                end_date=date(2019, 5, 1),
                position=0,
            )
        ],
        skills=[
            SkillRead(id=_uuid(), name="Python", category="Languages", position=0),
            SkillRead(id=_uuid(), name="Postgres", category="Databases", position=1),
        ],
        projects=[
            ProjectRead(
                id=_uuid(),
                name="Portfolio Site",
                # Carries "RESTful API" — a proper noun that is not a skill — because a
                # live run was refused three times for "naming" exactly that kind of
                # phrase out of the user's own bullets. The fabrication check is only
                # honestly tested against a fixture that contains one.
                tech_stack="Next.js, Postgres, Docker",
                bullets=[
                    ProjectBulletRead(
                        id=_uuid(),
                        position=0,
                        text=(
                            "Personal site built with Next.js and a typed API layer, "
                            "deployed on a single container"
                        ),
                    ),
                    ProjectBulletRead(
                        id=_uuid(),
                        position=1,
                        text=(
                            "Built a RESTful API for the writing archive and wired it "
                            "to a Postgres store with cached reads"
                        ),
                    ),
                ],
                url="https://dana.example/portfolio",
                start_date=date(2022, 4, 1),
                end_date=date(2022, 9, 1),
                position=0,
            ),
            # Bare on purpose: a project can be nothing but a name, and both the
            # guardrails and the template have to cope without inventing filler.
            ProjectRead(id=_uuid(), name="Crossword Solver", position=1),
        ],
        links=[LinkRead(id=_uuid(), label="GitHub", url="https://gh/dana", position=0)],
    )


def valid_resume() -> TailoredResume:
    """Output that should pass: real references, faithful rewrites, real skills."""
    return TailoredResume(
        rationale=(
            "The posting asks for payments reliability and Postgres depth, both of "
            "which show up directly in the most recent role."
        ),
        summary="Software engineer focused on payment reliability and databases.",
        experiences=[
            TailoredExperience(
                source="E1",
                bullets=[
                    TailoredBullet(
                        source="E1B1",
                        text=(
                            "Hardened the payment service retry path, reducing error "
                            "rates at peak load"
                        ),
                    ),
                    TailoredBullet(
                        source="E1B2",
                        text=(
                            "Migrated the billing database to Postgres with zero "
                            "downtime"
                        ),
                    ),
                ],
            )
        ],
        projects=[
            TailoredProject(
                source="P1",
                bullets=[
                    TailoredBullet(
                        source="P1B1",
                        text=(
                            "Personal site built with Next.js and a typed API layer, "
                            "deployed as a single container"
                        ),
                    )
                ],
            )
        ],
        skills=["Python", "Postgres"],
    )


def broken_resume() -> TailoredResume:
    """Fails the chain on a skill absent from the profile."""
    resume = valid_resume()
    resume.skills = ["Kubernetes"]
    return resume
