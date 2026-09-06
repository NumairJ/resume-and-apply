"""The anti-fabrication suite — the highest-value tests in the project.

These are what make "this doesn't fabricate" checkable rather than a claim in a README.
Each rejection test feeds the chain deliberately fabricated output and asserts it is
caught; `test_a_legitimate_rewrite_passes` is the counterweight, because a chain that
rejected everything would produce an identically green run while being useless.

The chain was loosened deliberately after it spent a live run rejecting the candidate's
own words, so the counterweights matter more than they used to: several tests below
exist only to prove a relaxed check has not gone soft.
"""

import pytest

from schemas.profile import Profile
from schemas.resume import TailoredBullet, TailoredExperience, TailoredProject
from services import guardrails
from services.guardrails import overlap_ratio
from services.guardrails.references import ProfileIndex, numbers_in
from tests.factories import valid_resume


# --- the counterweight ------------------------------------------------------


def test_a_legitimate_rewrite_passes(profile: Profile) -> None:
    """Without this, a chain that rejected everything would look identically green."""
    assert guardrails.run_all(valid_resume(), profile) == []


def test_heavily_reworded_but_faithful_bullet_passes(profile: Profile) -> None:
    """Rephrasing is the whole point of tailoring; only invention is forbidden."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Reduced error rates across the payment service by hardening its retry path"
    )
    assert guardrails.run_all(resume, profile) == []


# --- the rejections ---------------------------------------------------------


def test_invented_employer_is_rejected(profile: Profile) -> None:
    """In this schema an invented employer is a reference to an experience that isn't there."""
    resume = valid_resume()
    resume.experiences.append(
        TailoredExperience(
            source="E9",
            bullets=[TailoredBullet(source="E9B1", text="Led platform engineering")],
        )
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "E9" in v.message for v in violations)


def test_shifted_date_is_rejected(profile: Profile) -> None:
    """E1 ran 2021-2024. Claiming 2015 on one of its bullets is a shifted date.

    2015 is a real year in this profile - the degree started then - so a check against
    the profile as a whole would wave this through. Bullets are scoped to their own
    experience precisely so it doesn't.
    """
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Hardened the payment service retry path, reducing error rates since 2015"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "dates" and "2015" in v.message for v in violations)


def test_year_outside_the_whole_profile_is_rejected_in_the_summary(
    profile: Profile,
) -> None:
    resume = valid_resume()
    resume.summary = "Engineer working on payment systems since 2011."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "dates" and "2011" in v.message for v in violations)


def test_known_limit_summary_year_from_elsewhere_in_the_profile(
    profile: Profile,
) -> None:
    """Documents a real gap rather than pretending it doesn't exist.

    "since 2015" in the summary is false - payments work started in 2021 - but 2015 is
    a genuine profile year (the degree), and the summary has no context to scope
    against. Pinned so the limitation is visible and any future fix is noticed.
    """
    resume = valid_resume()
    resume.summary = "Engineer working on payment systems since 2015."
    violations = guardrails.run_all(resume, profile)
    assert not any(v.check == "dates" for v in violations)


def test_future_employment_date_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.summary = "Engineer leading payments through 2099."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "dates" and "2099" in v.message for v in violations)


def test_skill_absent_from_the_profile_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.skills = ["Python", "Kubernetes"]
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "skills" and "Kubernetes" in v.message for v in violations)


