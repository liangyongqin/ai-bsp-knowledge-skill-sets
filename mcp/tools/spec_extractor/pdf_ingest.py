"""
PDF Ingestion Pipeline — extract structured text blocks from BSP specification PDFs.

Provides pdfplumber-based primary extraction with fallback to unstructured
for complex/scanned PDFs.  Each extracted block carries page, section,
text content, and source_file metadata.

Usage::

    from mcp.tools.spec_extractor.pdf_ingest import ingest_pdf
    blocks = ingest_pdf("/path/to/soc_trm.pdf", soc="mt6989")
"""

import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"^(?P<num>(?:\d+\.)+\d*)\s+(?P<title>.+)$"
)


def _detect_section(text: str) -> str:
    """Heuristically detect a section heading from a text string."""
    line = text.strip().splitlines()[0] if text.strip() else ""
    m = _SECTION_RE.match(line)
    if m:
        return f"{m.group('num')} {m.group('title')}"
    return ""


def _clean_text(raw: str) -> str:
    """Normalise whitespace and remove control characters."""
    if not raw:
        return ""
    # Remove form-feed and other control chars except newline/tab
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", raw)
    # Collapse excessive whitespace
    raw = re.sub(r" {3,}", "  ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Primary extractor: pdfplumber
# ---------------------------------------------------------------------------

def _extract_with_pdfplumber(path: str, soc: str) -> list[dict]:
    """Extract text blocks using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required: pip install pdfplumber")

    blocks: list[dict] = []
    source_file = os.path.basename(path)
    current_section = ""

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            except Exception as exc:
                logger.warning("pdfplumber page %d extraction error: %s", page_num, exc)
                text = ""

            text = _clean_text(text)
            if not text:
                continue

            # Detect section heading from the first non-empty line
            heading = _detect_section(text)
            if heading:
                current_section = heading

            # Split into paragraph-level blocks
            paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
            for para in paragraphs:
                blocks.append({
                    "page": page_num,
                    "section": current_section,
                    "text": para,
                    "source_file": source_file,
                    "soc": soc,
                    "extractor": "pdfplumber",
                })

            # Also extract any tables as structured text
            try:
                tables = page.extract_tables()
                for tbl_idx, table in enumerate(tables or []):
                    if not table:
                        continue
                    rows_text = "\n".join(
                        " | ".join(str(cell) if cell else "" for cell in row)
                        for row in table
                        if any(cell for cell in row)
                    )
                    if rows_text.strip():
                        blocks.append({
                            "page": page_num,
                            "section": current_section,
                            "text": rows_text,
                            "source_file": source_file,
                            "soc": soc,
                            "extractor": "pdfplumber_table",
                            "table_index": tbl_idx,
                        })
            except Exception as exc:
                logger.debug("Table extraction error page %d: %s", page_num, exc)

    return blocks


# ---------------------------------------------------------------------------
# Fallback extractor: unstructured
# ---------------------------------------------------------------------------

def _extract_with_unstructured(path: str, soc: str) -> list[dict]:
    """Fallback extraction using the unstructured library."""
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        raise ImportError("unstructured[pdf] is required: pip install 'unstructured[pdf]'")

    source_file = os.path.basename(path)
    blocks: list[dict] = []
    current_section = ""

    try:
        elements = partition_pdf(filename=path, strategy="fast")
    except Exception as exc:
        logger.error("unstructured partition_pdf failed: %s", exc)
        return []

    for elem in elements:
        elem_type = type(elem).__name__
        text = _clean_text(str(elem))
        if not text:
            continue

        # Attempt to extract page number from metadata
        page_num = 0
        try:
            page_num = elem.metadata.page_number or 0
        except AttributeError:
            pass

        if elem_type in ("Title", "Header"):
            current_section = text[:120]

        blocks.append({
            "page": page_num,
            "section": current_section,
            "text": text,
            "source_file": source_file,
            "soc": soc,
            "extractor": "unstructured",
            "element_type": elem_type,
        })

    return blocks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_pdf(path: str, soc: str) -> list[dict[str, Any]]:
    """Extract clean text blocks from a BSP specification PDF.

    Attempts extraction with pdfplumber first.  Falls back to unstructured
    if pdfplumber returns no content (e.g., scanned/image-only PDFs).

    Parameters
    ----------
    path:
        Absolute or relative filesystem path to the PDF file.
    soc:
        SoC identifier string (e.g. ``"mt6989"``).  Attached to every block
        for downstream filtering.

    Returns
    -------
    list[dict]
        Each dict has keys: ``page``, ``section``, ``text``,
        ``source_file``, ``soc``, ``extractor``.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If *path* is not a ``.pdf`` file.
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.lower().endswith(".pdf"):
        raise ValueError(f"Expected a .pdf file, got: {path}")

    logger.info("Ingesting PDF: %s (soc=%s)", path, soc)

    blocks: list[dict] = []

    # Try pdfplumber first
    try:
        blocks = _extract_with_pdfplumber(path, soc)
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s — falling back to unstructured", exc)

    if not blocks:
        logger.info("pdfplumber yielded no blocks, trying unstructured …")
        try:
            blocks = _extract_with_unstructured(path, soc)
        except Exception as exc:
            logger.error("unstructured extraction also failed: %s", exc)

    logger.info("Extracted %d text blocks from %s", len(blocks), os.path.basename(path))
    return blocks
