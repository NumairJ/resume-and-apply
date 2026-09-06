"""Reference labels, and the index that resolves them.

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
"""

import re
from dataclasses import dataclass, field
from datetime import date

from schemas.profile import ExperienceRead, Profile, ProjectRead

_WORD = re.compile(r"[a-z0-9]+")

# Two or more consecutive capitalised words: the shape of an organisation name.
#
# Lives here rather than in `checks.py` because both sides need it — this module *mines*
# the profile's own free text for known phrases, and `checks.py` *scans* generated text
# for unknown ones. One pattern, so the two cannot disagree about what a phrase is.
#
# The joiner is horizontal whitespace, never `\s+`. A newline is a sentence boundary, not
# a word gap: with `\s+`, a description reading "…built with Bootstrap\nBuilt a REST API…"
# yields the phrase "Bootstrap Built", which nobody wrote and which therefore matches
# nothing in any vocabulary. Real profiles are full of such line breaks.
PROPER_PHRASE = re.compile(r"\b([A-Z][\w&.-]*(?:[^\S\r\n]+[A-Z][\w&.-]*)+)")


def experience_label(index: int) -> str:
    return f"E{index + 1}"


def bullet_label(experience_index: int, bullet_index: int) -> str:
    return f"{experience_label(experience_index)}B{bullet_index + 1}"


def project_label(index: int) -> str:
    return f"P{index + 1}"


def project_bullet_label(project_index: int, bullet_index: int) -> str:
    return f"{project_label(project_index)}B{bullet_index + 1}"


@dataclass
class ProfileIndex:
    """Everything the checks need to answer "is this in the profile?" quickly."""

    profile: Profile
    _experiences: dict[str, ExperienceRead] = field(default_factory=dict)
    _bullets: dict[str, str] = field(default_factory=dict)
    _projects: dict[str, ProjectRead] = field(default_factory=dict)
    _project_bullets: dict[str, str] = field(default_factory=dict)
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
            for bullet_position, bullet in enumerate(project.bullets):
                self._project_bullets[
                    project_bullet_label(position, bullet_position)
                ] = bullet.text

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

        # And the proper nouns the user wrote in their own free text.
        #
        # Names alone were not enough, and the gap was not theoretical: a live run was
        # rejected three times for "naming" RESTful API, Team Builder and Convolutional
        # Neural Network — every one of them typed by the user into their own bullets and
        # project bullets. The check was calling the profile's own words invented.
        #
        # Phrases, never loose words. Adding the individual tokens would let a model
        # recombine "Northwind" from one bullet and "Systems" from another into an
        # employer nobody has ever worked for, which is the exact failure this check
        # exists to catch. Reusing a phrase the user actually typed is not fabrication;
        # assembling a new one from their vocabulary would be.
        self.vocabulary |= {
            _normalize(match.group(1))
            for text in self._authored_text()
            for match in PROPER_PHRASE.finditer(text)
        }

    def _authored_text(self) -> list[str]:
        """Every free-text field the user wrote themselves and the model is shown."""
        return [
            self.profile.summary or "",
            *self._bullets.values(),
            *self._project_bullets.values(),
            # The stack is user-authored too, and the model is shown it — so a summary
            # that mentions "Node.js, Express" must not read as fabrication.
            *(project.tech_stack or "" for project in self.profile.projects),
        ]

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


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))
