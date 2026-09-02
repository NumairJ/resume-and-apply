"""The last-resort extraction stage.

Only reached when a page has no ATS adapter, no JSON-LD, and passed the scoring gate.
Everything before this point is free; this is the one stage that costs money, which is
why so much work goes into not arriving here.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from models.enums import ExtractionMethod
from schemas.application import JobPostingCreate
from services.llm.base import LLMProvider

PROMPT_VERSION = "extract_job.v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / f"{PROMPT_VERSION}.md"


class ExtractedJob(BaseModel):
    """The structured shape the model is constrained to return."""

    company: str = Field(description="The hiring organisation")
    title: str = Field(description="The role title on its own")
    location: str | None = None
    employment_type: str | None = None
    description: str | None = None
    requirements: str | None = None
    salary_range: str | None = None


def extract(text: str, source_url: str, provider: LLMProvider) -> JobPostingCreate:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(page_text=text)
    result = provider.generate_structured(prompt, ExtractedJob)

    return JobPostingCreate(
        **result.model_dump(),
        source_url=source_url,
        raw_text=text,
        extraction_method=ExtractionMethod.LLM,
    )
