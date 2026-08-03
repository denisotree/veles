"""M226 — the provider-backed vision adapter.

Default is zero-config: describe the image with whatever model the
project routes `vision` to (which, with no explicit route, is the
`[engine]` model). `[vision]` in config.toml covers the rest — pin a
different model when the engine is text-only, add an OCR stage for
scans, or turn the whole thing off.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.core.project_config import load_project_config, save_project_config
from veles.core.vision import backends
from veles.core.vision.adapter import (
    RoutedVisionAdapter,
    VisionSettings,
    build_vision_adapter,
    install_vision_adapter,
    load_vision_settings,
)
from veles.modules.vision import VisionError, get_vision_adapter, reset_vision_adapter

_JPEG = b"\xff\xd8\xffbody"


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="vtest")


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_vision_adapter()
    yield
    reset_vision_adapter()


def _set_vision_cfg(project: Project, **values) -> None:
    cfg = load_project_config(project)
    cfg.setdefault("vision", {}).update(values)
    save_project_config(project, cfg)


def _stub_describe(monkeypatch: pytest.MonkeyPatch, calls: list) -> None:
    def fake(provider_name, model, image_bytes, mime, prompt):
        calls.append((provider_name, model, image_bytes, mime, prompt))
        return "a chart with two bars"

    monkeypatch.setattr(backends, "describe", fake)
    monkeypatch.setattr("veles.core.vision.adapter.describe", fake)


# ---- settings ----


def test_defaults_to_the_model_pass(project: Project) -> None:
    s = load_vision_settings(project)
    assert s.mode == "model"
    assert s.spec is None
    assert s.uses_model and not s.uses_ocr


def test_settings_read_from_config(project: Project) -> None:
    _set_vision_cfg(project, mode="ocr+model", model="openrouter:some/vlm", ocr_lang="rus+eng")
    s = load_vision_settings(project)
    assert (s.mode, s.spec, s.ocr_lang) == ("ocr+model", "openrouter:some/vlm", "rus+eng")
    assert s.uses_ocr and s.uses_model


def test_unknown_mode_falls_back_to_model(project: Project) -> None:
    _set_vision_cfg(project, mode="magic")
    assert load_vision_settings(project).mode == "model"


def test_mode_off_installs_no_adapter(project: Project) -> None:
    _set_vision_cfg(project, mode="off")
    assert build_vision_adapter(project) is None
    assert install_vision_adapter(project) is None
    assert get_vision_adapter() is None


def test_install_registers_the_adapter(project: Project) -> None:
    adapter = install_vision_adapter(project)
    assert adapter is not None
    assert get_vision_adapter() is adapter


# ---- describe ----


def test_model_pass_uses_the_routed_model(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "openrouter:moonshotai/kimi-k2.5")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    calls: list = []
    _stub_describe(monkeypatch, calls)

    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings())
    assert adapter.describe_image(_JPEG, "image/jpeg") == "a chart with two bars"
    provider_name, model, image_bytes, mime, _prompt = calls[0]
    assert (provider_name, model, image_bytes, mime) == (
        "openrouter",
        "moonshotai/kimi-k2.5",
        _JPEG,
        "image/jpeg",
    )


def test_pinned_model_wins_over_routing(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine is text-only (ollama): `[vision] model` is how the user
    points images at something that can actually see."""
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "ollama:qwen3:4b-instruct")
    _set_vision_cfg(project, model="openrouter:z-ai/glm-4.6v")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    calls: list = []
    _stub_describe(monkeypatch, calls)

    adapter = RoutedVisionAdapter(project=project, settings=load_vision_settings(project))
    adapter.describe_image(_JPEG, "image/jpeg")
    assert calls[0][0:2] == ("openrouter", "z-ai/glm-4.6v")


def test_ocr_only_never_calls_a_model(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    _stub_describe(monkeypatch, calls)
    monkeypatch.setattr("veles.core.vision.adapter.ocr_bytes", lambda data, lang: "INVOICE 42")

    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings(mode="ocr"))
    out = adapter.describe_image(_JPEG, "image/jpeg")
    assert "INVOICE 42" in out
    assert calls == []


def test_ocr_plus_model_combines_both(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "openrouter:some/vlm")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _stub_describe(monkeypatch, [])
    monkeypatch.setattr("veles.core.vision.adapter.ocr_bytes", lambda data, lang: "INVOICE 42")

    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings(mode="ocr+model"))
    out = adapter.describe_image(_JPEG, "image/jpeg")
    assert "INVOICE 42" in out
    assert "a chart with two bars" in out


def test_missing_tesseract_does_not_kill_the_model_pass(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "openrouter:some/vlm")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _stub_describe(monkeypatch, [])

    def boom(data, lang):
        raise backends.OCRUnavailable("tesseract binary not found in PATH")

    monkeypatch.setattr("veles.core.vision.adapter.ocr_bytes", boom)
    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings(mode="ocr+model"))
    assert "a chart" in adapter.describe_image(_JPEG, "image/jpeg")


def test_ocr_only_reports_missing_tesseract(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(data, lang):
        raise backends.OCRUnavailable("tesseract binary not found in PATH")

    monkeypatch.setattr("veles.core.vision.adapter.ocr_bytes", boom)
    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings(mode="ocr"))
    with pytest.raises(VisionError, match="tesseract"):
        adapter.describe_image(_JPEG, "image/jpeg")


def test_text_only_provider_says_how_to_fix_it(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "claude-cli:sonnet")
    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings())
    with pytest.raises(VisionError, match=r"\[vision\] model"):
        adapter.describe_image(_JPEG, "image/jpeg")


def test_missing_api_key_is_a_clean_vision_error(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.routing import set_project_route

    set_project_route(project, "vision", "openrouter:some/vlm")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("veles.core.secrets.get_provider_key", lambda *a, **kw: None)
    adapter = RoutedVisionAdapter(project=project, settings=VisionSettings())
    with pytest.raises(VisionError, match="no API key"):
        adapter.describe_image(_JPEG, "image/jpeg")


def test_local_provider_is_a_valid_vision_backend() -> None:
    """A local llava/qwen-vl behind ollama speaks the OpenAI wire format —
    that's the free way to give a text-only engine eyes."""
    assert {"ollama", "llamacpp", "openai-compat"} <= backends.VISION_PROVIDERS
