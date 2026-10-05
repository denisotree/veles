"""Release E: a provider named by config, a flag or a route — known, retired,
installed from a registry, or unknown."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from veles.core.project import init_project
from veles.core.project_config import load_project_config, save_project_config
from veles.core.registry import ensure


@pytest.fixture()
def fake_install(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        ensure, "_resolve", lambda spec: SimpleNamespace(ref=spec, ext=SimpleNamespace(version="1"))
    )
    monkeypatch.setattr(
        ensure,
        "_install",
        lambda found, *, project, user_scope, preapproved=False: calls.append(found.ref),
    )
    ensure.reset_warnings()
    return calls


def test_run_with_an_unknown_provider_says_so(isolated_user_home: Path, capsys) -> None:
    from veles.cli._console import ensure_api_key

    assert ensure_api_key("opnrouter") is False
    err = capsys.readouterr().err
    assert "unknown provider 'opnrouter'" in err and "openrouter" in err


def test_a_retired_provider_names_its_replacement(isolated_user_home: Path, capsys) -> None:
    from veles.cli._console import check_provider

    assert check_provider("gemini-cli") is False
    assert "removed in 1.2.6" in capsys.readouterr().err


def test_a_named_registry_provider_installs_itself(
    isolated_user_home: Path, fake_install: list[str], capsys
) -> None:
    assert ensure.ensure_provider("antigravity-cli", reason="named with --provider") is False
    assert fake_install == ["public:official/antigravity-cli"]
    assert "(named with --provider)" in capsys.readouterr().err


def test_a_routed_provider_a_registry_offers_installs(
    isolated_user_home: Path, tmp_path: Path, fake_install: list[str], monkeypatch
) -> None:
    from veles.core.registry import catalog

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg["engine"] = {"provider": "openrouter", "model": "x/y"}
    cfg["routing"] = {"tasks": {"curator": "groqmod:llama", "insights": "typo:m"}}
    save_project_config(project, cfg)
    monkeypatch.setattr(
        catalog,
        "providers_of",
        lambda token: ["corp:x/groqmod"] if token == "provider:groqmod" else [],
    )
    # The typo nobody offers is doctor's to report, not an install.
    assert ensure.routed_provider_needs(project) == [
        ("groqmod", "named in [routing.tasks].curator")
    ]
    ensure.ensure_routed_providers(project)
    assert fake_install == ["corp:x/groqmod"]


def test_models_with_an_unknown_provider_says_so(isolated_user_home: Path, capsys) -> None:
    from veles.cli.commands.models import cmd_models

    rc = cmd_models(argparse.Namespace(provider="nope", refresh=False, as_json=False))
    assert rc == 2 and "unknown provider 'nope'" in capsys.readouterr().err


def test_provider_flag_takes_a_module_provider() -> None:
    from veles.cli._parsers import build_parser

    args = build_parser().parse_args(["run", "--provider", "some-module-provider", "hi"])
    assert args.provider == "some-module-provider"


def test_daemon_start_with_an_unknown_provider_refuses(
    isolated_user_home: Path, tmp_path: Path, monkeypatch, capsys, fake_channel
) -> None:
    from veles.cli.commands import daemon as daemon_cmd

    project = init_project(tmp_path, name="p")
    save_project_config(project, {"engine": {"provider": "opnrouter", "model": "m"}})
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        command="daemon", foreground=True, host="127.0.0.1", port=8765, provider=None
    )
    assert daemon_cmd._cmd_daemon_start(args) == 2
    assert "unknown provider 'opnrouter'" in capsys.readouterr().err


def test_doctor_names_a_provider_nothing_provides(isolated_user_home: Path, tmp_path: Path) -> None:
    from veles.core.doctor import _check_provider_catalog
    from veles.core.providers import user_catalog_path

    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"routing": {"tasks": {"curator": "typo:m"}}})
    user_catalog_path().parent.mkdir(parents=True, exist_ok=True)
    user_catalog_path().write_text('[providers.x]\nkind = "openai-api"\n', encoding="utf-8")
    result = _check_provider_catalog(project)
    assert result.status == "warn" and "typo" in result.message
    assert "no base_url" in (result.details or {}).get("catalogue", [""])[0]
