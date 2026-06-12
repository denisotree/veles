"""M117.1: layout.toml manifest parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout.manifest import (
    LayoutManifestError,
    LayoutOperation,
    LayoutWritableZone,
    read_manifest,
)


def _write(toml_path: Path, body: str) -> Path:
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    toml_path.write_text(body, encoding="utf-8")
    return toml_path


# ---- happy path ----


def test_minimal_manifest_parses(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "minimal"
""",
    )
    m = read_manifest(p)
    assert m.name == "minimal"
    assert m.description == ""
    assert m.version == "0.0"
    assert m.writable_zones == ()
    assert m.operations == ()
    assert m.source == p


def test_full_manifest_parses(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "llm-wiki"
description = "Karpathy LLM Wiki"
version = "1.0"

[[layout.writable_zones]]
path = "wiki/"
description = "agent-writable knowledge"

[[layout.writable_zones]]
path = "sources/"
readonly = true
description = "raw immutable source material"

[[layout.operations]]
name = "ingest"
skill = "ingest"
description = "Read a source and write a wiki page"

[[layout.operations]]
name = "query"
skill = "query"
""",
    )
    m = read_manifest(p)
    assert m.name == "llm-wiki"
    assert m.description == "Karpathy LLM Wiki"
    assert m.version == "1.0"
    assert m.writable_zones == (
        LayoutWritableZone(path="wiki/", description="agent-writable knowledge"),
        LayoutWritableZone(
            path="sources/", description="raw immutable source material", readonly=True
        ),
    )
    assert m.operations == (
        LayoutOperation(
            name="ingest", skill="ingest", description="Read a source and write a wiki page"
        ),
        LayoutOperation(name="query", skill="query"),
    )


def test_read_manifest_accepts_directory_path(tmp_path: Path) -> None:
    """read_manifest can be called with the pack directory, not just
    the toml file — the discovery layer expects this."""
    pack_dir = tmp_path / "my-pack"
    _write(
        pack_dir / "layout.toml",
        """\
[layout]
name = "my-pack"
""",
    )
    m = read_manifest(pack_dir)
    assert m.name == "my-pack"


# ---- accessors ----


def test_writable_path_strings_excludes_readonly(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.writable_zones]]
path = "wiki/"

[[layout.writable_zones]]
path = "sources/"
readonly = true
""",
    )
    m = read_manifest(p)
    assert m.writable_path_strings() == ("wiki/",)


def test_operation_lookup_by_name(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.operations]]
name = "ingest"
skill = "ingest_skill"

[[layout.operations]]
name = "query"
skill = "query_skill"
""",
    )
    m = read_manifest(p)
    op = m.operation("query")
    assert op is not None and op.skill == "query_skill"
    assert m.operation("missing") is None


# ---- error paths ----


def test_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_manifest(tmp_path / "nope.toml")


def test_invalid_toml_raises_manifest_error(tmp_path: Path) -> None:
    p = _write(tmp_path / "layout.toml", '[layout\nname = "broken"\n')
    with pytest.raises(LayoutManifestError) as ei:
        read_manifest(p)
    assert "valid TOML" in str(ei.value)


def test_missing_layout_section(tmp_path: Path) -> None:
    p = _write(tmp_path / "layout.toml", 'name = "x"\n')
    with pytest.raises(LayoutManifestError) as ei:
        read_manifest(p)
    assert "[layout] section" in str(ei.value)


def test_missing_name_field(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
description = "no name"
""",
    )
    with pytest.raises(LayoutManifestError) as ei:
        read_manifest(p)
    assert "name" in str(ei.value)


def test_empty_name_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "   "
""",
    )
    with pytest.raises(LayoutManifestError):
        read_manifest(p)


def test_operation_missing_skill_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.operations]]
name = "ingest"
""",
    )
    with pytest.raises(LayoutManifestError) as ei:
        read_manifest(p)
    assert "skill" in str(ei.value)


def test_duplicate_operation_name_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.operations]]
name = "ingest"
skill = "a"

[[layout.operations]]
name = "ingest"
skill = "b"
""",
    )
    with pytest.raises(LayoutManifestError) as ei:
        read_manifest(p)
    assert "duplicate" in str(ei.value)


def test_writable_zone_missing_path_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.writable_zones]]
description = "no path"
""",
    )
    with pytest.raises(LayoutManifestError):
        read_manifest(p)


def test_writable_zone_readonly_must_be_bool(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "layout.toml",
        """\
[layout]
name = "x"

[[layout.writable_zones]]
path = "wiki/"
readonly = "yes"
""",
    )
    with pytest.raises(LayoutManifestError):
        read_manifest(p)
