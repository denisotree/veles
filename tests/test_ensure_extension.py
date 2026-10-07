"""`ensure_extension` — a project that needs a layout or engine that isn't installed
is offered the install (TTY) or told how (no TTY); it never raises, warns once per
need per process, and touches neither the network nor the project's data when it
can't ask."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from veles.core.contributions import Engine
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project
from veles.core.registry import ensure
from veles.core.registry.catalog import ResolveError
from veles.core.registry.ensure import EngineNeed, LayoutNeed, ensure_extension, needs_for


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    ensure.reset_warnings()
    yield tmp_path
    ensure.reset_warnings()


def _own_layout(home: Path, name: str, engines: str = "") -> None:
    d = home / "home" / ".veles" / "layouts" / name
    d.mkdir(parents=True)
    (d / "layout.toml").write_text(
        f'[layout]\nname = "{name}"\ndescription = "d"\n{engines}', encoding="utf-8"
    )


def _project_with_layout(home: Path, name: str):
    project = init_project(home / "p", name="p", layout="bare")
    toml = project.state_dir / "project.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace('layout = "bare"', f'layout = "{name}"'),
        encoding="utf-8",
    )
    from veles.core.project import load_project

    return load_project(project.root)


@pytest.fixture()
def fake_install(monkeypatch):
    calls: list[str] = []

    def resolve(spec: str):
        calls.append(f"resolve {spec}")
        return SimpleNamespace(ref=spec, ext=SimpleNamespace(kind="layout", requires=()))

    def install(found, *, project, user_scope, preapproved=False):
        calls.append(
            f"install {found.ref}"
            + (" --user" if user_scope else "")
            + (" --preapproved" if preapproved else "")
        )

    monkeypatch.setattr(ensure, "_resolve", resolve)
    monkeypatch.setattr(ensure, "_install", install)
    return calls


def test_missing_layout_is_a_need(home) -> None:
    project = _project_with_layout(home, "ghost-layout")
    assert needs_for(project) == [LayoutNeed("ghost-layout")]


def test_engine_without_contribution_is_a_need(home) -> None:
    _own_layout(home, "mine", "[layout.engines]\nghost = true\n")
    project = _project_with_layout(home, "mine")
    assert needs_for(project) == [EngineNeed("ghost")]


def test_engine_found_by_contribution_not_by_dir_name(home) -> None:
    _own_layout(home, "mine", "[layout.engines]\nghost = true\n")
    project = _project_with_layout(home, "mine")
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "some-other-dir-name").contribute("engine", "ghost", Engine("ghost"))
    reg.merge_from(scratch, "some-other-dir-name")
    token = set_module_registry(reg)
    try:
        assert needs_for(project) == []
    finally:
        reset_module_registry(token)


def test_former_builtins_come_from_public_official() -> None:
    assert ensure.ref_for(LayoutNeed("llm-wiki")) == "public:official/llm-wiki"
    assert ensure.ref_for(LayoutNeed("notes")) == "public:official/notes"
    assert ensure.ref_for(EngineNeed("wiki")) == "public:official/wiki"


def test_no_tty_warns_once_and_never_resolves(home, fake_install, capsys) -> None:
    project = _project_with_layout(home, "ghost-layout")
    need = LayoutNeed("ghost-layout")
    assert ensure_extension(need, project, interactive=False) is False
    assert ensure_extension(need, project, interactive=False) is False
    err = capsys.readouterr().err
    assert err.count("warning:") == 1 and "ghost-layout" in err
    assert "veles registry install" in err
    assert fake_install == []  # no catalog lookup, no network


def test_tty_installs_the_official_ref(home, fake_install) -> None:
    assert ensure_extension(LayoutNeed("llm-wiki"), None, interactive=True) is True
    assert fake_install == [
        "resolve public:official/llm-wiki",
        "install public:official/llm-wiki",
    ]


def test_engine_need_installs_the_provider(home, fake_install, monkeypatch) -> None:
    from veles.core.registry import catalog

    monkeypatch.setattr(
        catalog, "providers_of", lambda t: ["corp:eng/ghost"] if t == "engine:ghost" else []
    )
    assert ensure_extension(EngineNeed("ghost"), None, interactive=True) is True
    # An engine module serves every project with a pack that asks for it.
    assert fake_install == ["resolve corp:eng/ghost", "install corp:eng/ghost --user"]


def test_offline_or_declined_is_false_with_one_warning(home, monkeypatch, capsys) -> None:
    def offline(spec):
        raise ResolveError("registry unreachable")

    monkeypatch.setattr(ensure, "_resolve", offline)
    assert ensure_extension(LayoutNeed("llm-wiki"), None, interactive=True) is False
    err = capsys.readouterr().err
    assert err.count("warning:") == 1 and "public:official/llm-wiki" in err


def test_install_error_never_escapes(home, monkeypatch, capsys) -> None:
    monkeypatch.setattr(ensure, "_resolve", lambda spec: SimpleNamespace(ref=spec))

    def boom(found, *, project, user_scope, preapproved=False):
        raise RuntimeError("anything at all")

    monkeypatch.setattr(ensure, "_install", boom)
    assert ensure_extension(LayoutNeed("llm-wiki"), None, interactive=True) is False
    assert "anything at all" in capsys.readouterr().err


def test_cli_verb_on_a_project_with_a_missing_layout_warns_and_runs(
    home, capsys, monkeypatch
) -> None:
    from veles.cli import main

    project = _project_with_layout(home, "ghost-layout")
    agents = project.root / "AGENTS.md"
    before = agents.read_text(encoding="utf-8")
    monkeypatch.chdir(project.root)
    assert main(["sessions", "list"]) == 0
    err = capsys.readouterr().err
    assert err.count("warning: layout 'ghost-layout' is not installed") == 1
    assert agents.read_text(encoding="utf-8") == before


def test_a_module_verb_in_an_upgraded_project_names_the_install(home, capsys, monkeypatch) -> None:
    """`veles add` in an llm-wiki project after the upgrade, before any
    `registry update`: no cached catalog knows the verb, but the project's own
    missing layout explains it."""
    from veles.cli import main

    project = _project_with_layout(home, "llm-wiki")
    monkeypatch.chdir(project.root)
    with pytest.raises(SystemExit) as exc:
        main(["add", "notes.md"])
    assert exc.value.code == 2
    assert "veles registry install public:official/llm-wiki" in capsys.readouterr().err


def test_layout_sync_names_the_install(home, capsys, monkeypatch) -> None:
    from veles.cli import main

    project = _project_with_layout(home, "llm-wiki-gone")
    monkeypatch.chdir(project.root)
    assert main(["layout", "sync"]) == 2
    assert "veles registry install llm-wiki-gone" in capsys.readouterr().err


def test_ambiguous_engine_providers_install_nothing(
    home, fake_install, monkeypatch, capsys
) -> None:
    from veles.core.registry import catalog

    monkeypatch.setattr(catalog, "providers_of", lambda t: ["a:x/g", "b:y/g"])
    assert ensure_extension(EngineNeed("ghost"), None, interactive=True) is False
    assert fake_install == []
    err = capsys.readouterr().err
    assert "a:x/g" in err and "b:y/g" in err


def test_platform_need_installs_for_the_user_without_asking(home, fake_install, capsys) -> None:
    """A channel declared in config is an intent: its platform module installs
    itself — user scope, no confirmation, one line saying what and why."""
    from veles.core.registry.ensure import PlatformNeed, ref_for

    assert ref_for(PlatformNeed("telegram")) == "public:official/telegram"
    why = "declared in [channels.telegram]"
    assert ensure_extension(
        PlatformNeed("telegram"), None, interactive=False, auto=True, reason=why
    )
    assert fake_install[-1] == "install public:official/telegram --user --preapproved"
    assert f"({why})" in capsys.readouterr().err


def test_an_official_platform_comes_only_from_the_official_registry_when_connected(
    home, fake_install, monkeypatch
) -> None:
    """With `public` connected the official ref is the only candidate — even when
    its cache is stale and another registry provides the platform, that third
    party is never installed without asking. Only with `public` disconnected
    does a single other provider count (a fork, a private mirror)."""
    from veles.core.registry import catalog
    from veles.core.registry import config as registry_config
    from veles.core.registry.config import RegistrySource
    from veles.core.registry.ensure import PlatformNeed

    third_party = ["corp:official/telegram"]
    monkeypatch.setattr(catalog, "providers_of", lambda t: third_party)
    assert ensure_extension(PlatformNeed("telegram"), None, interactive=False, auto=True)
    assert fake_install[-1] == "install public:official/telegram --user --preapproved"

    monkeypatch.setattr(
        registry_config, "list_sources", lambda: [RegistrySource("corp", "https://x")]
    )
    assert ensure_extension(PlatformNeed("telegram"), None, interactive=False, auto=True)
    assert fake_install[-1] == "install corp:official/telegram --user --preapproved"


def test_a_wizard_without_loaded_modules_sees_an_installed_platform(home, monkeypatch) -> None:
    """The daemon picker and `veles init` load no modules: an installed platform
    must not look like a registry offer that installs a second time."""
    from tests.channels.fake_platform import install_as_user_module
    from veles.core.modules import reset_module_registry, set_module_registry
    from veles.core.registry.ensure import available_platforms, ensure_platform_interactive

    install_as_user_module()
    monkeypatch.setattr(
        ensure, "ensure_extension", lambda *a, **k: pytest.fail("installed platform reinstalled")
    )
    token = set_module_registry(None)
    try:
        assert available_platforms()[0] == "fake"
        assert ensure_platform_interactive("fake") is True
    finally:
        reset_module_registry(token)


def test_a_wizard_runs_a_platform_modules_entrypoint_once(home, monkeypatch) -> None:
    """Listing the platforms, then taking the pick, loads the user's modules
    once — an entrypoint never runs twice in one process."""
    from veles.core.modules import reset_module_registry, set_module_registry
    from veles.core.registry.ensure import available_platforms, ensure_platform_interactive
    from veles.core.registry.gate import approve_module
    from veles.core.user_paths import user_modules_dir

    calls = home / "register-calls.txt"
    mod = user_modules_dir() / "oncech"
    mod.mkdir(parents=True)
    (mod / "module.toml").write_text(
        '[module]\nname = "oncech"\ndescription = "d"\nentrypoint = "e.py:register"\n',
        encoding="utf-8",
    )
    (mod / "e.py").write_text(
        "from tests.channels.fake_platform import FAKE_SPEC\n\n"
        "def register(api):\n"
        f"    with open({str(calls)!r}, 'a') as fh:\n"
        "        fh.write('x')\n"
        "    api.contribute('platform', 'once', FAKE_SPEC)\n",
        encoding="utf-8",
    )
    approve_module(mod, name="oncech", project_root=None)
    token = set_module_registry(None)
    try:
        assert "once" in available_platforms()
        assert ensure_platform_interactive("once") is True
    finally:
        reset_module_registry(token)
    assert calls.read_text(encoding="utf-8") == "x"


def test_a_stale_registry_cache_is_refreshed_once_before_giving_up(home, monkeypatch) -> None:
    """Upgraders have a `public` cache from before the package existed: the
    install refreshes that registry and looks again instead of refusing."""
    from veles.core.registry import catalog, repo
    from veles.core.registry.catalog import ResolveError

    looked: list[str] = []
    updated: list[str] = []

    def resolve(spec):
        looked.append(spec)
        if not updated:
            raise ResolveError(f"no extension named {spec!r}")
        return SimpleNamespace(ref=spec)

    monkeypatch.setattr(catalog, "resolve", resolve)
    monkeypatch.setattr(repo, "update", lambda source: updated.append(source.name) or "abc")
    assert ensure._resolve("public:official/telegram").ref == "public:official/telegram"
    assert updated == ["public"] and len(looked) == 2


def test_auto_install_refuses_ambiguous_and_unreachable(home, fake_install, monkeypatch, capsys):
    from veles.core.registry import catalog
    from veles.core.registry.ensure import PlatformNeed

    monkeypatch.setattr(catalog, "providers_of", lambda token: ["a:x/s", "b:y/s"])
    assert not ensure_extension(PlatformNeed("slackish"), None, interactive=False, auto=True)
    assert fake_install == [] and "a:x/s" in capsys.readouterr().err

    def unreachable(spec):
        raise ResolveError("no registry named 'public'")

    monkeypatch.setattr(catalog, "providers_of", lambda token: [])  # nothing cached
    monkeypatch.setattr(ensure, "_resolve", unreachable)
    ensure.reset_warnings()
    assert not ensure_extension(PlatformNeed("telegram"), None, interactive=False, auto=True)
    assert "public" in capsys.readouterr().err


def test_channel_needs_lists_declared_platforms_without_a_module(home, fake_platform) -> None:
    from veles.core.project_config import load_project_config, save_project_config
    from veles.core.registry.ensure import PlatformNeed, channel_needs

    project = init_project(home / "p", name="p", layout="bare")
    cfg = load_project_config(project)
    cfg["channels"] = {
        "fake": {"enabled": True},
        "ghost": {"enabled": True},
        "off": {"enabled": False},
    }
    save_project_config(project, cfg)
    assert channel_needs(project, None) == [PlatformNeed("ghost")]


def test_doctor_names_a_declared_channel_without_its_module(home) -> None:
    from veles.core.doctor import _check_channel_platforms
    from veles.core.project_config import load_project_config, save_project_config

    project = init_project(home / "p", name="p", layout="bare")
    cfg = load_project_config(project)
    cfg["channels"] = {"ghost": {"enabled": True}}
    save_project_config(project, cfg)
    result = _check_channel_platforms(project)
    assert result.status == "warn" and "ghost" in result.message
    assert "daemon start" in (result.fix_hint or "")


def test_doctor_sees_an_installed_channel_module(home) -> None:
    """doctor loads no modules up front; an installed platform is not "missing"."""
    from tests.channels.fake_platform import install_as_user_module
    from veles.core.doctor import run_all
    from veles.core.modules import reset_module_registry, set_module_registry
    from veles.core.project_config import load_project_config, save_project_config

    install_as_user_module()
    project = init_project(home / "p", name="p", layout="bare")
    cfg = load_project_config(project)
    cfg["channels"] = {"fake": {"enabled": True}}
    save_project_config(project, cfg)
    token = set_module_registry(None)
    try:
        report = run_all(project)
    finally:
        reset_module_registry(token)
    assert next(r for r in report.results if r.name == "channel_platforms").status == "ok"


def test_channel_run_installs_the_named_platform(home, monkeypatch) -> None:
    """`veles channel run --channel X` names X explicitly — that is the decision."""
    from veles.cli.commands import channel as channel_cmd

    asked: list[tuple[str, bool, str | None]] = []

    def fake_ensure(need, project, *, interactive, auto=False, reason=None):
        asked.append((need.name, auto, reason))
        return False

    monkeypatch.setattr(ensure, "ensure_extension", fake_ensure)
    args = SimpleNamespace(
        channel_command="run",
        channel="slackish",
        secret=None,
        daemon_url=None,
        daemon_token="t",
        project_root=None,
    )
    assert channel_cmd.cmd_channel(args) == 2  # not installed → unknown platform
    assert asked == [("slackish", True, "named with --channel")]


def test_auto_install_names_the_block_that_declared_it(
    home, fake_install, monkeypatch, capsys
) -> None:
    from veles.core.project_config import load_project_config, save_project_config
    from veles.core.registry import catalog
    from veles.core.registry.ensure import ensure_channel_platforms

    monkeypatch.setattr(catalog, "providers_of", lambda token: ["corp:x/ghost"])
    project = init_project(home / "p", name="p", layout="bare")
    cfg = load_project_config(project)
    cfg["daemon"] = {"api": {"port": 8801, "channels": {"ghost": {"enabled": True}}}}
    save_project_config(project, cfg)
    ensure_channel_platforms(project, "api")
    assert "(declared in [daemon.api.channels.ghost])" in capsys.readouterr().err


def test_ensure_layout_true_for_an_installed_pack(home) -> None:
    assert ensure.ensure_layout("bare", interactive=False) is True


def test_ensure_layout_offers_a_missing_pack(home, monkeypatch) -> None:
    seen: list[object] = []
    monkeypatch.setattr(
        ensure, "ensure_extension", lambda need, project, *, interactive: seen.append(need) or True
    )
    assert ensure.ensure_layout("journal", interactive=True) is True
    assert seen == [LayoutNeed("journal")]


def test_layout_or_default_falls_back_and_says_so(home, monkeypatch, capsys) -> None:
    monkeypatch.setattr(ensure, "ensure_layout", lambda name, *, interactive: False)
    assert ensure.layout_or_default("llm-wiki", interactive=True) == "bare"
    assert "llm-wiki" in capsys.readouterr().err
    assert ensure.layout_or_default("bare", interactive=True) == "bare"
