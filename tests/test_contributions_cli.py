"""`cli_command` — a module adds a `veles <verb>`; builtin verbs stay builtin, and
a verb that only an uninstalled extension provides points at the install."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli import main
from veles.core.project import init_project
from veles.core.registry.gate import approve_module

_MODULE = """
from veles.sdk.contributions import CliCommand


def _args(parser):
    parser.add_argument("--name", default="world")


def _hello(args, project, host):
    print(f"hello {args.name} from {project.name} provider={args.provider}")
    return 7


def register(api):
    api.contribute("cli_command", "hello", CliCommand(
        help="say hello", add_arguments=_args, run=_hello, run_flags=True))
    api.contribute("cli_command", "init", CliCommand(
        help="hijack", add_arguments=lambda p: None, run=lambda a, p, h: 99))
"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VELES_NO_WIZARD", "1")
    project = init_project(tmp_path / "p", name="p", layout="bare")
    d = project.modules_dir / "greeter"
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        '[module]\nname = "greeter"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(_MODULE, encoding="utf-8")
    approve_module(d, name="greeter", project_root=project.root)
    return project


def test_module_verb_runs(project, capsys) -> None:
    rc = main(
        ["hello", "--name", "ann", "--provider", "ollama", "--project-root", str(project.root)]
    )
    out = capsys.readouterr()
    assert rc == 7
    assert "hello ann from p provider=ollama" in out.out


def test_module_cannot_take_a_builtin_verb(project, capsys) -> None:
    main(["hello", "--project-root", str(project.root)])
    assert "init" in capsys.readouterr().err  # warned, skipped
    from veles.cli import _COMMANDS

    assert _COMMANDS["init"][0] == "veles.cli.commands.init"


def test_unknown_verb_points_at_the_extension(project, capsys, monkeypatch) -> None:
    from veles.core.registry import catalog

    def providers_of(token: str) -> list[str]:
        return ["public:official/ghost"] if token == "cli_command:ghost" else []

    monkeypatch.setattr(catalog, "providers_of", providers_of)
    with pytest.raises(SystemExit) as exc:
        main(["ghost", "x.md", "--project-root", str(project.root)])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "veles registry install public:official/ghost" in err


def test_wiki_add_is_a_module_verb(project, capsys) -> None:
    rc = main(["add", "https://example.com", "--project-root", str(project.root)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "wiki content engine" in err and "bare" in err


def test_providers_of_reads_cached_catalogs_only(monkeypatch) -> None:
    from types import SimpleNamespace

    from veles.core.registry import catalog

    seen: dict = {}

    def fake_available(*, registry=None, sync_missing=True):
        seen["sync_missing"] = sync_missing
        ext = SimpleNamespace(provides=("cli_command:add", "engine:wiki"))
        return [SimpleNamespace(ext=ext, ref="public:official/wiki")], []

    monkeypatch.setattr(catalog, "available", fake_available)
    assert catalog.providers_of("engine:wiki") == ["public:official/wiki"]
    assert catalog.providers_of("engine:other") == []
    assert seen["sync_missing"] is False
