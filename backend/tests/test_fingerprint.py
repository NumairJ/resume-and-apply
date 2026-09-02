"""Fingerprint normalization.

Both directions matter, and they pull against each other. Too loose and a user is
warned off a role they never applied to; too strict and the warning never fires. The
collision tests and the separation tests below are what hold that balance in place.
"""

import pytest

from services.fingerprint import (
    fingerprint,
    normalize_company,
    normalize_location,
    normalize_title,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Acme Inc.", "acme"),
        ("Acme, Inc", "acme"),
        ("ACME LLC", "acme"),
        ("Acme Corporation", "acme"),
        ("Acme Systems GmbH", "acme systems"),
        ("  Acme   Systems  ", "acme systems"),
        # Only trailing suffixes are stripped — a leading "Corp" is part of the name.
        ("Corp Travel Company", "corp travel"),
    ],
)
def test_normalize_company(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Senior Software Engineer", "software engineer"),
        ("Sr. Software Engineer", "software engineer"),
        ("Software Engineer II", "software engineer"),
        ("Staff Software Engineer", "software engineer"),
        ("Lead Software Engineer", "software engineer"),
        ("Software Engineer", "software engineer"),
    ],
)
def test_normalize_title_strips_seniority(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Toronto, Ontario, Canada", "toronto"),
        ("Toronto", "toronto"),
        ("Remote", "remote"),
        ("Remote - US", "remote"),
        ("Remote, Italy", "remote"),
        ("Anywhere", "remote"),
        (None, ""),
    ],
)
def test_normalize_location(raw: str | None, expected: str) -> None:
    assert normalize_location(raw) == expected


@pytest.mark.parametrize(
    "left, right",
    [
        # The same job listed on two boards, worded differently.
        (
            ("Acme Inc.", "Senior Software Engineer", "Toronto, Ontario, Canada"),
            ("ACME", "Sr. Software Engineer", "Toronto"),
        ),
        # Level noise only.
        (
            ("Globex LLC", "Software Engineer II", "Remote"),
            ("Globex", "Software Engineer", "Remote - US"),
        ),
    ],
)
def test_same_job_phrased_differently_collides(
    left: tuple, right: tuple
) -> None:
    assert fingerprint(*left) == fingerprint(*right)


@pytest.mark.parametrize(
    "left, right, why",
    [
        (
            ("Acme", "Software Engineer", "Toronto"),
            ("Acme", "Product Manager", "Toronto"),
            "different roles",
        ),
        (
            ("Acme", "Software Engineer", "Toronto"),
            ("Globex", "Software Engineer", "Toronto"),
            "different companies",
        ),
        (
            ("Acme", "Software Engineer", "Toronto"),
            ("Acme", "Software Engineer", "Vancouver"),
            "different cities",
        ),
        (
            ("Acme", "Software Engineer", "Toronto"),
            ("Acme", "Software Engineer", "Remote"),
            "on-site is not the same posting as remote",
        ),
        (
            ("Acme", "Frontend Engineer", "Toronto"),
            ("Acme", "Backend Engineer", "Toronto"),
            "adjacent but distinct roles",
        ),
    ],
)
def test_genuinely_different_roles_do_not_collide(
    left: tuple, right: tuple, why: str
) -> None:
    assert fingerprint(*left) != fingerprint(*right), why


def test_fingerprint_is_stable_and_hex() -> None:
    value = fingerprint("Acme", "Engineer", "Toronto")
    assert value == fingerprint("Acme", "Engineer", "Toronto")
    assert len(value) == 64
    assert int(value, 16) >= 0
