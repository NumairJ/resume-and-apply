from services.llm.anthropic_provider import AnthropicProvider
from services.llm.base import LLMProvider

# Adding a provider means writing a class and adding it here — no calling code changes.
#
# FakeLLMProvider is deliberately absent: a fake reachable in production would serve
# invented job details and invented resumes as though they were real, which is a much
# worse failure than an honest error. Tests inject it directly.
PROVIDERS: dict[str, type[LLMProvider]] = {
    AnthropicProvider.name: AnthropicProvider,
}


class UnknownProvider(KeyError):
    """No provider is registered under that name."""


def get_provider(name: str, api_key: str, model: str | None = None) -> LLMProvider:
    try:
        provider_class = PROVIDERS[name]
    except KeyError as exc:
        raise UnknownProvider(
            f"Unknown provider {name!r}. Available: {', '.join(sorted(PROVIDERS))}"
        ) from exc
    return provider_class(api_key=api_key, model=model)


def available() -> list[dict[str, object]]:
    """What the provider switcher offers. Never includes keys."""
    return [
        {"name": name, "available_models": list(provider_class.available_models)}
        for name, provider_class in sorted(PROVIDERS.items())
    ]
