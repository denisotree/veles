"""Tests for core/tools/toolsets.py — Tier δ M57 declarative composition."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.tools.toolsets import TOOLSETS, load_toolsets


def _write_toml(path: Path, body: str) -> None:
    path.write_text(body)


# ---------- bundled file ----------


def test_bundled_toolsets_have_canonical_keys() -> None:
    assert {"builtin", "run", "ingest"} <= set(TOOLSETS)


def test_run_toolset_inherits_from_builtin() -> None:
    """run = builtin + writers + network + advisor."""
    assert "read_file" in TOOLSETS["run"]
    assert "write_file" in TOOLSETS["run"]
    assert "wiki_search" in TOOLSETS["run"]


# ---------- include resolution ----------


def test_includes_pull_tools_transitively(tmp_path: Path) -> None:
    _write_toml(
        tmp_path / "ts.toml",
        "\n".join(
            [
                '[a]\ntools = ["t1"]',
                '[b]\nincludes = ["a"]\ntools = ["t2"]',
                '[c]\nincludes = ["b"]\ntools = ["t3"]',
            ]
        ),
    )
    ts = load_toolsets(tmp_path / "ts.toml")
    assert ts["c"] == ("t1", "t2", "t3")


def test_duplicate_tool_names_dedup_preserves_order(tmp_path: Path) -> None:
    _write_toml(
        tmp_path / "ts.toml",
        "\n".join(
            [
                '[a]\ntools = ["t1", "t2"]',
                '[b]\nincludes = ["a"]\ntools = ["t2", "t3"]',
            ]
        ),
    )
    ts = load_toolsets(tmp_path / "ts.toml")
    assert ts["b"] == ("t1", "t2", "t3")


def test_cycle_in_includes_raises(tmp_path: Path) -> None:
    _write_toml(
        tmp_path / "ts.toml",
        "\n".join(
            [
                '[a]\nincludes = ["b"]',
                '[b]\nincludes = ["a"]',
            ]
        ),
    )
    with pytest.raises(ValueError, match="cycle"):
        load_toolsets(tmp_path / "ts.toml")


def test_unknown_include_raises(tmp_path: Path) -> None:
    _write_toml(
        tmp_path / "ts.toml",
        '[a]\nincludes = ["nope"]',
    )
    with pytest.raises(KeyError, match="nope"):
        load_toolsets(tmp_path / "ts.toml")


def test_non_list_tools_raises(tmp_path: Path) -> None:
    _write_toml(tmp_path / "ts.toml", '[a]\ntools = "not-a-list"')
    with pytest.raises(ValueError, match="must be lists"):
        load_toolsets(tmp_path / "ts.toml")


# ---------- cli/_runtime.py module aliases ----------


def test_runtime_module_aliases_match_toolsets() -> None:
    from veles.cli._runtime import _INGEST_TOOLS, _RUN_TOOLS

    assert TOOLSETS["run"] == _RUN_TOOLS
    assert TOOLSETS["ingest"] == _INGEST_TOOLS
