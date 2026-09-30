"""Tests for the generic external-memory-provider builder.

Providers come from modules (`api.add_memory_provider`); this file tests the
builder's contract only. Concrete adapters (Honcho, Mem0, Supermemory, ...)
moved to registry extensions.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.core.memory.providers import build_extra_providers
from veles.core.memory.providers import builder as builder_mod
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry


class _Fake:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.name = "fake"

    def recall(self, query: str, *, limit: int) -> list:
        return []


@pytest.fixture
def registry() -> Iterator[ModuleRegistry]:
    reg = ModuleRegistry()
    token = set_module_registry(reg)
    builder_mod._warned.clear()
    yield reg
    reset_module_registry(token)


def _config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_no_config_returns_empty(tmp_path: Path, registry: ModuleRegistry) -> None:
    assert build_extra_providers(tmp_path / "missing.toml") == []


def test_factory_gets_its_section(tmp_path: Path, registry: ModuleRegistry) -> None:
    ModuleAPI(registry, "m").add_memory_provider("fake", lambda cfg: _Fake(cfg))
    cfg = _config(tmp_path, '[memory.external.fake]\napi_key = "k"\n')
    [provider] = build_extra_providers(cfg)
    assert provider.cfg == {"api_key": "k"}


def test_factory_none_skips(tmp_path: Path, registry: ModuleRegistry) -> None:
    ModuleAPI(registry, "m").add_memory_provider("fake", lambda cfg: None)
    assert build_extra_providers(_config(tmp_path, "[memory.external.fake]\n")) == []


def test_factory_exception_is_contained(tmp_path: Path, registry: ModuleRegistry, capsys) -> None:
    def boom(cfg: dict) -> object:
        raise RuntimeError("bad key")

    ModuleAPI(registry, "m").add_memory_provider("fake", boom)
    cfg = _config(tmp_path, "[memory.external.fake]\n")
    assert build_extra_providers(cfg) == []
    assert build_extra_providers(cfg) == []  # called once per turn: warn only once
    assert capsys.readouterr().err.count("bad key") == 1


def test_configured_but_not_installed_warns_once(
    tmp_path: Path, registry: ModuleRegistry, capsys
) -> None:
    cfg = _config(tmp_path, '[memory.external.mem0]\napi_key = "k"\n')
    assert build_extra_providers(cfg) == []
    assert build_extra_providers(cfg) == []
    err = capsys.readouterr().err
    assert err.count("veles registry install --user mem0") == 1


def test_duplicate_provider_name_rejected(registry: ModuleRegistry) -> None:
    ModuleAPI(registry, "a").add_memory_provider("fake", lambda cfg: None)
    with pytest.raises(ValueError, match="already registered"):
        ModuleAPI(registry, "b").add_memory_provider("fake", lambda cfg: None)


def test_non_slug_name_rejected(registry: ModuleRegistry) -> None:
    with pytest.raises(ValueError):
        ModuleAPI(registry, "a").add_memory_provider("Bad Name", lambda cfg: None)


def test_malformed_toml_returns_empty(tmp_path: Path, registry: ModuleRegistry) -> None:
    assert build_extra_providers(_config(tmp_path, "not = [toml")) == []


def test_no_module_registry_returns_empty(tmp_path: Path) -> None:
    cfg = _config(tmp_path, "[memory.external.fake]\n")
    assert build_extra_providers(cfg) == []
