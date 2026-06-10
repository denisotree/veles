"""M33 — multi-project registry persistence + CLI slash-prefix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.project_registry import (
    Registry,
    RegistryEntry,
    default_registry_path,
)


def _registry_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "registry.json"
    monkeypatch.setenv("VELES_REGISTRY_PATH", str(path))
    return path


# ---- default_registry_path / env override ----


def test_default_registry_path_uses_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "custom.json"
    monkeypatch.setenv("VELES_REGISTRY_PATH", str(custom))
    assert default_registry_path() == custom


def test_default_registry_path_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VELES_REGISTRY_PATH", raising=False)
    assert default_registry_path() == Path.home() / ".veles/projects/registry.json"


# ---- load / save ----


def test_load_returns_empty_when_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    reg = Registry.load(path)
    assert reg.list_entries() == []


def test_load_handles_corrupt_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    path.write_text("{ not json", encoding="utf-8")
    reg = Registry.load(path)
    assert reg.list_entries() == []


def test_save_creates_parent_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "registry.json"
    monkeypatch.setenv("VELES_REGISTRY_PATH", str(nested))
    reg = Registry.load(nested)
    project = init_project(tmp_path / "p", name="p")
    reg.add(project, slug="p")
    reg.save()
    assert nested.is_file()
    payload = json.loads(nested.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert "p" in payload["projects"]


# ---- add / remove / get / touch ----


def test_add_inserts_entry_with_slug_and_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="my-project")
    reg = Registry.load(path)
    entry = reg.add(project)
    assert entry.slug == "my-project"
    assert entry.path == str((tmp_path / "p").resolve())
    assert entry.last_active_at > 0


def test_add_updates_existing_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="x")
    reg = Registry.load(path)
    first = reg.add(project)
    second = reg.add(project)
    assert second.slug == first.slug
    assert second.last_active_at >= first.last_active_at
    assert len(reg.list_entries()) == 1


def test_add_with_explicit_slug(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="legacy-name")
    reg = Registry.load(path)
    reg.add(project, slug="custom")
    assert reg.get("custom") is not None
    assert reg.get("legacy-name") is None


def test_remove_pops_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="p")
    reg = Registry.load(path)
    reg.add(project)
    reg.remove("p")
    assert reg.get("p") is None
    with pytest.raises(KeyError):
        reg.remove("p")


def test_touch_bumps_last_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import time

    path = _registry_path(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="p")
    reg = Registry.load(path)
    reg.add(project)
    initial = reg.get("p")
    assert initial is not None
    time.sleep(0.01)
    bumped = reg.touch("p")
    assert bumped is not None
    assert bumped.last_active_at > initial.last_active_at


def test_touch_returns_none_for_unknown_slug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    reg = Registry.load(path)
    assert reg.touch("nope") is None


def test_list_entries_sorted_by_recent_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import time

    path = _registry_path(monkeypatch, tmp_path)
    p1 = init_project(tmp_path / "a", name="a")
    p2 = init_project(tmp_path / "b", name="b")
    reg = Registry.load(path)
    reg.add(p1)
    time.sleep(0.01)
    reg.add(p2)
    listed = reg.list_entries()
    assert [e.slug for e in listed] == ["b", "a"]


def test_save_load_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    p1 = init_project(tmp_path / "a", name="a")
    p2 = init_project(tmp_path / "b", name="b")
    reg = Registry.load(path)
    reg.add(p1)
    reg.add(p2)
    reg.save()

    reloaded = Registry.load(path)
    slugs = {e.slug for e in reloaded.list_entries()}
    assert slugs == {"a", "b"}
    a_entry = reloaded.get("a")
    assert a_entry is not None
    assert a_entry.path == str((tmp_path / "a").resolve())


def test_load_skips_malformed_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _registry_path(monkeypatch, tmp_path)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "projects": {
                    "good": {
                        "slug": "good",
                        "path": "/some/path",
                        "name": "good",
                        "last_active_at": 1.0,
                    },
                    "missing-path": {
                        "slug": "missing-path",
                        "name": "x",
                        "last_active_at": 2.0,
                    },
                    "not-a-dict": "scalar",
                },
            }
        ),
        encoding="utf-8",
    )
    reg = Registry.load(path)
    slugs = {e.slug for e in reg.list_entries()}
    assert slugs == {"good"}


# ---- /project slash-prefix in _cmd_run ----


def test_slash_prefix_switches_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from veles.cli import _maybe_apply_project_slash_prefix

    path = _registry_path(monkeypatch, tmp_path)
    target = init_project(tmp_path / "target", name="target")
    cwd_proj = init_project(tmp_path / "cwd", name="cwd")
    reg = Registry.load(path)
    reg.add(target)
    reg.save()

    new_proj, new_prompt = _maybe_apply_project_slash_prefix(
        cwd_proj, "/project target write a poem"
    )
    assert new_proj.root.resolve() == target.root.resolve()
    assert new_prompt == "write a poem"


def test_slash_prefix_passthrough_when_no_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from veles.cli import _maybe_apply_project_slash_prefix

    _registry_path(monkeypatch, tmp_path)
    cwd_proj = init_project(tmp_path / "cwd", name="cwd")
    new_proj, new_prompt = _maybe_apply_project_slash_prefix(cwd_proj, "tell me a joke")
    assert new_proj is cwd_proj
    assert new_prompt == "tell me a joke"


def test_slash_prefix_unknown_slug_warns_and_keeps_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from veles.cli import _maybe_apply_project_slash_prefix

    _registry_path(monkeypatch, tmp_path)
    cwd_proj = init_project(tmp_path / "cwd", name="cwd")
    new_proj, new_prompt = _maybe_apply_project_slash_prefix(cwd_proj, "/project ghost do work")
    assert new_proj is cwd_proj
    assert new_prompt == "/project ghost do work"
    err = capsys.readouterr().err
    assert "ghost" in err


def test_slash_prefix_match_with_no_rest_uses_placeholder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from veles.cli import _maybe_apply_project_slash_prefix

    path = _registry_path(monkeypatch, tmp_path)
    target = init_project(tmp_path / "target", name="target")
    cwd_proj = init_project(tmp_path / "cwd", name="cwd")
    reg = Registry.load(path)
    reg.add(target)
    reg.save()

    new_proj, new_prompt = _maybe_apply_project_slash_prefix(cwd_proj, "/project target")
    assert new_proj.root.resolve() == target.root.resolve()
    assert "no further instructions" in new_prompt


# ---- RegistryEntry surface ----


def test_registry_entry_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    e = RegistryEntry(slug="x", path="/p", name="x", last_active_at=1.0)
    with pytest.raises(FrozenInstanceError):
        e.slug = "y"  # type: ignore[misc]