def test_untraceable_bullet_is_rejected(profile: Profile) -> None:
    """Cites a real bullet, but the text is a different claim entirely."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Managed a team of eight engineers and owned the annual infrastructure budget"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "traceability" and "E1B1" in v.message for v in violations)


# --- further reference integrity --------------------------------------------


def test_bullet_from_another_experience_is_rejected(profile: Profile) -> None:
    """A real bullet, but attached to the wrong employer, which changes its meaning."""
    resume = valid_resume()
    resume.experiences[0].bullets.append(
        TailoredBullet(
            source="E2B1", text="Built internal React dashboards for the support team"
        )
    )
    violations = guardrails.run_all(resume, profile)
    assert any(
        v.check == "references" and "different experience" in v.message
        for v in violations
    )


def test_nonexistent_bullet_of_a_real_experience_is_rejected(
    profile: Profile,
) -> None:
    resume = valid_resume()
    resume.experiences[0].bullets.append(
        TailoredBullet(source="E1B9", text="Something that was never recorded")
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "E1B9" in v.message for v in violations)


def test_duplicated_experience_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.experiences.append(TailoredExperience(source="E1", bullets=[]))
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "more than once" in v.message for v in violations)


# --- projects ---------------------------------------------------------------
#
# Projects reach the resume the same way experiences do — by label, with every factual
# field filled from the row — so they need the same rejections proved against them.


def test_invented_project_is_rejected(profile: Profile) -> None:
    """The model cannot write a project name, so citing one that isn't there is how an
    invented project would have to appear."""
    resume = valid_resume()
    resume.projects.append(TailoredProject(source="P9"))
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "P9" in v.message for v in violations)


def test_duplicated_project_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.projects.append(TailoredProject(source="P1"))
    violations = guardrails.run_all(resume, profile)
    assert any(
        v.check == "references" and "P1" in v.message and "more than once" in v.message
        for v in violations
    )


def test_invented_project_bullet_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.projects[0].bullets.append(
        TailoredBullet(source="P1B9", text="Something that was never recorded")
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "P1B9" in v.message for v in violations)


def test_a_bullet_from_another_project_is_rejected(profile: Profile) -> None:
    """A real project bullet, but hung under the wrong project.

    Cited under P2, `P1B1` resolves perfectly well — which is exactly why resolution
    alone is not enough. The claim would appear under a project that never made it.
    """
    resume = valid_resume()
    resume.projects.append(
        TailoredProject(
            source="P2",
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
    )
    violations = guardrails.run_all(resume, profile)
    assert any(
        v.check == "references" and "different project" in v.message for v in violations
    )


def test_untraceable_project_bullet_is_rejected(profile: Profile) -> None:
    """Project bullets are held to the same overlap floor as experience bullets.

    They briefly were not. While a project was one long `description`, a one-line resume
    entry could retain at most a fifth of a sixty-word paragraph, so a separate
    containment measure existed for projects. Storing bullets as rows removed the
    mismatch — these are the same length as experience bullets — and the special case
    went with it.
    """
    resume = valid_resume()
    resume.projects[0].bullets[0].text = (
        "Led a distributed team building trading infrastructure"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "traceability" and "P1B1" in v.message for v in violations)


def test_a_project_with_no_bullets_may_still_be_selected(profile: Profile) -> None:
    """P2 in the fixture is a bare name. Its name is a real profile fact, and requiring
    bullets would drop a legitimate entry for having been recorded tersely."""
    resume = valid_resume()
    resume.projects.append(TailoredProject(source="P2"))
    assert guardrails.run_all(resume, profile) == []


# --- figures -----------------------------------------------------------------
#
# The check word overlap cannot do. An inflated metric is the most damaging thing a
# tailored resume can carry, and the most invisible: every word around it is faithful,
# so traceability scores it highly and waves it through.


def test_an_inflated_metric_is_rejected(profile: Profile) -> None:
    """E1B1 records "from 2.1% to 0.3%". An 86% reduction is arithmetic the candidate
    never claimed, and it is the figure a reference check would disprove."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Reduced payment service error rates by 86% by hardening the retry path"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "metrics" and "86%" in v.message for v in violations)


def test_the_metric_violation_quotes_the_source(profile: Profile) -> None:
    """The retry has to be able to act on this, which means seeing the real figures."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Reduced payment service error rates by 86% by hardening the retry path"
    )
    message = next(
        v.message for v in guardrails.run_all(resume, profile) if v.check == "metrics"
    )
    assert "2.1% to 0.3%" in message


def test_a_figure_borrowed_from_a_sibling_bullet_is_rejected(profile: Profile) -> None:
    """Both bullets are real, and the combination is not. 40,000 belongs to the billing
    migration, not to the retry path, so a bullet may only carry its own source's
    figures."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Hardened the payment service retry path, reducing error rates for 40,000 "
        "accounts"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "metrics" and "E1B1" in v.message for v in violations)


def test_keeping_the_original_figures_passes(profile: Profile) -> None:
    """The counterweight: the check must not push the model into dropping real numbers,
    which are the most persuasive thing on a resume."""
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Hardened the payment retry path, cutting payment service error rates from "
        "2.1% to 0.3%"
    )
    assert guardrails.run_all(resume, profile) == []


