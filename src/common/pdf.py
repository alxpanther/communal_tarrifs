"""Turning a PDF into something a text-only or a vision model can read.

Gemini takes a PDF as bytes and reads it itself, scans included. OpenAI-compatible APIs take
text and images only, so for them a PDF is flattened here: its text layer when it has one,
rendered page images when it is a scan with nothing to extract.
"""

import logging

import pymupdf

from common.fetching import MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

# A page of a tariff table carries hundreds of characters. Less than this across the whole
# document means there is no usable text layer: a scan, perhaps with a stray header in it.
MIN_TEXT_CHARS = 200

# Decrees put the tariff tables in their first pages. Rendering a long annex page by page
# would multiply the cost of one call for nothing.
MAX_PAGES = 8

# Enough for a vision model to read small table digits without making each page huge.
DPI = 150

def _covering_text(table, texts: list, row: int, col: int) -> str:
    """Text of the merged cell that covers (row, col).

    Looks up first: a cell merged down is the nearest real cell above whose bottom edge
    reaches below this row's top. Otherwise the merge runs across, and the cell is the
    nearest real one to the left. Real cells are always above or to the left of the ones
    they cover, so their text is already final when this is called.
    """
    top = table.rows[row].bbox[1]
    for above in range(row - 1, -1, -1):
        cell = table.rows[above].cells[col]
        if cell is None:
            continue
        if cell[3] > top + 1:
            return texts[above][col]
        break
    for left in range(col - 1, -1, -1):
        if table.rows[row].cells[left] is not None:
            return texts[row][left]
    return ""


def _table_text(table) -> str:
    """A table row by row, cells separated by a pipe.

    A merged cell is stored once: PyMuPDF puts its text in the cell that holds it and None in
    every cell it covers. Left that way, the row under a decree reference merged over two
    rows has no decree — which is how the Moscow heat tariff came back with an empty
    `decree_info` — and a column under a header merged across two has no header, which is
    how it once came back without VAT. Every covered cell therefore gets the text of the cell
    covering it. An empty string is a genuinely empty cell and stays empty.
    """
    raw = table.extract()
    texts = [[(cell or "").replace("\n", " ").strip() for cell in row] for row in raw]
    for r, row in enumerate(raw):
        for c, cell in enumerate(row):
            if cell is None and c < len(table.rows[r].cells):
                texts[r][c] = _covering_text(table, texts, r, c)
    return "\n".join(" | ".join(row) for row in texts)


def _page_text(page) -> str:
    """A page as text, with its tables kept as rows and columns.

    Plain text extraction reads a table column by column into a flat list of numbers, and a
    list of numbers says nothing about which of them is the tariff with VAT. Tables are
    therefore written out row by row, cells separated by a pipe — the same shape web pages
    get in common/fetching.py — and only the text outside them is taken as it is.
    """
    tables = page.find_tables().tables
    if not tables:
        return page.get_text()
    areas = [pymupdf.Rect(table.bbox) for table in tables]
    outside = [block[4] for block in page.get_text("blocks")
               if not any(pymupdf.Rect(block[:4]).intersects(area) for area in areas)]
    parts = ["".join(outside).strip()] + [_table_text(table) for table in tables]
    return "\n\n".join(part for part in parts if part)


def text_of(data: bytes) -> str:
    """The text layer of the PDF, tables kept as rows and columns, cut to the same limit
    as a fetched web page."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            text = "\n\n".join(_page_text(page) for page in document)
    except Exception as e:
        logger.warning(f"Could not read the PDF text layer: {e}")
        return ""
    if len(text) > MAX_TEXT_CHARS:
        logger.warning(f"PDF text cut from {len(text)} to {MAX_TEXT_CHARS} chars")
        text = text[:MAX_TEXT_CHARS]
    return text


def is_scan(text: str) -> bool:
    return len((text or "").strip()) < MIN_TEXT_CHARS


def page_images(data: bytes) -> list:
    """PNG bytes of the first pages, for a document with no text layer."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.page_count > MAX_PAGES:
                logger.warning(f"PDF has {document.page_count} pages, rendering the first {MAX_PAGES}")
            return [document[i].get_pixmap(dpi=DPI).tobytes("png")
                    for i in range(min(document.page_count, MAX_PAGES))]
    except Exception as e:
        logger.warning(f"Could not render the PDF pages: {e}")
        return []
