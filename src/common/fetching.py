"""Downloading a source document and preparing it for the extraction model.

A regulator publishes a tariff as an HTML table, as a text PDF, or as a scan with no text
layer at all. All three have to reach the model, so a document is carried as either text
or raw bytes and the caller never has to know which it was.

No URL and no timeout is written here: both come from config/<cc>/sources.json.
"""

import html as html_module
import logging
import re

import requests

logger = logging.getLogger(__name__)

# Some regulator sites answer a bare script with 403, so the request looks like a browser.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Documents the model can read as bytes. Anything else is treated as markup and flattened
# to text, which also keeps a whole page from eating the context window as raw HTML.
BINARY_TYPES = ("application/pdf", "image/png", "image/jpeg", "image/webp")

# A page larger than this is almost certainly a listing rather than a tariff document;
# the text is cut so that one bad URL cannot exhaust the model's context.
MAX_TEXT_CHARS = 200_000


class Document:
    """One fetched source: text to read, or bytes to hand over as-is."""

    def __init__(self, url: str, text: str = "", data: bytes = None, mime: str = ""):
        self.url = url
        self.text = text
        self.data = data
        self.mime = mime

    @property
    def is_binary(self) -> bool:
        return self.data is not None

    def as_llm_part(self):
        """The document in the shape common/llm.py expects."""
        return (self.mime, self.data) if self.is_binary else self.text

    def __bool__(self) -> bool:
        return bool(self.data) or bool(self.text.strip())


def html_to_text(markup: str) -> str:
    """Flattens markup, keeping the row and cell structure a tariff table depends on.

    A tariff is a number in a cell next to a label in another cell: drop the table shape
    and the model has to guess which number belongs to which service. Cells are separated
    by a pipe and rows by a newline, which survives far better than raw tags and costs a
    fraction of the tokens.
    """
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", markup, flags=re.S | re.I)
    text = re.sub(r"</t[dh]\s*>", " | ", text, flags=re.I)
    text = re.sub(r"</tr\s*>|<br\s*/?>|</p\s*>|</div\s*>|</li\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n[ \n]*", "\n", text)
    return text.strip()


def _decode(raw: bytes, declared: str) -> str:
    """Regulator sites still serve windows-1251, and often mislabel it."""
    encodings = ["utf-8", "cp1251"]
    match = re.search(r"charset=([\w-]+)", declared or "", re.I)
    if match:
        encodings.insert(0, match.group(1).lower())
    for encoding in encodings:
        try:
            decoded = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        # A wrong single-byte guess decodes without error but produces no Cyrillic at all.
        if len(re.findall(r"[А-Яа-яЁё]", decoded)) >= 10 or encoding == encodings[-1]:
            return decoded
    return raw.decode("utf-8", "replace")


def fetch(url: str, timeout: int) -> Document:
    """Fetches one document. Returns an empty Document on any failure — never raises.

    A source that is down must not abort the run: the city keeps its previous tariff and
    the caller reports the miss.
    """
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except Exception as e:
        logger.warning(f"Could not fetch {url}: {e}")
        return Document(url)

    if response.status_code != 200:
        logger.warning(f"Could not fetch {url}: HTTP {response.status_code}")
        return Document(url)

    content_type = (response.headers.get("Content-Type") or "").lower()
    for mime in BINARY_TYPES:
        if mime in content_type:
            logger.info(f"Fetched {url}: {mime}, {len(response.content)} bytes")
            return Document(url, data=response.content, mime=mime)

    text = html_to_text(_decode(response.content, content_type))
    if len(text) > MAX_TEXT_CHARS:
        logger.warning(f"{url}: text cut from {len(text)} to {MAX_TEXT_CHARS} chars")
        text = text[:MAX_TEXT_CHARS]
    logger.info(f"Fetched {url}: {len(text)} chars of text")
    return Document(url, text=text)


def fetch_all(urls: list, timeout: int) -> list:
    """Fetches several documents for one city, dropping the ones that failed."""
    documents = []
    for url in urls:
        document = fetch(url, timeout)
        if document:
            documents.append(document)
    return documents
