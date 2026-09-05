"""Reference labels, and the index that resolves them.

The labelling scheme lives here and **only** here. The prompt renderer and the guardrail
chain both import it, so the labels the model is shown are by construction the same
labels the checks resolve. If these two ever drifted apart, every generation would look
like fabrication.

    E1      the first experience
    E1B2    the second bullet of the first experience
    P1      the first project

Labels are 1-based because they appear in a prompt, and a model reading "E0" as the
first item is an avoidable stumble.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from schemas.profile import ExperienceRead, Profile, ProjectRead

_WORD = re.compile(r"[a-z0-9]+")


def experience_label(index: int) -> str:
    return f"E{index + 1}"


def bullet_label(experience_index: int, bullet_index: int) -> str:
    return f"{experience_label(experience_index)}B{bullet_index + 1}"


def project_label(index: int) -> str:
    return f"P{index + 1}"


@dataclass
class ProfileIndex:
    """Everything the checks need to answer "is this in the profile?" quickly."""

    profile: Profile
    _experiences: dict[str, ExperienceRead] = field(default_factory=dict)
    _bullets: dict[str, str] = field(default_factory=dict)
    _projects: dict[str, ProjectRead] = field(default_factory=dict)
    skills: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)
    vocabulary: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        for position, experience in enumerate(self.profile.experiences):
            self._experiences[experience_label(position)] = experience
            for bullet_position, bullet in enumerate(experience.bullets):
                self._bullets[bullet_label(position, bullet_position)] = bullet.text

        for position, project in enumerate(self.profile.projects):
            self._projects[project_label(position)] = project

        self.skills = {_normalize(skill.name) for skill in self.profile.skills}

        for start, end in self._date_pairs():
            for value in (start, end):
                if value:
                    self.years.add(value.year)

        # Proper nouns the profile legitimately contains, so the fabrication check has
        # something to measure against.
        self.vocabulary = {
            _normalize(value)
            for value in [
                self.profile.full_name,
                *(e.company for e in self.profile.experiences),
                *(e.title for e in self.profile.experiences),
                *(e.school for e in self.profile.education),
                *(e.degree for e in self.profile.education),
                *(e.field_of_study or "" for e in self.profile.education),
                *(p.name for p in self.profile.projects),
                *(s.name for s in self.profile.skills),
                *(link.label for link in self.profile.links),
            ]
            if value
        }

    def experience(self, label: str) -> ExperienceRead | None:
        return self._experiences.get(label)

    def bullet(self, label: str) -> str | None:
        """The original text of a bullet, or None if the label resolves to nothing."""
        return self._bullets.get(label)

    def project(self, label: str) -> ProjectRead | None:
        return self._projects.get(label)

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


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))
