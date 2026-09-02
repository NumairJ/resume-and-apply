import httpx

# A real browser UA. Plenty of career sites serve a bot page or a 403 to the default
# httpx agent, and the resulting HTML scores as "not a job posting" for the wrong reason.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MAX_BYTES = 2_000_000


class FetchError(RuntimeError):
    """The page could not be retrieved. Distinct from 'this is not a job posting'."""


def build_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def fetch(url: str, client: httpx.Client) -> str:
    """Retrieve a page as text, refusing anything too large or not HTML.

    The size cap is enforced *while streaming*. Checking `len(response.text)` after the
    fact would mean a pathological page had already been read into memory in full,
    which is the exact thing the cap exists to prevent.
    """
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if content_type and "html" not in content_type.lower():
                raise FetchError(f"expected HTML, got {content_type!r}")

            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FetchError(f"page exceeds {MAX_BYTES} bytes")
                chunks.append(chunk)

            body = b"".join(chunks)
            encoding = response.encoding or "utf-8"
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"upstream returned {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc

    return body.decode(encoding, errors="replace")
