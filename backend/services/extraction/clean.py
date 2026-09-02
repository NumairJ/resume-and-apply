import html
import re

from bs4 import BeautifulSoup, Comment

# Chrome, navigation and boilerplate. Stripping these is the main defence against
# unbounded token cost: a typical posting page is mostly not the posting.
NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]

_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(markup: str) -> str:
    """Plain text from an HTML fragment, tags and entities resolved.

    Handles markup that arrives entity-escaped, which is common in JSON payloads:
    Greenhouse's `content` and schema.org `description` both come through as
    `&lt;p&gt;Text&lt;/p&gt;`. Parsing that directly yields the literal string
    "<p>Text</p>" as *text*, tags intact — so it needs one unescape first.

    The condition is what keeps that from over-firing. Unescaping unconditionally
    would turn a legitimate `&amp;` in already-decoded markup into a bare `&`, and
    could resurrect escaped angle brackets that were meant to be shown as characters.
    Escaped markup has no real tags of its own, so requiring that is a reliable test.
    """
    if "<" not in markup and "&lt;" in markup:
        markup = html.unescape(markup)
    soup = BeautifulSoup(markup, "html.parser")
    return _collapse(soup.get_text(separator="\n"))


def clean_page(markup: str) -> str:
    """Reduce a full page to the text worth sending to a model.

    A typical posting comes out a few thousand tokens, which is what keeps the LLM
    stage's cost bounded and predictable.
    """
    soup = BeautifulSoup(markup, "html.parser")

    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    return _collapse(soup.get_text(separator="\n"))


def _collapse(text: str) -> str:
    text = _WHITESPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", text).strip()
