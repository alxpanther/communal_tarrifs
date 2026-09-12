"""Downloading a source document and preparing it for the extraction model.

A regulator publishes a tariff as an HTML table, as a text PDF, or as a scan with no text
layer at all. All three have to reach the model, so a document is carried as either text
or raw bytes and the caller never has to know which it was.

No URL and no timeout is written here: both come from config/<cc>/sources.json.
"""

import glob
import html as html_module
import logging
import os
import re
import ssl

import certifi
import requests
from requests.adapters import HTTPAdapter

from common.paths import CERTS_DIR

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


def _ssl_context() -> ssl.SSLContext:
    """The usual trusted roots, plus the intermediate certificates kept in config/certs.

    Some utility sites send their own certificate without the intermediate one that links it
    to a trusted root. A browser fetches the missing link by itself; Python does not, and the
    site fails with "unable to get local issuer certificate" — the Kazan водоканал does exactly
    that. Each file in config/certs is such an intermediate, downloaded from the address the
    site's own certificate names for its issuer. Nothing here weakens verification: every chain
    still has to end at a standard root.
    """
    context = ssl.create_default_context(cafile=certifi.where())
    for path in sorted(glob.glob(os.path.join(CERTS_DIR, "*.pem"))):
        context.load_verify_locations(path)
    return context


class _TrustAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = _SSL_CONTEXT
        return super().init_poolmanager(*args, **kwargs)


_SSL_CONTEXT = _ssl_context()
_SESSION = requests.Session()
_SESSION.mount("https://", _TrustAdapter())
_SESSION.headers["User-Agent"] = USER_AGENT

# A tariff as a Russian-language page prints it: "3 800,68". Counting them is a cheap sign of
# whether a page carries tariffs at all or is a menu, an article, or a disguised 404.
PRICE = re.compile(r"\d,\d{2}\b")


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


CHARSET = re.compile(r"charset=[\"']?([\w-]+)", re.I)


def _declared_charset(declared: str, raw: bytes) -> str:
    """The encoding the response claims, from the header or from the page's own meta tag."""
    match = CHARSET.search(declared or "") or CHARSET.search(raw[:2048].decode("ascii", "ignore"))
    return match.group(1).lower() if match else ""


def _decode(raw: bytes, declared: str) -> str:
    """Regulator sites still serve windows-1251, and mislabel it in both directions.

    Valid UTF-8 is the one reliable signal. Single-byte text almost never decodes as UTF-8
    by accident, while a single-byte decoder accepts any bytes at all and silently turns
    real UTF-8 into mojibake — which is how an Azerbaijani page came back as "tariflЙ™r".
    So UTF-8 wins whenever it decodes, and the declared encoding is used only when it
    does not. Judging the result by the Cyrillic in it is what broke Azerbaijani and
    Armenian: those pages carry none, and a correct UTF-8 decode looked like a failure.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for encoding in (_declared_charset(declared, raw), "cp1251"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def fetch(url: str, timeout: int) -> Document:
    """Fetches one document. Returns an empty Document on any failure — never raises.

    A source that is down must not abort the run: the city keeps its previous tariff and
    the caller reports the miss.
    """
    try:
        response = _SESSION.get(url, timeout=timeout)
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


def probe(url: str, timeout: int) -> dict:
    """Whether a source can be read from this machine, and whether it looks like a tariff.

    Downloads the document but calls no model, so it costs nothing. Returns the status, the type,
    the size, how many price-like numbers the text carries, and whether it reads like a "page
    not found" served with a 200 — which is how one of the Samara addresses failed.
    """
    from common import pdf  # local: common.pdf imports this module

    try:
        response = _SESSION.get(url, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {str(e)[:160]}"}
    result = {"ok": response.status_code == 200, "status": response.status_code,
              "bytes": len(response.content)}
    if not result["ok"]:
        return result

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/pdf" in content_type:
        text = pdf.text_of(response.content)
        result["kind"] = "pdf, scan" if pdf.is_scan(text) else "pdf"
    elif any(mime in content_type for mime in BINARY_TYPES):
        text, result["kind"] = "", "image"
    else:
        text, result["kind"] = html_to_text(_decode(response.content, content_type)), "html"
    result["chars"] = len(text)
    result["prices"] = len(PRICE.findall(text))
    low = text.lower()
    result["looks_like_404"] = "404" in low and ("не найден" in low or "not found" in low)
    return result
