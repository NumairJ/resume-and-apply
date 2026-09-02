from services.extraction.ats.base import ATSAdapter
from services.extraction.ats.greenhouse import GreenhouseAdapter

# Adding a platform means writing an adapter and appending it here. Nothing that calls
# `find` changes. Lever and Ashby are the next two — both expose comparable JSON APIs.
REGISTRY: list[ATSAdapter] = [
    GreenhouseAdapter(),
]


def find(url: str) -> tuple[ATSAdapter, dict[str, str]] | None:
    """The first adapter that recognises this URL, with the ids it pulled out.

    Pure string work, no I/O — which is why this runs before anything is fetched.
    """
    for adapter in REGISTRY:
        if identifiers := adapter.match(url):
            return adapter, identifiers
    return None


__all__ = ["ATSAdapter", "GreenhouseAdapter", "REGISTRY", "find"]
