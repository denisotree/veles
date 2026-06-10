"""M50 — image_ocr (Tesseract) + image_describe (vision LLM)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from veles.core.context import (
    reset_active_project,
    set_active_project,
)
from veles.core.project import init_project
from veles.core.tools.builtin.image import (
    _DEFAULT_DESCRIBE_PROMPT,
    _VISION_OUTPUT_CAP,
    _detect_mime,
    _truncate,
    image_describe,
    image_ocr,
)

# ---------- harness ----------


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return tmp_path


def _make_image_file(
    _sandbox: Path, name: str = "img.png", body: bytes = b"\x89PNG\r\n\x1a\n"
) -> Path:
    p = _sandbox / name
    p.write_bytes(body)
    return p


def _stub_pytesseract(monkeypatch: pytest.MonkeyPatch, text: str = "extracted ocr text") -> None:
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = text
    fake_pil_image = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    fake_pil_image.open.return_value = cm
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", MagicMock(Image=fake_pil_image))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)


# ---------- image_ocr ----------


def test_image_ocr_returns_extracted_text(_sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_image_file(_sandbox)
    _stub_pytesseract(monkeypatch, "Hello World")
    out = image_ocr(str(p))
    assert out == "Hello World"


def test_image_ocr_strips_whitespace(_sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_image_file(_sandbox)
    _stub_pytesseract(monkeypatch, "   \n  foo  \n  ")
    assert image_ocr(str(p)) == "foo"


def test_image_ocr_warns_on_empty_result(_sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_image_file(_sandbox)
    _stub_pytesseract(monkeypatch, "   ")
    out = image_ocr(str(p))
    assert "warning" in out.lower()
    assert "empty" in out.lower()


def test_image_ocr_passes_lang_to_tesseract(_sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_image_file(_sandbox)
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.return_value = "rus text"
    fake_pil = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    fake_pil.open.return_value = cm
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", MagicMock(Image=fake_pil))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil)
    image_ocr(str(p), lang="rus+eng")
    fake_pytesseract.image_to_string.assert_called_once()
    _, kwargs = fake_pytesseract.image_to_string.call_args
    assert kwargs.get("lang") == "rus+eng"


def test_image_ocr_install_hint_when_deps_missing(
    _sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _make_image_file(_sandbox)
    import builtins

    real_import = builtins.__import__

    def deny(name, *a, **kw):
        if name in {"pytesseract", "PIL"}:
            raise ImportError("not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", deny)
    out = image_ocr(str(p))
    assert "<error" in out
    assert "pytesseract" in out
    assert "tesseract" in out.lower()


def test_image_ocr_handles_missing_tesseract_binary(
    _sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _make_image_file(_sandbox)
    fake_pytesseract = MagicMock()
    fake_pytesseract.image_to_string.side_effect = FileNotFoundError("tesseract")
    fake_pil = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    fake_pil.open.return_value = cm
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", MagicMock(Image=fake_pil))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil)
    out = image_ocr(str(p))
    assert "tesseract" in out.lower()
    assert "PATH" in out or "install" in out.lower()


def test_image_ocr_handles_missing_file(_sandbox) -> None:
    out = image_ocr(str(_sandbox / "nope.png"))
    assert "<error" in out
    assert "not found" in out


def test_image_ocr_rejects_path_outside_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "sb"
    outside = tmp_path / "elsewhere"
    sandbox.mkdir()
    outside.mkdir()
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", str(sandbox))
    target = outside / "x.png"
    target.write_bytes(b"\x89PNG")
    out = image_ocr(str(target))
    assert "<error" in out


# ---------- image_describe routing / errors ----------


@pytest.fixture
def _project(_sandbox: Path):
    project = init_project(_sandbox / "proj", name="proj")
    token = set_active_project(project)
    yield project
    reset_active_project(token)


def test_describe_requires_active_project(_sandbox) -> None:
    p = _make_image_file(_sandbox)
    out = image_describe(str(p))
    assert "<error" in out
    assert "active project" in out


def test_describe_requires_api_key(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _make_image_file(_project.root.parent)
    out = image_describe(str(p))
    assert "<error" in out
    assert "API key" in out


def test_describe_handles_missing_file(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    out = image_describe(str(_project.root / "ghost.png"))
    assert "<error" in out
    assert "not found" in out


# ---------- per-provider wire format ----------


def test_describe_anthropic_wire_format(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    """Routing → anthropic; tool builds the right Messages-API content."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub")
    from veles.core.routing import set_project_route

    set_project_route(_project, "vision", "anthropic:claude-sonnet-4.6")
    p = _make_image_file(_project.root, "x.png", body=b"PNGBYTES")

    fake_client = MagicMock()
    block = MagicMock(type="text", text="anthropic-described")
    fake_response = MagicMock(content=[block])
    fake_client.messages.create.return_value = fake_response
    fake_anthropic_mod = MagicMock()
    fake_anthropic_mod.Anthropic.return_value = fake_client
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic_mod)

    out = image_describe(str(p), prompt="say hi")
    assert out == "anthropic-described"
    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["model"] == "claude-sonnet-4.6"
    msg = kwargs["messages"][0]
    assert msg["role"] == "user"
    blocks = msg["content"]
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[0]["source"]["type"] == "base64"
    assert blocks[1] == {"type": "text", "text": "say hi"}


