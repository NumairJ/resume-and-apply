import anthropic

from services.llm.base import LLMError, LLMProvider, ResponseT

# Sonnet rather than Opus at the user's explicit direction, to keep generation costs
# down. Sonnet rather than Haiku because this project's prompts carry strict
# anti-fabrication rules and the guardrail chain retries on violations — a weaker model
# fails those checks more often, and every failure costs another generation.
DEFAULT_MODEL = "claude-sonnet-5"

# Output tokens bill at roughly five times input, and with adaptive thinking the effort
# level is the largest single lever on how many of them a generation spends. Dropped from
# "high" to "medium": tailoring is selection and rephrasing against an explicit rule list,
# not open-ended reasoning, and the rules the model must satisfy are checked afterwards by
# the guardrail chain rather than trusted. Raise it again if rejected first attempts start
# outnumbering clean ones — a retry costs a whole extra generation and would undo the
# saving several times over.
EFFORT = "medium"

# Not a cost: a ceiling. It bounds a runaway response, and is never itself billed.
MAX_TOKENS = 16000


class AnthropicProvider(LLMProvider):
    """Structured generation through the Anthropic API.

    **No server-side refusal fallbacks.** A model may decline a request outright
    (HTTP 200 with `stop_reason: "refusal"`); rather than rerouting to a different
    model, that is raised as an error and surfaced. Rerouting would silently change
    which model produced a resume, and `fallbacks` is not accepted by every model
    anyway — Sonnet 5 returns a 400 for it — so omitting it keeps the request identical
    across the whole model list.
    """

    name = "anthropic"
    # Opus stays offered even though it is not the default: the switcher reads this, so
    # the user can trade cost for capability per request.
    available_models = [DEFAULT_MODEL, "claude-opus-5", "claude-haiku-4-5"]

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL
        # The key is handed to the SDK and kept nowhere else on this object.
        self._client = anthropic.Anthropic(api_key=api_key)

    def __repr__(self) -> str:
        """Deliberately narrow.

        The default dataclass-ish repr would print `_client`, and an SDK client's repr
        has historically included configuration. A provider instance appears in
        tracebacks and log lines, so it says only what is safe to say.
        """
        return f"<AnthropicProvider model={self.model!r}>"

    def generate_structured(
        self, prompt: str, response_model: type[ResponseT]
    ) -> ResponseT:
        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                messages=[{"role": "user", "content": prompt}],
                output_format=response_model,
            )
        # Most specific first. Collapsing these into one `except` would lose the
        # distinction between "your key is wrong" and "try again in a minute", which
        # are the two the user can actually act on.
        except anthropic.AuthenticationError as exc:
            raise LLMError(
                "The API key was rejected. Check the key in the provider switcher."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError(
                "Rate limited by the Anthropic API. Wait a moment and try again."
            ) from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"The API rejected the request: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"The Anthropic API returned {exc.status_code}."
            ) from exc

        # stop_details is populated only on a refusal, so it is read only in that branch.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise LLMError(
                "The model declined this request"
                + (f" ({category})." if category else ".")
            )

        # parsed_output is an Optional property — None when no content block parsed.
        # Returning it unchecked would hand a None to a caller expecting a model.
        result = response.parsed_output
        if result is None:
            raise LLMError(
                f"The model returned no parseable {response_model.__name__} "
                f"(stop_reason: {response.stop_reason})."
            )
        return result
