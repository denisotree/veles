"""M181 — `veles init` heals a directory copied from another project.

`cp -R old new && cd new && veles init` carries `old`'s `.veles/` (its stale
default AGENTS.md titled `# old`, and its memory.db). init writes a fresh
`project.toml` for `new` but must not silently keep the wrong identity:
- a stale *default* AGENTS.md whose title ≠ the new name is regenerated;
- a customised AGENTS.md is preserved;
- a carried-over memory.db is flagged (not auto-deleted).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache
from veles.core.layout.discovery import find_layout
from veles.core.layout.scaffold import apply_scaffold
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    clear_engine_cache()
    yield
    clear_engine_cache()


_DEFAULT = "# {name}\n\nAdd your project context here.\n\n## Layout\n\n- x\n"


# ---- apply_scaffold regeneration ----


def test_apply_scaffold_regenerates_stale_default(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "AGENTS.md").write_text(_DEFAULT.format(name="mind-palace"), encoding="utf-8")
    pack = find_layout("llm-wiki", project=None)
    apply_scaffold(pack, root, "proj")
    new = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert new.splitlines()[0] == "# proj"
    assert "mind-palace" not in new


def test_apply_scaffold_preserves_customised(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    custom = "# Whatever I Want\n\nMy real project context, no marker.\n"
    (root / "AGENTS.md").write_text(custom, encoding="utf-8")
    pack = find_layout("llm-wiki", project=None)
    apply_scaffold(pack, root, "proj")
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == custom


def test_apply_scaffold_keeps_default_with_matching_title(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    same = _DEFAULT.format(name="proj")
    (root / "AGENTS.md").write_text(same, encoding="utf-8")
    pack = find_layout("llm-wiki", project=None)
    apply_scaffold(pack, root, "proj")
    # Regenerated-or-not, the title is right and no churn changes the identity.
    assert (root / "AGENTS.md").read_text(encoding="utf-8").splitlines()[0] == "# proj"


# ---- init_project heal of a copied .veles/ ----


def test_init_regenerates_cloned_agents_md(tmp_path: Path) -> None:
    """Simulate `cp -R old new` (a .veles/ without project.toml, carrying a
    stale default AGENTS.md) then `veles init`."""
    root = tmp_path / "main"
    (root / ".veles").mkdir(parents=True)
    (root / "AGENTS.md").write_text(_DEFAULT.format(name="mind-palace"), encoding="utf-8")
    (root / ".veles" / "memory.db").write_bytes(b"sqlite-ish bytes")  # foreign memory

    project = init_project(root, name="main", layout="llm-wiki")
    assert project.name == "main"
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.splitlines()[0] == "# main"
    assert "mind-palace" not in agents


def test_init_warns_about_carried_over_memory(tmp_path: Path, capsys) -> None:
    root = tmp_path / "main"
    (root / ".veles").mkdir(parents=True)
    (root / ".veles" / "memory.db").write_bytes(b"x")
    init_project(root, name="main", layout="llm-wiki")
    err = capsys.readouterr().err
    assert "memory.db" in err and "prior project" in err
