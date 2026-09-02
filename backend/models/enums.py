from enum import StrEnum


class ApplicationStatus(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ExtractionMethod(StrEnum):
    """Which stage of the extraction pipeline produced a posting.

    Recorded on every job_postings row so tests and the README can both show which
    path handled which posting — the cheap paths (jsonld, the ATS adapters) should
    be doing most of the work, and this is how that claim stays checkable.
    """

    JSONLD = "jsonld"
    ATS_GREENHOUSE = "ats_greenhouse"
    ATS_LEVER = "ats_lever"
    ATS_ASHBY = "ats_ashby"
    LLM = "llm"