def test_describe_openai_wire_format(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "stub")
    from veles.core.routing import set_project_route

    set_project_route(_project, "vision", "openai:gpt-4o-mini")
    p = _make_image_file(_project.root, "x.png", body=b"PNGBYTES")

    fake_client = MagicMock()
    fake_choice = MagicMock(message=MagicMock(content="openai-described"))
    fake_response = MagicMock(choices=[fake_choice])
    fake_client.chat.completions.create.return_value = fake_response
    fake_openai_mod = MagicMock()
    fake_openai_mod.OpenAI.return_value = fake_client
    monkeypatch.setitem(sys.modules, "openai", fake_openai_mod)

    out = image_describe(str(p))
    assert out == "openai-described"
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    blocks = kwargs["messages"][0]["content"]
    assert blocks[0]["type"] == "text"
    assert blocks[1]["type"] == "image_url"
    assert blocks[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_describe_openrouter_uses_openai_with_base_url(
    _project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    p = _make_image_file(_project.root, "x.png")

    fake_client = MagicMock()
    fake_choice = MagicMock(message=MagicMock(content="via openrouter"))
    fake_client.chat.completions.create.return_value = MagicMock(choices=[fake_choice])
    fake_openai_mod = MagicMock()
    fake_openai_mod.OpenAI.return_value = fake_client
    monkeypatch.setitem(sys.modules, "openai", fake_openai_mod)

    out = image_describe(str(p))
    assert out == "via openrouter"
    _args, kwargs = fake_openai_mod.OpenAI.call_args
    assert "openrouter.ai" in (kwargs.get("base_url") or "")


def test_describe_gemini_wire_format(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "stub")
    from veles.core.routing import set_project_route

    set_project_route(_project, "vision", "gemini:gemini-2.0-flash")
    p = _make_image_file(_project.root, "x.png", body=b"PNGBYTES")

    fake_client = MagicMock()
    fake_response = MagicMock(text="gemini-described")
    fake_client.models.generate_content.return_value = fake_response
    fake_genai = MagicMock()
    fake_genai.Client.return_value = fake_client
    fake_google = MagicMock(genai=fake_genai)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    out = image_describe(str(p))
    assert out == "gemini-described"
    _, kwargs = fake_client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.0-flash"
    parts = kwargs["contents"][0]["parts"]
    assert "inline_data" in parts[0]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["text"] == _DEFAULT_DESCRIBE_PROMPT


def test_describe_unsupported_provider(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    """cli-delegate providers can't run vision queries."""
    from veles.core.routing import set_project_route

    set_project_route(_project, "vision", "claude-cli:nope")
    monkeypatch.setattr(
        "veles.core.provider_factory.has_api_key",
        lambda name: True,  # bypass the api-key gate so we hit the dispatch arm
    )
    p = _make_image_file(_project.root, "x.png")
    out = image_describe(str(p))
    assert "<error" in out
    assert "vision" in out.lower() or "can't run" in out.lower()


def test_describe_handles_sdk_exception(_project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub")
    from veles.core.routing import set_project_route

    set_project_route(_project, "vision", "anthropic:claude-sonnet-4.6")
    p = _make_image_file(_project.root, "x.png")

    fake_anthropic_mod = MagicMock()
    fake_anthropic_mod.Anthropic.side_effect = RuntimeError("network")
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic_mod)

    out = image_describe(str(p))
    assert "<error" in out
    assert "RuntimeError" in out
    assert "network" in out


# ---------- helpers ----------


def test_detect_mime_by_extension() -> None:
    assert _detect_mime(Path("x.png")) == "image/png"
    assert _detect_mime(Path("x.JPG")) == "image/jpeg"
    assert _detect_mime(Path("x.gif")) == "image/gif"
    assert _detect_mime(Path("x.webp")) == "image/webp"
    # Unknown extension falls back to PNG.
    assert _detect_mime(Path("x.unknown")) == "image/png"


def test_truncate_passes_short_text() -> None:
    short = "x" * 1000
    assert _truncate(short) == short


def test_truncate_caps_long_text() -> None:
    big = "x" * (_VISION_OUTPUT_CAP * 2)
    out = _truncate(big)
    assert len(out) <= _VISION_OUTPUT_CAP
    assert "truncated" in out


# ---------- registry wiring ----------


def test_image_tools_registered() -> None:
    from veles.core.tools.registry import registry

    names = registry.list_names()
    assert "image_ocr" in names
    assert "image_describe" in names


def test_vision_in_default_routing() -> None:
    from veles.core.routing import DEFAULT_TASKS

    assert "vision" in DEFAULT_TASKS
