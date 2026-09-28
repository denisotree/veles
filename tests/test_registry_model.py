from pathlib import Path

import pytest

from tests.registry_helpers import write_extension, write_registry
from veles.core.registry.model import (
    ExtensionError,
    is_slug,
    load_registry_meta,
    parse_extension,
    scan_registry,
)

_SHA = "a" * 40
_TREE = "b" * 64


def _ext(body: str, source: str = 'type = "path"') -> str:
    return (
        '[extension]\nname = "slack"\nkind = "module"\nversion = "0.3.0"\n'
        'description = "Slack"\nlicense = "Apache-2.0"\nrequires_veles = ">=1.0"\n'
        f"{body}\n[source]\n{source}\n"
    )


def test_parse_minimal_path_module() -> None:
    ext = parse_extension(_ext('provides = ["hook:pre_turn"]'), group="official")
    assert ext.name == "slack"
    assert ext.kind == "module"
    assert ext.source.type == "path"
    assert ext.provides == ("hook:pre_turn",)
    assert ext.group == "official"


def test_parse_git_source() -> None:
    src = f'type = "git"\nurl = "https://x/y"\ncommit = "{_SHA}"\nsha256 = "{_TREE}"'
    ext = parse_extension(_ext("", source=src))
    assert ext.source.commit == _SHA
    assert ext.source.sha256 == _TREE


@pytest.mark.parametrize(
    ("body", "source", "needle"),
    [
        (
            "",
            'type = "git"\nurl = "https://x/y"\ncommit = "main"\nsha256 = "' + _TREE + '"',
            "commit",
        ),
        ("", 'type = "git"\nurl = "https://x/y"\ncommit = "' + _SHA + '"', "sha256"),
        ("", 'type = "path"\nurl = "https://x/y"', "path"),
        ("", 'type = "path"\nsha256 = "' + _TREE + '"', "path"),
        ("", 'type = "zip"', "source.type"),
        (
            "",
            f'type = "git"\nurl = "--upload-pack=touch /x"\ncommit = "{_SHA}"\nsha256 = "{_TREE}"',
            "must not start",
        ),
        (
            "",
            f'type = "git"\nurl = "https://x/y"\ncommit = "{_SHA}"\nsha256 = "{_TREE}"\n'
            'subdir = "/etc"',
            "subdir",
        ),
        (
            "",
            f'type = "git"\nurl = "https://x/y"\ncommit = "{_SHA}"\nsha256 = "{_TREE}"\n'
            'subdir = "../x"',
            "subdir",
        ),
    ],
)
def test_parse_rejects_bad_source(body: str, source: str, needle: str) -> None:
    with pytest.raises(ExtensionError, match=needle):
        parse_extension(_ext(body, source=source))


def test_parse_rejects_bad_fields() -> None:
    with pytest.raises(ExtensionError, match="name"):
        parse_extension(_ext("").replace('name = "slack"', 'name = "Slack!"'))
    with pytest.raises(ExtensionError, match="kind"):
        parse_extension(_ext("").replace('kind = "module"', 'kind = "plugin"'))
    with pytest.raises(ExtensionError, match="version"):
        parse_extension(_ext("").replace('version = "0.3.0"', 'version = "1.0"'))


def test_provides_only_for_modules() -> None:
    text = _ext('provides = ["hook:pre_turn"]').replace('kind = "module"', 'kind = "skill"')
    with pytest.raises(ExtensionError, match="provides"):
        parse_extension(text)


def test_mcp_kind_requires_recipe() -> None:
    text = _ext("").replace('kind = "module"', 'kind = "mcp"')
    with pytest.raises(ExtensionError, match=r"\[mcp\]"):
        parse_extension(text)
    ext = parse_extension(text + '\n[mcp]\ncommand = "graphify-mcp"\n')
    assert ext.mcp == {"command": "graphify-mcp"}


def test_scan_registry_collects_entries_and_errors(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "reg")
    write_extension(root, "official", "alpha")
    broken = write_extension(root, "community", "beta")
    (broken / "extension.toml").write_text("not toml [", encoding="utf-8")
    entries, errors = scan_registry(root)
    assert [e.name for e in entries] == ["alpha"]
    assert entries[0].dir == root / "extensions" / "official" / "alpha"
    assert errors and errors[0][0] == broken / "extension.toml"


def test_load_registry_meta(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "reg", name="acme", public=True)
    meta = load_registry_meta(root)
    assert (meta.name, meta.schema, meta.public) == ("acme", 1, True)
    with pytest.raises(ExtensionError):
        load_registry_meta(tmp_path)


def test_scan_registry_reports_bad_encoding_without_raising(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "reg")
    ext = write_extension(root, "official", "bad")
    (ext / "extension.toml").write_bytes(b"\xff\xfe")
    entries, errors = scan_registry(root)
    assert entries == []
    assert errors and errors[0][0] == ext / "extension.toml"
    assert "extension.toml" in str(errors[0][0])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("alpha", True),
        ("alpha-2", True),
        ("a", True),
        ("../evil", False),
        ("has/slash", False),
        ('has"quote', False),
        ("", False),
        ("-leading-dash", False),
        ("Has-Upper", False),
    ],
)
def test_is_slug(value: str, expected: bool) -> None:
    assert is_slug(value) is expected


def test_load_registry_meta_reports_bad_encoding_as_extension_error(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "reg")
    (root / "registry.toml").write_bytes(b"\xff\xfe")
    with pytest.raises(ExtensionError, match=r"registry\.toml"):
        load_registry_meta(root)
