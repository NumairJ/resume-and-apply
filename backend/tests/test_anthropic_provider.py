"""AnthropicProvider request shape and failure handling.

The SDK client is replaced with a stub, so these assert what we *send* and how we react
to what comes back. No test reaches api.anthropic.com.
"""

import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from services.llm import registry
from services.llm.anthropic_provider import DEFAULT_MODEL, AnthropicProvider
from services.llm.base import LLMError

SECRET = "sk-ant-test-do-not-log-me"


class Answer(BaseModel):
    value: str


def parsed(value: str = "ok", stop_reason: str = "end_turn", **extra):
    return SimpleNamespace(
        parsed_output=Answer(value=value) if value is not None else None,
        stop_reason=stop_reason,
        stop_details=extra.get("stop_details"),
    )


def provider_with(response=None, error: Exception | None = None) -> tuple:
    """A provider whose SDK call is replaced, plus the recorded call kwargs."""
    provider = AnthropicProvider(api_key=SECRET)
    recorded: dict = {}

    def fake_parse(**kwargs):
        recorded.update(kwargs)
        if error is not None:
            raise error
        return response

    provider._client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(parse=fake_parse))
    )
    return provider, recorded


# --- request shape ----------------------------------------------------------


def test_request_carries_the_expected_parameters() -> None:
    provider, recorded = provider_with(parsed())
    provider.generate_structured("a prompt", Answer)

    # Sonnet by the user's explicit choice, for cost. Opus stays selectable.
    assert recorded["model"] == DEFAULT_MODEL == "claude-sonnet-5"
    assert recorded["output_format"] is Answer
    assert recorded["thinking"] == {"type": "adaptive"}
    assert recorded["messages"] == [{"role": "user", "content": "a prompt"}]


def test_effort_and_max_tokens_are_pinned() -> None:
    """Both were previously unasserted, so either could change without a test noticing.

    Effort is the largest single lever on output tokens under adaptive thinking, and
    output bills at roughly five times input — a silent move back to "high" would be an
    invisible cost regression, which is exactly the kind a test should catch.
    """
    provider, recorded = provider_with(parsed())
    provider.generate_structured("a prompt", Answer)

    assert recorded["output_config"] == {"effort": "medium"}
    assert recorded["max_tokens"] == 16000


@pytest.mark.parametrize(
    "model", ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"]
)
def test_no_server_side_fallbacks_on_any_model(model: str) -> None:
    """A refusal is raised, not rerouted to a different model.

    Also avoids a real 400: a live call returned "'claude-sonnet-5' does not support
    the `fallbacks` parameter". Omitting it keeps one request shape for every model.
    """
    provider, recorded = provider_with(parsed())
    provider.model = model
    provider.generate_structured("a prompt", Answer)

    assert "fallbacks" not in recorded
    assert "betas" not in recorded


def test_no_fable_models_offered() -> None:
    assert not any("fable" in m for m in AnthropicProvider.available_models)


def test_model_can_be_overridden() -> None:
    provider, recorded = provider_with(parsed())
    provider.model = "claude-opus-5"
    provider.generate_structured("a prompt", Answer)
    assert recorded["model"] == "claude-opus-5"


def test_opus_stays_selectable() -> None:
    """Cheaper by default, but the switcher must still offer the capable option."""
    assert "claude-opus-5" in AnthropicProvider.available_models


def test_returns_the_parsed_model() -> None:
    provider, _ = provider_with(parsed("hello"))
    assert provider.generate_structured("p", Answer) == Answer(value="hello")


# --- failure handling -------------------------------------------------------


def test_refusal_is_reported_not_returned() -> None:
    """HTTP 200 with stop_reason 'refusal' — reading content here would be wrong."""
    provider, _ = provider_with(
        parsed(None, stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    )
    with pytest.raises(LLMError, match="declined"):
        provider.generate_structured("p", Answer)


def test_missing_parsed_output_is_reported() -> None:
    """parsed_output is Optional; handing None back to the caller would crash later."""
    provider, _ = provider_with(parsed(None))
    with pytest.raises(LLMError, match="no parseable"):
        provider.generate_structured("p", Answer)


def _api_error(cls, status_code: int) -> Exception:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return cls("boom", response=response, body=None)


@pytest.mark.parametrize(
    "error, expected",
    [
        (_api_error(anthropic.AuthenticationError, 401), "key"),
        (_api_error(anthropic.RateLimitError, 429), "Rate limited"),
        (_api_error(anthropic.BadRequestError, 400), "rejected the request"),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")), "reach"),
    ],
)
def test_api_errors_become_actionable_messages(error: Exception, expected: str) -> None:
    """Each failure the user can act on differently gets its own message."""
    provider, _ = provider_with(error=error)
    with pytest.raises(LLMError, match=expected):
        provider.generate_structured("p", Answer)


# --- the key must not leak --------------------------------------------------


def test_key_absent_from_repr() -> None:
    provider = AnthropicProvider(api_key=SECRET)
    assert SECRET not in repr(provider)
    assert SECRET not in str(vars(provider))


def test_key_absent_from_error_messages() -> None:
    provider, _ = provider_with(error=_api_error(anthropic.AuthenticationError, 401))
    with pytest.raises(LLMError) as raised:
        provider.generate_structured("p", Answer)
    assert SECRET not in str(raised.value)


def test_key_absent_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    """The key arrives from the browser each request; it must never reach a log file."""
    with caplog.at_level(logging.DEBUG):
        provider, _ = provider_with(parsed())
        provider.generate_structured("p", Answer)
        logging.getLogger().info("provider in use: %s", provider)

    assert SECRET not in caplog.text


# --- registry ---------------------------------------------------------------


def test_registry_builds_anthropic() -> None:
    provider = registry.get_provider("anthropic", api_key=SECRET)
    assert isinstance(provider, AnthropicProvider)


def test_registry_rejects_unknown_names() -> None:
    with pytest.raises(registry.UnknownProvider):
        registry.get_provider("not-a-provider", api_key=SECRET)


def test_fake_is_not_registered() -> None:
    """A fake reachable in production would serve invented resumes as real ones."""
    assert "fake" not in registry.PROVIDERS


def test_available_lists_models_and_no_secrets() -> None:
    listed = registry.available()
    assert {"name": "anthropic"}.items() <= listed[0].items()
    assert DEFAULT_MODEL in listed[0]["available_models"]
    assert SECRET not in str(listed)
