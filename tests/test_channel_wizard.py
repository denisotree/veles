"""M137: add-channel wizard + `veles channel {add,remove}`.

The wizard reuses the `cli/wizard.py` Prompter abstraction (injectable for
tests) and a platform's `cred_fields` descriptor: secrets go to the keychain
(`set_provider_key`, mocked by the autouse `FakeKeyring` fixture in
`tests/conftest.py`), non-secret fields to the channel's config block — global
`[channels.<type>]` or per-session `[daemon.<name>.channels.<type>]`.
"""

from __future__ import annotations

from pathlib import Path

from veles.cli.channel_wizard import add_channel, remove_channel
from veles.core.project import init_project
from veles.core.project_config import (
    get_section,
    list_channel_configs,
    load_project_config,
    save_project_config,
)


def _scripted_prompter(answers: dict[str, str]):
    """Prompter that matches by a substring of the prompt label."""

    def ask(prompt: str, default):
        for needle, value in answers.items():
            if needle.lower() in prompt.lower():
                return value
        return default if default is not None else ""

    return ask


def test_add_telegram_to_default_daemon_writes_config_and_keychain(tmp_path: Path, fake_keyring):
    from veles.core.secrets import get_provider_key

    project = init_project(tmp_path / "p", name="p")
    prompter = _scripted_prompter({"bot token": "123:ABC", "chat ids": "111, 222"})
    rc = add_channel(project, channel="telegram", prompter=prompter)
    assert rc == 0

    cfg = load_project_config(project)
    block = get_section(cfg, "channels", "telegram")
    assert block["enabled"] is True
    assert block["whitelist"] == ["111", "222"]
    # Secret went to the keychain, NOT the config block.
    assert "bot_token" not in block
    assert get_provider_key("telegram", project=project.name) == "123:ABC"


def test_add_telegram_to_named_session(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    # Declare a named daemon session so its channels nest under [daemon.api].
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)

    prompter = _scripted_prompter({"bot token": "tok", "chat ids": ""})
    rc = add_channel(project, session="api", channel="telegram", prompter=prompter)
    assert rc == 0

    cfg = load_project_config(project)
    block = get_section(cfg, "daemon", "api", "channels", "telegram")
    assert block["enabled"] is True
    # Per-session config is read by the M136 bus only for that session.
    assert list_channel_configs(cfg, daemon_session="api") == [("telegram", block)]
    assert list_channel_configs(cfg) == []  # global block untouched


def test_add_missing_required_secret_errors(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    prompter = _scripted_prompter({"bot token": ""})  # required, blank
    rc = add_channel(project, channel="telegram", prompter=prompter)
    assert rc == 2
    assert get_section(load_project_config(project), "channels", "telegram") == {}


def test_add_unknown_channel_errors(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    rc = add_channel(project, channel="nope", prompter=_scripted_prompter({}))
    assert rc == 2


def test_remove_channel_drops_block(tmp_path: Path, fake_keyring):
    project = init_project(tmp_path / "p", name="p")
    add_channel(
        project,
        channel="telegram",
        prompter=_scripted_prompter({"bot token": "t", "chat ids": "1"}),
    )
    assert get_section(load_project_config(project), "channels", "telegram")["enabled"]

    rc = remove_channel(project, "telegram")
    assert rc == 0
    assert get_section(load_project_config(project), "channels", "telegram") == {}


def test_remove_absent_channel_errors(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    assert remove_channel(project, "telegram") == 1


# ---- collect/apply split (shared by CLI wizard + TUI flow, M137-in-TUI) ----


def test_collect_channel_fields_splits_secret_and_config():
    from veles.channels.platform_registry import get_platform
    from veles.cli.channel_wizard import collect_channel_fields

    entry = get_platform("telegram")
    ask = _scripted_prompter({"bot token": "123:ABC", "chat ids": "1, 2"})
    secrets, config_fields = collect_channel_fields(entry, ask)
    assert secrets == {"bot_token": "123:ABC"}
    assert config_fields == {"whitelist": ["1", "2"]}


def test_collect_channel_fields_required_blank_returns_none():
    from veles.channels.platform_registry import get_platform
    from veles.cli.channel_wizard import collect_channel_fields

    entry = get_platform("telegram")
    assert collect_channel_fields(entry, _scripted_prompter({"bot token": ""})) is None


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
        channel="telegram",
        secrets={"bot_token": "tok"},
        config_fields={"whitelist": ["7"]},
    )
    block = get_section(load_project_config(project), "daemon", "api", "channels", "telegram")
    assert block == {"whitelist": ["7"], "enabled": True}
    assert get_provider_key("telegram", project=project.name) == "tok"


def test_delete_channel_block_returns_bool(tmp_path: Path, fake_keyring):
    from veles.cli.channel_wizard import apply_channel, delete_channel_block

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)
    apply_channel(project, session="api", channel="telegram", secrets={}, config_fields={})
    assert delete_channel_block(project, "telegram", session="api") is True
    assert get_section(load_project_config(project), "daemon", "api", "channels") == {}
    # Second delete → False (already gone).
    assert delete_channel_block(project, "telegram", session="api") is False


def test_apply_channel_keychain_failure_leaves_no_half_write(tmp_path: Path, monkeypatch):
    """A keychain write failure must abort BEFORE the config is enabled — no
    tokenless-but-enabled `[channels.telegram]` block (M138-followup robustness)."""
    import veles.core.secrets as secrets_mod
    from veles.cli.channel_wizard import apply_channel

    project = init_project(tmp_path / "p", name="p")

    def boom(*a, **kw):
        raise secrets_mod.KeyringUnavailable("no backend")

    monkeypatch.setattr(secrets_mod, "set_provider_key", boom)

    import pytest

    with pytest.raises(secrets_mod.KeyringUnavailable):
        apply_channel(
            project,
            session=None,
            channel="telegram",
            secrets={"bot_token": "x"},
            config_fields={},
        )
    # Config untouched — no enabled-but-tokenless block.
    assert get_section(load_project_config(project), "channels") == {}
