import uuid
from typing import Annotated

from fastapi import Header, HTTPException, status

from core.config import settings
from services.llm import registry
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


def get_llm_provider(
    x_llm_provider: Annotated[str | None, Header()] = None,
    x_llm_model: Annotated[str | None, Header()] = None,
    x_llm_api_key: Annotated[str | None, Header()] = None,
) -> LLMProvider:
    """Resolve the provider for this request from headers, with an .env fallback.

    The key arrives per-request from the browser, where the provider switcher holds it
    in localStorage. It is used to construct the client and **never written to the
    database or a log** — the only copy the server keeps is the one inside the SDK
    client for the life of the request.

    The `.env` fallback exists for local development so the app is usable without
    pasting a key into the UI on every session.

    `FakeLLMProvider` is deliberately not reachable here: a fake in production would
    serve invented job details and invented resumes as though they were real.
    """
    name = x_llm_provider or registry.AnthropicProvider.name
    api_key = x_llm_api_key or settings.anthropic_api_key

    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_PROVIDER_MESSAGE)

    try:
        return registry.get_provider(name, api_key=api_key, model=x_llm_model)
    except registry.UnknownProvider as exc:
        # str() on a KeyError adds quotes; args[0] is the message we wrote.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, exc.args[0]
        ) from exc
