from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/core/config.py -> backend/ -> repo root. Resolving from __file__ rather than the
# working directory means bare-metal dev picks up the root .env whatever directory uvicorn
# or alembic is invoked from. In the container this path doesn't exist and is ignored —
# compose supplies the same values as real environment variables.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str
    resume_dir: Path = Path("/data/resumes")
    anthropic_api_key: str | None = None


settings = Settings()
