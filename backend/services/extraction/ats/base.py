from abc import ABC, abstractmethod

import httpx

from models.enums import ExtractionMethod
from schemas.application import JobPostingCreate


class ATSAdapter(ABC):
    """A dedicated reader for one applicant tracking system.

    Adapters exist because these platforms expose structured JSON that is far more
    reliable than scraping their rendered HTML. An adapter therefore never sees the
    fetched page — it recognises the URL, pulls the identifiers out of it, and calls
    the platform's own API.
    """

    name: str
    method: ExtractionMethod

    @abstractmethod
    def match(self, url: str) -> dict[str, str] | None:
        """Identifiers pulled from the URL, or None if this adapter can't handle it.

        Must not perform I/O — matching happens before anything is fetched, which is
        what lets a recognised URL skip the page download entirely.
        """

    @abstractmethod
    def parse(
        self, url: str, identifiers: dict[str, str], client: httpx.Client
    ) -> JobPostingCreate:
        """Call the platform API and map its response onto our schema."""