def test_shortening_a_figure_is_not_inventing_one(profile: Profile) -> None:
    """E1B2 says "40,000". Writing it as "40k" is tightening, which is what tailoring is
    for — and the reference implementation this check came from would have flagged it."""
    resume = valid_resume()
    resume.experiences[0].bullets[1].text = (
        "Migrated the billing database to Postgres with zero downtime for 40k accounts"
    )
    assert guardrails.run_all(resume, profile) == []


def test_an_invented_figure_in_the_summary_is_rejected(profile: Profile) -> None:
    """The summary cites no source, so it is checked against every figure recorded."""
    resume = valid_resume()
    resume.summary = "Engineer who cut payment error rates by 92% across the platform."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "metrics" and "92%" in v.message for v in violations)


def test_small_counts_and_years_do_not_fire(profile: Profile) -> None:
    """Two exclusions, both there to keep this check signal rather than noise.

    Incidental counts assert nothing on their own, and years belong to `check_dates`,
    which knows the range each claim may fall in — reporting them here as well would
    raise two violations for one mistake and hand the model a contradictory retry note.
    """
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Hardened the payment service retry path across 3 regions, reducing error "
        "rates through 2024"
    )
    violations = guardrails.run_all(resume, profile)
    assert not any(v.check == "metrics" for v in violations)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("cut costs by $1,200.00", {"1200"}),
        ("supported 40,000 accounts", {"40000"}),
        ("supported 40k accounts", {"40000"}),
        ("reached 1.2M users", {"1200000"}),
        ("improved throughput 3x", {"3x"}),
        ("from 2.1% to 0.3%", {"2.1%", "0.3%"}),
        # Two separate figures: the unit is not decoration, so "40" does not satisfy a
        # claim of "40%" and the pair is kept apart.
        ("grew 40% on 40 servers", {"40%", "40"}),
        ("shipped in 2024 with 3 engineers", set()),
    ],
)
def test_number_normalisation(text: str, expected: set[str]) -> None:
    assert numbers_in(text) == expected


# --- the profile's own words are not fabrication -----------------------------
#
# A live run against a real posting was refused three times for "naming" RESTful API,
# Team Builder and Convolutional Neural Network — every one of them typed by the user
# into their own bullets. A scan for capitalised phrases used to reject any that were
# not mined from the profile, and it is gone. These pin the property that outlasted it:
# a faithful rewrite carrying the candidate's own wording passes the whole chain.


def test_a_rewrite_keeping_a_proper_noun_from_its_source_passes(
    profile: Profile,
) -> None:
    profile.experiences[0].bullets[0].text = (
        "Reduced payment service error rates by hardening the Apache Kafka retry path"
    )
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Hardened the Apache Kafka retry path, reducing payment service error rates"
    )
    assert guardrails.run_all(resume, profile) == []


def test_a_rewrite_keeping_a_proper_noun_from_a_project_bullet_passes(
    profile: Profile,
) -> None:
    """The exact live failure: the fixture's own bullet says "RESTful API"."""
    resume = valid_resume()
    # Cites P1B2, the fixture bullet that actually contains the phrase.
    resume.projects[0].bullets = [
        TailoredBullet(
            source="P1B2",
            text="Built a RESTful API for the writing archive, backed by Postgres",
        )
    ]
    assert guardrails.run_all(resume, profile) == []


def test_an_unfamiliar_organisation_in_the_summary_is_accepted(
    profile: Profile,
) -> None:
    """The accepted cost of removing the proper-noun scan, pinned rather than left to be
    discovered.

    The summary is free text and it prints on the resume, so this is a real gap. It is
    accepted because the check that closed it was rejecting the candidate's own words
    several times per live run, and because the structural guarantee is untouched: the
    model has no field in which to write an employer, so this cannot become a job on the
    resume — only a sentence the candidate will read in the preview before applying.
    """
    resume = valid_resume()
    resume.summary = "Software engineer, previously at Goldman Sachs."
    assert not any(v.check == "fabrication" for v in guardrails.run_all(resume, profile))


# --- skill promotion ---------------------------------------------------------


def test_a_skill_promoted_from_a_project_stack_passes(profile: Profile) -> None:
    """Docker is in P1's stack and is not a skills row. Requiring it to be typed a
    second time under Settings rejected honest output — the candidate plainly claims it.
    """
    resume = valid_resume()
    resume.skills = ["Python", "Docker"]
    assert guardrails.run_all(resume, profile) == []


def test_a_skill_promoted_from_a_bullet_passes(profile: Profile) -> None:
    resume = valid_resume()
    resume.skills = ["React"]  # E2B1 says "Built internal React dashboards"
    assert guardrails.run_all(resume, profile) == []


