"""M49 — `pdf_read` builtin tool: tier-1 pypdf + tier-2 OCR fallback."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from veles.core.tools.builtin.pdf import (
    _DEFAULT_MAX_PAGES,
    _OUTPUT_CHAR_CAP,
    _truncate,
    pdf_read,
)

# ---------- harness ----------


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", str(tmp_path))
    return tmp_path


def _make_text_pdf(text: str) -> bytes:
    """Build a minimal one-page PDF containing `text` (ASCII).

    Hand-crafted bytes — avoids pulling in `reportlab` as a test dep.
    pypdf can parse this; suitable for the one integration test that
    exercises the real tier-1 path.
    """
    safe = text.replace("(", r"\(").replace(")", r"\)").encode("ascii", "replace")
    stream = b"BT /F1 24 Tf 100 700 Td (" + safe + b") Tj ET"
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        (
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
            b"/Contents 4 0 R/Resources<</Font<</F1<</Type/Font"
            b"/Subtype/Type1/BaseFont/Helvetica>>>>>>"
        ),
        b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream",
    ]
    parts: list[bytes] = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(sum(len(p) for p in parts))
        parts.append(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = sum(len(p) for p in parts)
    xref = [f"xref\n0 {len(objs) + 1}\n".encode(), b"0000000000 65535 f \n"]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n".encode())
    parts.extend(xref)
    parts.append(b"trailer\n")
    parts.append(f"<</Size {len(objs) + 1}/Root 1 0 R>>\n".encode())
    parts.append(f"startxref\n{xref_offset}\n%%EOF\n".encode())
    return b"".join(parts)


def _stub_pypdf_with_pages(monkeypatch: pytest.MonkeyPatch, page_texts: list[str]) -> None:
    """Replace pypdf.PdfReader with a fake that returns canned page texts."""
    fake_reader = MagicMock()
    fake_reader.pages = []
    for t in page_texts:
        page = MagicMock()
        page.extract_text.return_value = t
        fake_reader.pages.append(page)
    fake_pypdf = MagicMock()
    fake_pypdf.PdfReader.return_value = fake_reader
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)


# ---------- error / sandbox paths ----------


def test_pdf_read_rejects_path_outside_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", str(sandbox))
    target = outside / "secret.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(target))
    assert "<error" in out
    assert "outside sandbox" in out or "SandboxViolation" in out


def test_pdf_read_handles_missing_file(_sandbox: Path) -> None:
    out = pdf_read(str(_sandbox / "ghost.pdf"))
    assert "<error" in out
    assert "not found" in out


def test_pdf_read_rejects_zero_max_pages(_sandbox: Path) -> None:
    f = _sandbox / "x.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f), max_pages=0)
    assert "<error" in out
    assert "max_pages" in out


# ---------- tier 1: pypdf ----------


def test_pdf_read_returns_embedded_text(_sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real tier-1 integration with hand-crafted PDF + real pypdf."""
    pdf = _sandbox / "sample.pdf"
    pdf.write_bytes(_make_text_pdf("Hello veles"))
    out = pdf_read(str(pdf))
    assert "Hello veles" in out
    assert "page 1" in out


def test_pdf_read_caps_at_max_pages(_sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocked pypdf returns 5 pages; max_pages=2 → only 2 in output."""
    _stub_pypdf_with_pages(monkeypatch, ["p1", "p2", "p3", "p4", "p5"])
    f = _sandbox / "multi.pdf"
    f.write_bytes(b"%PDF-1.4\n")  # any non-empty bytes; pypdf is mocked
    out = pdf_read(str(f), max_pages=2)
    assert "page 1" in out
    assert "page 2" in out
    assert "page 3" not in out


def test_pdf_read_skips_empty_pages(_sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_pypdf_with_pages(monkeypatch, ["alpha", "", "  \n  ", "delta"])
    f = _sandbox / "p.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f))
    assert "alpha" in out
    assert "delta" in out
    # The empty/whitespace pages don't generate page headers.
    assert out.count("--- page") == 2


def test_pdf_read_returns_install_hint_when_pypdf_missing(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force ImportError on `import pypdf` and verify the user-facing message."""
    f = _sandbox / "x.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    import builtins

    real_import = builtins.__import__

    def deny(name, *a, **kw):
        if name == "pypdf":
            raise ImportError("not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", deny)
    out = pdf_read(str(f))
    assert "<error" in out
    assert "pypdf" in out
    assert "install" in out.lower()


def test_pdf_read_handles_pypdf_open_failure(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_pypdf = MagicMock()
    fake_pypdf.PdfReader.side_effect = ValueError("not a PDF")
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    f = _sandbox / "broken.pdf"
    f.write_bytes(b"not a pdf")
    out = pdf_read(str(f))
    assert "<error" in out
    assert "ValueError" in out


# ---------- tier 2: OCR fallback ----------


def test_ocr_fallback_when_pypdf_yields_empty(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_pypdf_with_pages(monkeypatch, ["", "  ", ""])
    fake_pdf2image = MagicMock()
    fake_pdf2image.convert_from_path.return_value = ["img1", "img2"]
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.side_effect = ["scanned A", "scanned B"]
    monkeypatch.setitem(sys.modules, "pdf2image", fake_pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    f = _sandbox / "scan.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f))
    assert "scanned A" in out
    assert "scanned B" in out
    assert "(OCR)" in out


def test_ocr_fallback_install_hint_when_deps_missing(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tier-1 returns empty, tier-2 deps missing → user-facing install hint."""
    _stub_pypdf_with_pages(monkeypatch, [""])
    import builtins

    real_import = builtins.__import__

    def deny(name, *a, **kw):
        if name in {"pdf2image", "pytesseract"}:
            raise ImportError("not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", deny)
    f = _sandbox / "scan.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f))
    assert "OCR" in out
    assert "tesseract" in out.lower()


def test_ocr_handles_missing_tesseract_binary(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_pypdf_with_pages(monkeypatch, [""])
    fake_pdf2image = MagicMock()
    fake_pdf2image.convert_from_path.return_value = ["img1"]
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.side_effect = FileNotFoundError("tesseract")
    monkeypatch.setitem(sys.modules, "pdf2image", fake_pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    f = _sandbox / "scan.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f))
    assert "tesseract" in out.lower()
    assert "PATH" in out or "install" in out.lower()


def test_ocr_returns_empty_when_both_tiers_yield_nothing(
    _sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_pypdf_with_pages(monkeypatch, [""])
    fake_pdf2image = MagicMock()
    fake_pdf2image.convert_from_path.return_value = ["img1"]
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "   "
    monkeypatch.setitem(sys.modules, "pdf2image", fake_pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    f = _sandbox / "blank.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    out = pdf_read(str(f))
    assert "no extractable text" in out


# ---------- _truncate ----------


def test_truncate_passes_through_short_text() -> None:
    short = "x" * 1000
    assert _truncate(short) == short


def test_truncate_trims_oversized_output() -> None:
    big = "x" * (_OUTPUT_CHAR_CAP * 2)
    out = _truncate(big)
    assert len(out) <= _OUTPUT_CHAR_CAP
    assert "truncated" in out


# ---------- registry wiring ----------


def test_pdf_read_registered_as_builtin_tool() -> None:
    """The tool is auto-registered via the @tool decorator on import."""
    from veles.core.tools.registry import registry

    names = registry.list_names()
    assert "pdf_read" in names


def test_default_max_pages_constant_sane() -> None:
    assert _DEFAULT_MAX_PAGES > 0
    assert _DEFAULT_MAX_PAGES < 1000  # sanity
