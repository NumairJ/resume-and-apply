from typing import Any

from fastapi import APIRouter

from services.llm import registry

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[dict])
def list_providers() -> Any:
    """Providers and their models, so the switcher isn't hardcoded in the frontend.

    Contains no credentials — keys live in the browser and arrive per request.
    """
    return registry.available()
