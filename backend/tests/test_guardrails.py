"""The anti-fabrication suite — the highest-value tests in the project.

These are what make "this doesn't fabricate" checkable rather than a claim in a README.
Each rejection test feeds the chain deliberately fabricated output and asserts it is
caught; `test_a_legitimate_rewrite_passes` is the counterweight, because a chain that
rejected everything would produce an identically green run while being useless.
"""

import pytest

from schemas.profile import Profile
from schemas.resume import (
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)
from services import guardrails
from services.guardrails import MIN_PROJECT_GROUNDING, grounding_ratio, overlap_ratio
from services.guardrails.references import PROPER_PHRASE
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


# --- the five rejections ----------------------------------------------------


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


def test_invented_employer_named_in_the_summary_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.summary = "Engineer who led payments at Initech Global before Northwind Systems."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "fabrication" and "Initech" in v.message for v in violations)


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
    resume.projects.append(TailoredProject(source="P9", text="A thing I never built"))
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "references" and "P9" in v.message for v in violations)


def test_duplicated_project_is_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.projects.append(TailoredProject(source="P1", text=""))
    violations = guardrails.run_all(resume, profile)
    assert any(
        v.check == "references" and "P1" in v.message and "more than once" in v.message
        for v in violations
    )


def test_untraceable_project_rewrite_is_rejected(profile: Profile) -> None:
    """Everything the line claims has to come from the recorded description."""
    resume = valid_resume()
    resume.projects[0].text = "Led a distributed team building trading infrastructure"
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "traceability" and "P1" in v.message for v in violations)


def test_a_project_line_may_say_much_less_than_the_description(
    profile: Profile,
) -> None:
    """Projects are measured by grounding, not retention, and this is why.

    A profile's project description is a paragraph of notes; the résumé needs one line.
    Under the retention measure bullets use, a 12-word line drawn from a 60-word
    description can score at most ~20% however faithful it is — so the check had no
    passing answer and rejected every correct rewrite, while the prompt was
    simultaneously demanding a one-page résumé.
    """
    source = profile.projects[0].description
    concise = "Personal site with a typed API layer"

    assert overlap_ratio(concise, source) < 0.35  # would have been rejected
    assert grounding_ratio(concise, source) == 1.0  # every word is supported

    resume = valid_resume()
    resume.projects[0].text = concise
    assert guardrails.run_all(resume, profile) == []


def test_grounding_measures_the_rewrite_not_the_source() -> None:
    source = "Built a task manager in Python with a Postgres store"

    # Says less than the source: fully supported.
    assert grounding_ratio("Built a task manager in Python", source) == 1.0
    # Says more than the source: the added claims are unsupported.
    assert grounding_ratio(
        "Shipped a trading platform for Boeing in Rust across three regions", source
    ) < MIN_PROJECT_GROUNDING
    # Nothing asserted, nothing to support — the empty case is not a violation.
    assert grounding_ratio("", source) == 1.0


def test_description_written_for_a_project_that_has_none_is_rejected(
    profile: Profile,
) -> None:
    """P2 in the fixture profile is a bare name. Text for it is not a rephrasing of
    anything — there is no source — so it is invention by definition."""
    resume = valid_resume()
    resume.projects.append(
        TailoredProject(source="P2", text="A fast solver written in Rust")
    )
    violations = guardrails.run_all(resume, profile)
    assert any(
        v.check == "traceability" and "P2" in v.message and "nothing to rewrite" in v.message
        for v in violations
    )


def test_a_project_with_no_description_may_still_be_selected(profile: Profile) -> None:
    """The name and dates are real profile facts. Requiring a description would drop a
    legitimate entry for having been recorded tersely."""
    resume = valid_resume()
    resume.projects.append(TailoredProject(source="P2", text=""))
    assert guardrails.run_all(resume, profile) == []


def test_dropping_a_project_description_entirely_passes(profile: Profile) -> None:
    """Omission is always allowed. Only writing something new is not."""
    resume = valid_resume()
    resume.projects[0].text = ""
    assert guardrails.run_all(resume, profile) == []


def test_project_text_is_covered_by_the_fabrication_check(profile: Profile) -> None:
    """Project descriptions are free text, so they get the same net as bullets."""
    resume = valid_resume()
    resume.projects[0].text = (
        "Personal site built with Next.js and a typed API layer, deployed on "
        "Northwind Cloud"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "fabrication" and "Northwind Cloud" in v.message for v in violations)


def test_project_text_is_covered_by_the_style_check(profile: Profile) -> None:
    resume = valid_resume()
    resume.projects[0].text = (
        "Personal site built with Next.js and a typed API layer, a testament to "
        "deployment"
    )
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "style" and "P1" in v.message for v in violations)


