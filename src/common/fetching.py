"""Downloading a source document and preparing it for the extraction model.

A regulator publishes a tariff as an HTML table, as a text PDF, or as a scan with no text
layer at all. All three have to reach the model, so a document is carried as either text
or raw bytes and the caller never has to know which it was.

No URL and no timeout is written here: both come from config/<cc>/sources.json.
"""

import base64
import html as html_module
import logging
import re
import ssl

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib.parse import quote, unquote, urljoin

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


class _UncheckedAdapter(HTTPAdapter):
    """Certificates are not checked, for any source.

    The owner's decision: what is read is a public tariff page, and the figures on it matter,
    not whether the site keeps its certificate in order. Utility sites fail in every way there
    is — expired certificates, keys too weak for OpenSSL 3, missing intermediates, names that do
    not match — and each one used to cost a country its data or a certificate file in the
    repository that went stale in weeks. So the chain is not verified, the hostname is not
    checked, and the cipher security level is lowered, which is what Dushanbe's water utility
    needs.
    """

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers("DEFAULT@SECLEVEL=0")
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


# urllib3 would otherwise print a warning for every page of every run.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_SESSION = requests.Session()
_SESSION.mount("https://", _UncheckedAdapter())
_SESSION.verify = False
_SESSION.headers["User-Agent"] = USER_AGENT

# A tariff as a Russian-language page prints it: "3 800,68". Counting them is a cheap sign of
# whether a page carries tariffs at all or is a menu, an article, or a disguised 404.
PRICE = re.compile(r"\d,\d{2}\b")


class Document:
    """One fetched source: text to read, or bytes to hand over as-is."""

    def __init__(self, url: str, text: str = "", data: bytes = None, mime: str = "",
                 markup: str = ""):
        self.url = url
        self.text = text
        self.data = data
        self.mime = mime
        # The markup is kept only so the images of a page can be found afterwards; nothing
        # sends it to a model, which is what the flattened text is for.
        self.markup = markup

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

    markup = _decode(response.content, content_type)
    text = html_to_text(markup)
    if len(text) > MAX_TEXT_CHARS:
        logger.warning(f"{url}: text cut from {len(text)} to {MAX_TEXT_CHARS} chars")
        text = text[:MAX_TEXT_CHARS]
    logger.info(f"Fetched {url}: {len(text)} chars of text")
    return Document(url, text=text, markup=markup)


# A page that publishes its tariff as a scan carries the document among its decoration. The
# decoration is small — logos, banners, a magazine cover — and a scanned decree page is not, so
# size is what separates them. Tajikistan's ministry publishes one 2560x1804 image per decision.
MIN_IMAGE_SIDE = 800
MAX_PAGE_IMAGES = 4
# An image embedded in the page as a data: URI carries no width or height to judge it by, so
# its decoded size is used instead. Icons embedded that way are a few hundred bytes; the
# tariff table Bishkek's heat utility pastes into its page is about 40 kB.
MIN_INLINE_IMAGE_BYTES = 20_000

IMG_TAG = re.compile(r"<img[^>]+>", re.I)
IMG_ATTR = re.compile(r"""(src|width|height)\s*=\s*["']([^"']+)["']""", re.I)
INLINE_IMAGE = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,(.+)$", re.S)

# A regulator that lists its decisions on one page and attaches each one: the page stays at the
# same address while the address of every decision changes.
LINK_ANCHOR = re.compile(r"""<a\s[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)
MAX_PAGE_DOCUMENTS = 6


def _large_images(markup: str, page_url: str) -> list:
    """The images on a page that are big enough to be documents: URLs to download, or
    Documents already decoded from an inline data: URI."""
    found = []
    for tag in IMG_TAG.findall(markup):
        attrs = {name.lower(): value for name, value in IMG_ATTR.findall(tag)}
        src = attrs.get("src", "").strip()
        inline = INLINE_IMAGE.match(src)
        if inline:
            image = _inline_image(page_url, inline.group(1), inline.group(2))
            if image:
                found.append(image)
            continue
        width, height = as_pixels(attrs.get("width")), as_pixels(attrs.get("height"))
        if max(width, height) < MIN_IMAGE_SIDE:
            continue
        url = urljoin(page_url, src)
        if url.startswith(("http://", "https://")) and url not in found:
            found.append(url)
    return found[:MAX_PAGE_IMAGES]


def _inline_image(page_url: str, mime: str, payload: str):
    """A data: URI image as a Document, or None when it is too small to be a document."""
    try:
        data = base64.b64decode(payload, validate=False)
    except ValueError:
        return None
    if len(data) < MIN_INLINE_IMAGE_BYTES:
        return None
    logger.info(f"Found an inline {mime} image on {page_url}: {len(data)} bytes")
    return Document(page_url, data=data, mime=mime)


def _linked_documents(markup: str, page_url: str, match) -> list:
    """Absolute URLs of the documents a page links to, in page order, capped.

    `match` is True for every PDF on the page, or a piece of text the link's address or caption
    must contain — and then the link may lead to a page as well as to a PDF, because Bishkek's
    city council publishes each resolution as a page of its own in a list of all of them. A
    filter is what keeps the application forms, the 2009 decrees and the menu out, since every
    document sent is paid for. The ones kept all go to the model, which picks the decision in
    force by its date: which end of a list is the newest differs from site to site. A page
    linking more than the cap is logged rather than cut silently, since the newest decision may
    be the one left out.
    """
    wanted = match.lower() if isinstance(match, str) else ""
    found = []
    for href, caption in LINK_ANCHOR.findall(markup):
        href = html_module.unescape(href.strip())
        address = unquote(href)
        if wanted:
            if wanted not in (address + " " + html_to_text(caption)).lower():
                continue
        elif not address.lower().endswith(".pdf"):
            continue
        url = urljoin(page_url, quote(href, safe="/:%?=&"))
        if url.startswith(("http://", "https://")) and url != page_url and url not in found:
            found.append(url)
    if len(found) > MAX_PAGE_DOCUMENTS:
        logger.warning(f"{page_url}: links {len(found)} matching documents, only the first "
                       f"{MAX_PAGE_DOCUMENTS} are read")
    return found[:MAX_PAGE_DOCUMENTS]


def as_pixels(value) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


def fetch_all(urls: list, timeout: int, read_images: bool = False,
              read_documents=False) -> list:
    """Fetches several documents for one city, dropping the ones that failed.

    With `read_images`, the large images of every page fetched are handed to the model
    alongside it. Some regulators publish a decision as a photograph of its pages —
    Tajikistan's ministry of energy does — and the page itself then carries no text to read.
    With `read_documents` (True for every PDF, or text a link must contain), the documents a
    page links to are fetched as well: Kyrgyzstan's energy regulator and Belarus's energy
    association attach their decisions as PDFs, Bishkek's city council gives each resolution a
    page of its own. Either way config keeps the stable page instead of the file name of this year's
    decision, which is what makes next year's decision arrive on its own.
    """
    documents = []
    for url in urls:
        document = fetch(url, timeout)
        if not document:
            continue
        documents.append(document)
        if not document.text:
            continue
        if read_images:
            for image in _large_images(document.markup, url):
                if isinstance(image, str):
                    image = fetch(image, timeout)
                if image and image.is_binary:
                    documents.append(image)
        if read_documents:
            for link in _linked_documents(document.markup, url, read_documents):
                attachment = fetch(link, timeout)
                if attachment:
                    documents.append(attachment)
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
