"""PDF text extraction (M49) — two-tier strategy: embedded text → OCR.

Open-source-first by design. Vision-LLM round-trips on PDFs are slow,
expensive, and leak data; native text extraction is instant and free
for the 80% case (text-native PDFs from Word/LaTeX/HTML-to-PDF
pipelines). Fallback to Tesseract OCR for scanned PDFs covers most of
the remaining 20%; the residual (handwriting, complex diagrams) is
where M50 vision tools come in.

Tier 1 — embedded text via `pypdf` (hard dependency, pure-Python). For
each page we call `extract_text()` and concatenate non-empty results.
Pages with empty text in tier 1 don't trigger a per-page fallback —
either the whole document is text-native or we go to tier 2.

Tier 2 — OCR via `pdf2image` + `pytesseract` (soft dependencies,
declared in `pyproject.toml::[project.optional-dependencies] pdf-ocr`;
require system Tesseract binary). Triggered only when tier 1 yields
zero non-whitespace output. If the soft deps are missing we return a
clear hint about the install command rather than crashing.

Path is sandboxed via M37 `resolve_safe` — same envelope as `read_file`.
The tool isn't marked `sensitive=True`: it's a pure file read with no
write side-effects, similar to `read_file`. M38 trust ladder doesn't
gate it.
"""

from __future__ import annotations

import sys

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_DEFAULT_MAX_PAGES = 50
_OUTPUT_CHAR_CAP = 200_000


@tool(risk_class=RiskClass.READ_ONLY)
def pdf_read(path: str, max_pages: int = _DEFAULT_MAX_PAGES) -> str:
    """Extract text from a PDF.

    Tries embedded-text extraction first (pure-Python, fast, free) and
    falls back to OCR for scanned PDFs. Returns markdown-formatted
    pages separated by `--- page N ---` headers. Path is sandbox-checked
    (must resolve under active project or `~/.veles/`). At most
    `max_pages` pages are processed; output is capped at ~200K chars.
    """
    try:
        p = resolve_safe(path)
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>"
    if not p.is_file():
        return f"<error: {p} not found>"
    if max_pages <= 0:
        return "<error: max_pages must be >= 1>"

    embedded = _try_embedded_text(p, max_pages)
    if embedded is None:
        return (
            "<error: pypdf is required for pdf_read. "
            "Install: `uv add pypdf` (or `pip install pypdf`)>"
        )
    if embedded.strip():
        return _truncate(embedded)

    # Tier 1 yielded nothing — likely a scanned PDF.
    ocr_result = _try_ocr(p, max_pages)
    if ocr_result is None:
        return (
            "<warning: PDF appears to have no embedded text. OCR fallback "
            "needs `pytesseract` + `pdf2image` (Python) and the system "
            "`tesseract` binary. Install: "
            "`uv pip install pytesseract pdf2image` and "
            "`brew install tesseract` (macOS) / "
            "`apt install tesseract-ocr` (Linux)>"
        )
    if not ocr_result.strip():
        return "<error: PDF has no extractable text (text-empty + OCR-empty)>"
    return _truncate(ocr_result)


def _try_embedded_text(path, max_pages: int) -> str | None:
    """Tier 1: pypdf text extraction. Returns None if pypdf is unavailable."""
    try:
        import pypdf
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        return f"<error: failed to open PDF: {type(exc).__name__}: {exc}>"
    n = min(len(reader.pages), max_pages)
    parts: list[str] = []
    for i in range(n):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception as exc:
            text = f"<extract failed: {type(exc).__name__}: {exc}>"
        text = text.strip()
        if text:
            parts.append(f"--- page {i + 1} ---\n{text}")
    return "\n\n".join(parts)


def _try_ocr(path, max_pages: int) -> str | None:
    """Tier 2: pdf2image + pytesseract. Returns None if soft deps missing."""
    try:
        import pdf2image
        import pytesseract
    except ImportError:
        return None
    try:
        images = pdf2image.convert_from_path(str(path), last_page=max_pages)
    except Exception as exc:
        return f"<error: pdf2image failed: {type(exc).__name__}: {exc}>"
    parts: list[str] = []
    for i, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img) or ""
        except FileNotFoundError:
            return (
                "<error: tesseract binary not found in PATH. Install: "
                "`brew install tesseract` (macOS) / "
                "`apt install tesseract-ocr` (Linux)>"
            )
        except Exception as exc:
            text = f"<OCR failed on page {i + 1}: {type(exc).__name__}: {exc}>"
        text = text.strip()
        if text:
            parts.append(f"--- page {i + 1} (OCR) ---\n{text}")
    return "\n\n".join(parts)


def _truncate(text: str) -> str:
    if len(text) <= _OUTPUT_CHAR_CAP:
        return text
    suffix = f"\n\n<truncated at {_OUTPUT_CHAR_CAP} chars; pass smaller max_pages for full output>"
    return text[: _OUTPUT_CHAR_CAP - len(suffix)] + suffix


def _have_pypdf() -> bool:
    """For tests: is pypdf actually importable?"""
    return "pypdf" in sys.modules or _check_module("pypdf")


def _check_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False