# --- the profile's own words are not fabrication -----------------------------
#
# A live run against a real posting was refused three times for "naming" RESTful API,
# Team Builder and Convolutional Neural Network — every one of them typed by the user
# into their own bullets and project descriptions. The vocabulary was built from *names*
# only (company, title, school, degree, project name, skill, link label), so a proper
# noun that lived solely in free text was unknown to the check, and any faithful rewrite
# carrying it was rejected as invented. Adding projects to the résumé made this near
# certain; it had been latent for bullets since Phase 4.


def test_a_proper_noun_from_a_stored_bullet_is_not_fabrication(
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


def test_a_proper_noun_from_a_stored_project_description_is_not_fabrication(
    profile: Profile,
) -> None:
    """The exact live failure: the fixture's description says "RESTful API"."""
    resume = valid_resume()
    resume.projects[0].text = "Built a RESTful API for the writing archive"
    assert guardrails.run_all(resume, profile) == []


def test_a_proper_noun_from_the_profile_summary_is_not_fabrication(
    profile: Profile,
) -> None:
    profile.summary = "Backend engineer, mostly Google Cloud Platform and Postgres."
    resume = valid_resume()
    resume.summary = "Backend engineer working in Google Cloud Platform and Postgres."
    assert guardrails.run_all(resume, profile) == []


def test_an_invented_organisation_still_fails(profile: Profile) -> None:
    """The counterweight. A vocabulary widened until it accepted everything would make
    every test above pass while destroying the guarantee they exist to protect."""
    resume = valid_resume()
    resume.summary = "Software engineer, previously at Goldman Sachs."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "fabrication" and "Goldman Sachs" in v.message for v in violations)


def test_words_recombined_across_the_profile_are_still_fabrication(
    profile: Profile,
) -> None:
    """Why phrases are mined rather than loose words.

    "Northwind" and "Systems" both appear in the profile — the first as a company, the
    second nowhere as a pair with it. Interning individual tokens would let a model
    assemble an employer nobody has worked for out of the profile's own vocabulary.
    """
    profile.experiences[0].bullets[0].text = "Built Northwind tooling for Contoso Systems"
    resume = valid_resume()
    resume.summary = "Engineer at Contoso Northwind."
    violations = guardrails.run_all(resume, profile)
    assert any(v.check == "fabrication" for v in violations)


def test_a_line_break_does_not_manufacture_a_proper_noun(profile: Profile) -> None:
    """The fixture description breaks the line between "Bootstrap" and "Built".

    Joining phrase words on `\\s+` matches that newline and yields "Bootstrap Built" — a
    name nobody wrote, which therefore matches nothing in any vocabulary and is reported
    as fabrication. Real profiles are full of such line breaks.
    """
    found = PROPER_PHRASE.findall("Styled with Bootstrap\nBuilt a RESTful API")
    assert "Bootstrap Built" not in found
    # The genuine phrase on the second line is still found — the fix narrows what counts
    # as a word gap, it does not stop the pattern working.
    assert found == ["RESTful API"]
    # And a real two-word name on one line is unaffected.
    assert PROPER_PHRASE.findall("Styled with Bootstrap Framework today") == [
        "Bootstrap Framework"
    ]


# --- style ------------------------------------------------------------------


def test_llm_tics_are_rejected(profile: Profile) -> None:
    resume = valid_resume()
    resume.summary = "A results-driven professional ready to delve into new challenges."
    violations = guardrails.run_all(resume, profile)
    assert sum(v.check == "style" for v in violations) >= 1


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


def test_rationale_may_name_the_target_job(profile: Profile) -> None:
    """Also a live rejection: the rationale named the role being applied for.

    Explaining the match necessarily names the posting. The rationale is shown to the
    candidate as an explanation, not printed on the resume.
    """
    resume = valid_resume()
    resume.rationale = (
        "The Account Executive role at Globex Systems asks for payment reliability, "
        "which the Northwind Systems work demonstrates directly."
    )
    vocabulary = {"account executive", "globex systems"}

    assert guardrails.run_all(resume, profile, posting_vocabulary=vocabulary) == []
    # Without that licence it is still flagged, so the check has not simply gone soft.
    assert any(
        v.check == "fabrication" for v in guardrails.run_all(resume, profile)
    )


def test_the_resume_itself_gets_no_posting_licence(profile: Profile) -> None:
    """The summary may not claim the target company; only the rationale may name it."""
    resume = valid_resume()
    resume.summary = "Engineer who delivered payment reliability at Globex Systems."
    violations = guardrails.run_all(
        resume, profile, posting_vocabulary={"globex systems"}
    )
    assert any(v.check == "fabrication" and "Globex" in v.message for v in violations)
