"""M137: add-channel wizard + `veles channel {add,remove}`.

The wizard reuses the `cli/wizard.py` Prompter abstraction (injectable for
tests) and a platform's `cred_fields` descriptor: secrets go to the keychain
(`set_provider_key`, mocked by the autouse `FakeKeyring` fixture in
`tests/conftest.py`), non-secret fields to the channel's config block — global
`[channels.<type>]` or per-session `[daemon.<name>.channels.<type>]`. The
platform is the test one, `fake` (`tests/channels/fake_platform.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.channel_wizard import add_channel, remove_channel
from veles.core.project import init_project
from veles.core.project_config import (
    get_section,
    list_channel_configs,
    load_project_config,
    save_project_config,
)

pytestmark = pytest.mark.usefixtures("fake_platform")


def _scripted_prompter(answers: dict[str, str]):
    """Prompter that matches by a substring of the prompt label."""

    def ask(prompt: str, default):
        for needle, value in answers.items():
            if needle.lower() in prompt.lower():
                return value
        return default if default is not None else ""

    return ask


def test_add_channel_offers_and_installs_a_registry_platform(tmp_path: Path, monkeypatch):
    from veles.core.registry import ensure

    project = init_project(tmp_path / "p", name="p")
    asked: list[str] = []
    monkeypatch.setattr(ensure, "available_platforms", lambda: ["fake", "slackish"])
    monkeypatch.setattr(
        ensure, "ensure_platform_interactive", lambda name: asked.append(name) or False
    )
    rc = add_channel(project, prompter=_scripted_prompter({"channel type": "slackish"}))
    assert asked == ["slackish"] and rc == 2  # the install was declined → nothing written
    assert get_section(load_project_config(project), "channels") == {}


def test_add_channel_to_default_daemon_writes_config_and_keychain(tmp_path: Path, fake_keyring):
    from veles.core.secrets import get_provider_key

    project = init_project(tmp_path / "p", name="p")
    prompter = _scripted_prompter({"fake token": "123:ABC", "rooms": "111, 222"})
    rc = add_channel(project, channel="fake", prompter=prompter)
    assert rc == 0

    cfg = load_project_config(project)
    block = get_section(cfg, "channels", "fake")
    assert block["enabled"] is True
    assert block["rooms"] == ["111", "222"]
    # Secret went to the keychain, NOT the config block.
    assert "token" not in block
    assert get_provider_key("fake", project=project.name) == "123:ABC"


def test_add_channel_to_named_session(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    # Declare a named daemon session so its channels nest under [daemon.api].
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)

    prompter = _scripted_prompter({"fake token": "tok", "rooms": ""})
    rc = add_channel(project, session="api", channel="fake", prompter=prompter)
    assert rc == 0

    cfg = load_project_config(project)
    block = get_section(cfg, "daemon", "api", "channels", "fake")
    assert block["enabled"] is True
    # Per-session config is read by the M136 bus only for that session.
    assert list_channel_configs(cfg, daemon_session="api") == [("fake", block)]
    assert list_channel_configs(cfg) == []  # global block untouched


def test_add_missing_required_secret_errors(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    prompter = _scripted_prompter({"fake token": ""})  # required, blank
    rc = add_channel(project, channel="fake", prompter=prompter)
    assert rc == 2
    assert get_section(load_project_config(project), "channels", "fake") == {}


def test_add_unknown_channel_errors(tmp_path: Path, monkeypatch):
    from veles.core.registry import ensure

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(ensure, "ensure_platform_interactive", lambda name: False)
    rc = add_channel(project, channel="nope", prompter=_scripted_prompter({}))
    assert rc == 2


def test_remove_channel_drops_block(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    add_channel(
        project,
        channel="fake",
        prompter=_scripted_prompter({"fake token": "t", "rooms": "1"}),
    )
    assert get_section(load_project_config(project), "channels", "fake")["enabled"]

    rc = remove_channel(project, "fake")
    assert rc == 0
    assert get_section(load_project_config(project), "channels", "fake") == {}


def test_remove_absent_channel_errors(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    assert remove_channel(project, "fake") == 1


# ---- collect/apply split (shared by CLI wizard + TUI flow, M137-in-TUI) ----


def test_collect_channel_fields_splits_secret_and_config():
    from veles.cli.channel_wizard import collect_channel_fields
    from veles.core.platforms import get_platform

    entry = get_platform("fake")
    ask = _scripted_prompter({"fake token": "123:ABC", "rooms": "1, 2"})
    secrets, config_fields = collect_channel_fields(entry, ask)
    assert secrets == {"token": "123:ABC"}
    assert config_fields == {"rooms": ["1", "2"]}


def test_collect_channel_fields_required_blank_returns_none():
    from veles.cli.channel_wizard import collect_channel_fields
    from veles.core.platforms import get_platform

    entry = get_platform("fake")
    assert collect_channel_fields(entry, _scripted_prompter({"fake token": ""})) is None


def test_apply_channel_writes_session_block_and_keychain(tmp_path: Path, fake_keyring):
    from veles.cli.channel_wizard import apply_channel
    from veles.core.secrets import get_provider_key

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)

    apply_channel(
        project,
        session="api",
        channel="fake",
        secrets={"token": "tok"},
        config_fields={"rooms": ["7"]},
    )
    block = get_section(load_project_config(project), "daemon", "api", "channels", "fake")
    assert block == {"rooms": ["7"], "enabled": True}
    assert get_provider_key("fake", project=project.name) == "tok"


def test_apply_channel_writes_each_secret_to_its_slot(tmp_path: Path, fake_keyring):
    """A second secret field must not overwrite the first (they used to share
    the `<platform>` slot)."""
    from tests.channels.fake_platform import FakeGateway, contributing
    from veles.cli.channel_wizard import apply_channel
    from veles.core.platforms import CredField, PlatformSpec
    from veles.core.secrets import get_provider_key

    spec = PlatformSpec(
        build=FakeGateway,
        cred_fields=(
            CredField("bot", "b", secret=True, required=True),
            CredField("app", "a", secret=True),
        ),
    )
    project = init_project(tmp_path / "p", name="p")
    with contributing({"twosecret": spec}):
        apply_channel(
            project,
            session=None,
            channel="twosecret",
            secrets={"bot": "B", "app": "A"},
            config_fields={},
        )
    assert get_provider_key("twosecret", project=project.name, env_fallback=False) == "B"
    assert get_provider_key("twosecret.app", project=project.name, env_fallback=False) == "A"


def test_delete_channel_block_returns_bool(tmp_path: Path, fake_keyring):
    from veles.cli.channel_wizard import apply_channel, delete_channel_block

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)
    apply_channel(project, session="api", channel="fake", secrets={}, config_fields={})
    assert delete_channel_block(project, "fake", session="api") is True
    assert get_section(load_project_config(project), "daemon", "api", "channels") == {}
    # Second delete → False (already gone).
    assert delete_channel_block(project, "fake", session="api") is False


def test_apply_channel_keychain_failure_leaves_no_half_write(tmp_path: Path, monkeypatch):
    """A keychain write failure must abort BEFORE the config is enabled — no
    tokenless-but-enabled `[channels.<platform>]` block (M138-followup robustness)."""
    import veles.core.secrets as secrets_mod
    from veles.cli.channel_wizard import apply_channel

    project = init_project(tmp_path / "p", name="p")

    def boom(*a, **kw):
        raise secrets_mod.KeyringUnavailable("no backend")

    monkeypatch.setattr(secrets_mod, "set_provider_key", boom)

    with pytest.raises(secrets_mod.KeyringUnavailable):
        apply_channel(
            project,
            session=None,
            channel="fake",
            secrets={"token": "x"},
            config_fields={},
        )
    # Config untouched — no enabled-but-tokenless block.
    assert get_section(load_project_config(project), "channels") == {}
