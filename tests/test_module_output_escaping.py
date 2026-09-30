"""The agent can write `module.toml` and create dirs under `.veles/modules/`: module
names and paths must never reach the terminal with raw control characters."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.cli import main
from veles.cli._project import _load_project_modules
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.module_manifest import ManifestError, parse_manifest
from veles.core.project import init_project

_EVIL = "\n\x1b[1A"
_TOML = '[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "m.py:register"\n'


@pytest.fixture(autouse=True)
def _yes() -> Iterator[None]:
    token = set_critical_confirmer(lambda op, summary: True)
    yield
    reset_critical_confirmer(token)


def _write(d: Path, toml: str) -> Path:
    d.mkdir(parents=True)
    (d / "module.toml").write_text(toml, encoding="utf-8")
    (d / "m.py").write_text("def register(api):\n    pass\n", encoding="utf-8")
    return d


def _clean(text: str) -> bool:
    return "\x1b" not in text and "a\n" not in text and "b\n" not in text and "x\n" not in text


def test_manifest_name_must_be_a_slug() -> None:
    with pytest.raises(ManifestError) as exc:
        parse_manifest(_TOML.format(name="x\\n\\u001b[1A"))
    assert "\x1b" not in str(exc.value)
    assert parse_manifest(_TOML.format(name="ok-name2")).name == "ok-name2"


def test_slug_rejects_a_trailing_newline() -> None:
    """`$` in `re.match` also matches before a final newline — slugs must match exactly."""
    from veles.core.registry.model import is_slug

    assert is_slug("guard")
    assert not is_slug("guard\n")
    with pytest.raises(ManifestError):
        parse_manifest(_TOML.format(name="guard\\n"))


def test_control_characters_in_module_name_never_reach_stderr_raw(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    # TOML escapes: the parsed name is "x\n\x1b[1A".
    _write(project.modules_dir / "evil", _TOML.format(name="x\\n\\u001b[1A"))
    assert _load_project_modules(project).modules == []
    err = capsys.readouterr().err
    assert _clean(err)
    assert "evil" in err


def test_control_characters_in_module_dir_name_never_reach_stderr_raw(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    project = init_project(tmp_path / "p", name="p")
    for prefix in ("a", "b"):
        _write(project.modules_dir / f"{prefix}{_EVIL}", _TOML.format(name="twin"))
    _write(project.modules_dir / f"c{_EVIL}", _TOML.format(name="solo"))
    assert _load_project_modules(project).modules == []
    monkeypatch.chdir(project.root)
    for argv in (
        ["module", "list"],
        ["module", "approve", "twin"],
        ["module", "show", "twin"],
        ["module", "remove", "--yes", "twin"],
        ["module", "approve", "solo"],
    ):
        main(argv)
    captured = capsys.readouterr()
    assert _clean(captured.err + captured.out)
    assert "twin" in captured.err and "approved module 'solo'" in captured.err
    capsys.readouterr()
    assert _load_project_modules(project).modules == ["solo"]
    assert main(["module", "remove", "--yes", "solo"]) == 0
    assert _clean(capsys.readouterr().err)


def test_hook_error_is_printed_escaped(capsys) -> None:
    from veles.core.modules import (
        ModuleAPI,
        ModuleRegistry,
        fire_hook,
        reset_module_registry,
        set_module_registry,
    )

    def boom(ctx: object) -> None:
        raise RuntimeError(f"x{_EVIL}")

    registry = ModuleRegistry()
    ModuleAPI(registry, "m").add_hook("pre_turn", boom)
    token = set_module_registry(registry)
    try:
        fire_hook("pre_turn")
    finally:
        reset_module_registry(token)
    err = capsys.readouterr().err
    assert "RuntimeError" in err and _clean(err)