def test_promotion_does_not_mean_anything_goes(profile: Profile) -> None:
    """The counterweight for the loosest check in the chain. A membership test widened
    until it accepted everything would make every test above pass while destroying the
    guarantee they exist to protect."""
    resume = valid_resume()
    resume.skills = ["Kubernetes", "Rust", "Terraform"]
    violations = guardrails.run_all(resume, profile)
    assert {v.check for v in violations} == {"skills"}
    assert len(violations) == 3


# --- how profile text is matched ---------------------------------------------


def test_mentions_ignores_accents(profile: Profile) -> None:
    """The old normaliser kept only `[a-z0-9]`, so "Pokémon" became "pok mon" and a
    résumé spelling it "Pokemon" compared unequal to the profile's own project name.
    Not hypothetical — that is a real project in the live database."""
    profile.projects[1].name = "Pokémon PokéDex"
    index = ProfileIndex(profile)

    assert index.mentions("Pokemon PokeDex")
    assert index.mentions("Pokémon PokéDex")


def test_mentions_matches_whole_words_not_substrings(profile: Profile) -> None:
    """Raw containment would read every profile mentioning Django as claiming Go."""
    profile.experiences[0].bullets[0].text = "Reduced error rates in the Django service"
    index = ProfileIndex(profile)

    assert not index.mentions("Go")
    assert index.mentions("Django")


def test_mentions_does_not_match_across_two_fields(profile: Profile) -> None:
    """Fields are matched whole, not joined into one document. P1 is named "Portfolio
    Site" and its stack begins "Next.js"; joining them would make "Site Next" findable.
    """
    index = ProfileIndex(profile)

    assert index.mentions("Portfolio Site") and index.mentions("Next.js")
    assert not index.mentions("Site Next.js")


# --- the overlap measure itself ---------------------------------------------


@pytest.mark.parametrize(
    "rewrite, source, expected_pass",
    [
        ("Hardened the retry path", "Hardened the retry path", True),
        ("Hardened the payment retry path at scale", "Hardened the retry path", True),
        ("Ran the marketing budget", "Hardened the retry path", False),
        ("", "Hardened the retry path", False),
    ],
)
def test_overlap_ratio_behaviour(
    rewrite: str, source: str, expected_pass: bool
) -> None:
    assert (overlap_ratio(rewrite, source) >= guardrails.MIN_BULLET_OVERLAP) is expected_pass


def test_overlap_ignores_stopwords(profile: Profile) -> None:
    """Two sentences must not look similar merely for sharing 'the' and 'and'."""
    assert overlap_ratio("The and of the", "Hardened the retry path") == 0.0


def test_the_floor_admits_an_aggressive_but_faithful_rewrite(
    profile: Profile,
) -> None:
    """Pins the drop from 0.35 to 0.25 deliberately rather than incidentally.

    Three of E1B2's nine meaningful words survive — 33%, which the old floor rejected.
    It is plainly the same claim, and the figures inside a bullet are now checked
    directly, which is what made the room to loosen this.
    """
    rewrite = "Ported the billing store onto Postgres with zero downtime"
    ratio = overlap_ratio(rewrite, profile.experiences[0].bullets[1].text)
    assert 0.25 <= ratio < 0.35

    resume = valid_resume()
    resume.experiences[0].bullets[1].text = rewrite
    assert guardrails.run_all(resume, profile) == []


def test_violations_read_usefully(profile: Profile) -> None:
    """The retry feeds these back to the model, so they have to name the problem."""
    resume = valid_resume()
    resume.skills = ["Kubernetes"]
    violation = guardrails.run_all(resume, profile)[0]
    assert str(violation).startswith("[skills]")
    assert "Kubernetes" in str(violation)


# --- regressions found by live runs ------------------------------------------


def test_faithful_elaboration_passes(profile: Profile) -> None:
    """A live run rejected this. Overlap is measured against the source, not the rewrite.

    Every content word of the original survives; the rewrite merely adds framing for
    the posting. Dividing by the rewrite's length punished exactly the behaviour
    tailoring is supposed to produce.
    """
    resume = valid_resume()
    resume.experiences[0].bullets[0].text = (
        "Reduced payment service error rates by hardening the retry path, improving "
        "checkout reliability for customers during peak traffic windows"
    )
    assert guardrails.run_all(resume, profile) == []
