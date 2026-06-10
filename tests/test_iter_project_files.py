"""M78: `iter_project_files` walks the project skipping common ignored
dirs, but keeps `.veles/tmp/` reachable for clipboard-paste artifacts."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import iter_project_files


def test_lists_top_level_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("a", encoding="utf-8")
    (tmp_path / "main.py").write_text("b", encoding="utf-8")
    rels = [p.as_posix() for p in iter_project_files(tmp_path)]
    assert "README.md" in rels
    assert "main.py" in rels


def test_excludes_standard_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("x", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lodash.js").write_text("x", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "junk.txt").write_text("x", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("x", encoding="utf-8")
    rels = [p.as_posix() for p in iter_project_files(tmp_path)]
    assert "src/ok.py" in rels
    assert all(not r.startswith(".git/") for r in rels)
    assert all(not r.startswith("node_modules/") for r in rels)
    assert all(not r.startswith("__pycache__/") for r in rels)
    assert all(not r.startswith("tmp/") for r in rels)


def test_excludes_dot_veles_but_keeps_dot_veles_tmp(tmp_path: Path) -> None:
    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text("x", encoding="utf-8")
    (tmp_path / ".veles" / "memory.db").write_text("x", encoding="utf-8")
    (tmp_path / ".veles" / "tmp").mkdir()
    (tmp_path / ".veles" / "tmp" / "paste").mkdir()
    (tmp_path / ".veles" / "tmp" / "paste" / "img1.png").write_text("x", encoding="utf-8")
    rels = [p.as_posix() for p in iter_project_files(tmp_path)]
    assert "tmp/paste/img1.png" in rels or ".veles/tmp/paste/img1.png" in rels
    # config.toml inside .veles/ root should not appear:
    assert all("config.toml" not in r for r in rels if r.startswith(".veles"))


def test_respects_cap(tmp_path: Path) -> None:
    for i in range(30):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
    rels = iter_project_files(tmp_path, cap=10)
    assert len(rels) == 10


def test_paths_are_relative(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x", encoding="utf-8")
    rels = iter_project_files(tmp_path)
    for p in rels:
        assert not p.is_absolute()
