import uuid

from fastapi import HTTPException, status

from services.llm.base import LLMProvider

# This app runs locally for one person and has no authentication. Rather than thread a
# nullable user through every query, the schema keeps real users/FKs and the initial
# migration seeds exactly one row with this ID.
#
# This constant is the single seam to change if multi-user ever arrives: swap the
# dependency below for one that resolves a session or token, and nothing else moves.
#
# The initial migration hard-codes the same literal. That duplication is deliberate —
# migrations must keep working as application code changes, so they don't import it.
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    """FastAPI dependency resolving the acting user."""
    return DEFAULT_USER_ID


NO_PROVIDER_MESSAGE = (
    "No LLM provider is configured yet, so pages that need one cannot be read. "
    "Postings on a supported job board still work."
)


def get_llm_provider() -> LLMProvider:
    """Resolve the provider for this request.

    Phase 4 replaces this body with the registry lookup that reads the provider name
    and API key from request headers. Until then it refuses.

    `FakeLLMProvider` is deliberately *not* wired in as a fallback: a fake reachable
    in production would serve invented job details as though they had been extracted
    from the page, which is a much worse failure than an honest 503. Tests override
    the injection point directly.
    """
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_PROVIDER_MESSAGE)
