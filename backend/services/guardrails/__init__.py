from services.guardrails.checks import (
    MIN_BULLET_OVERLAP,
    Violation,
    overlap_ratio,
    run_all,
)
from services.guardrails.references import (
    ProfileIndex,
    bullet_label,
    experience_label,
    project_label,
)


class GuardrailFailure(Exception):
    """Generated output failed validation and no retry is left.

    Carries the violations so the caller can tell the user what was wrong rather than
    reporting a bare failure.
    """

    def __init__(self, violations: list[Violation], attempts: int) -> None:
        super().__init__(
            f"Generated resume failed validation after {attempts} attempts"
        )
        self.violations = violations
        self.attempts = attempts


__all__ = [
    "GuardrailFailure",
    "MIN_BULLET_OVERLAP",
    "ProfileIndex",
    "Violation",
    "bullet_label",
    "experience_label",
    "overlap_ratio",
    "project_label",
    "run_all",
]
