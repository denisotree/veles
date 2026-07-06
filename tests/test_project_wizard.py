"""M82: project-level wizard tests. Uses an injected prompter so no
stdin / TTY is required."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.cli import project_wizard as pw


@pytest.fixture
def tmp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _args(**overrides) -> argparse.Namespace:
    base = dict(command="run", no_wizard=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def _scripted(answers: list[str]):
    """Build a prompter that returns the next pre-canned answer."""
    it = iter(answers)

    def _prompter(prompt: str, default: str | None) -> str:
        try:
            return next(it)
        except StopIteration:
            return default or ""

    return _prompter


# ---------------- gate ----------------


def test_gate_blocks_when_no_wizard_flag(tmp_cwd: Path) -> None:
    assert pw.should_run_project_wizard(_args(no_wizard=True), tmp_cwd) is False


def test_gate_blocks_when_env_opt_out(tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_NO_WIZARD", "1")
    assert pw.should_run_project_wizard(_args(), tmp_cwd) is False


def test_gate_blocks_for_bootstrap_commands(tmp_cwd: Path) -> None:
    for cmd in ("init", "import", "models"):
        assert pw.should_run_project_wizard(_args(command=cmd), tmp_cwd) is False


def test_gate_blocks_when_project_already_exists(tmp_cwd: Path) -> None:
    # A real project marker = .veles/project.toml. Bare .veles/ alone
    # must NOT count (see regression test below).
    (tmp_cwd / ".veles").mkdir()
    (tmp_cwd / ".veles" / "project.toml").write_text(
        'name = "x"\ncreated_at = 0.0\n', encoding="utf-8"
    )
    # Stub TTY check so we isolate the project-already path.
    if sys.stdin.isatty():
        assert pw.should_run_project_wizard(_args(), tmp_cwd) is False


def test_gate_does_not_block_on_bare_veles_dir_without_project_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: an ancestor `.veles/` without `project.toml` (the user
    config dir at $HOME/.veles is the real-world case) used to make the
    wizard skip itself, leaving the user staring at 'no Veles project'."""
    # Simulate $HOME/.veles/ that holds only user-config files (no project.toml).
    fake_home = tmp_path / "home"
    user_veles = fake_home / ".veles"
    user_veles.mkdir(parents=True)
    (user_veles / "config.toml").write_text('language = "en"\n', encoding="utf-8")
    # Now run the gate from a sub-directory of fake_home — like cwd
    # being `~/code/whatever` for a real user.
    sub = fake_home / "code" / "anywhere"
    sub.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    if sys.stdin.isatty():
        assert pw.should_run_project_wizard(_args(), sub) is True


def test_intro_uses_active_locale(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Switching the active locale flips the intro string. Smoke that the
    wizard's bootstrap question routes through `t()` (we don't need a TTY
    here — we drive `run_project_wizard` directly with a scripted prompter)."""
    from veles.core import i18n

    monkeypatch.delenv("VELES_LOCALE", raising=False)
    i18n.reset_for_tests()
    i18n.set_active_locale("ru")
    token = pw.set_project_wizard_prompter(_scripted(["n"]))
    try:
        result = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
        i18n.reset_for_tests()
    assert result is None
    err = capsys.readouterr().err
    # Intro line goes through print → stderr; question goes through the
    # injected prompter. Asserting on intro is sufficient to prove the
    # active locale wires through `t()`.
    assert "не найден проект Veles" in err

    i18n.set_active_locale("en")
    token = pw.set_project_wizard_prompter(_scripted(["n"]))
    try:
        pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
        i18n.reset_for_tests()
    err = capsys.readouterr().err
    assert "No Veles project found" in err


def test_init_triggers_wiki_reindex(tmp_cwd: Path) -> None:
    token = pw.set_project_wizard_prompter(_scripted(["y", "n", "n", "n"]))
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
    assert project is not None
    # The FTS sidecar lands at <wiki_root>/wiki_index.db after reindex.
    assert (project.wiki_root / "wiki_index.db").is_file()


def test_gate_blocks_when_no_tty(tmp_cwd: Path) -> None:
    # Pytest stdin is typically non-TTY; this should naturally return False.
    assert pw.should_run_project_wizard(_args(), tmp_cwd) is False


# ---------------- bootstrap ----------------


def test_decline_bootstrap_returns_none(tmp_cwd: Path) -> None:
    token = pw.set_project_wizard_prompter(_scripted(["n"]))
    try:
        result = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
    assert result is None
    assert not (tmp_cwd / ".veles").exists()


def test_accept_bootstrap_creates_project(tmp_cwd: Path) -> None:
    # Answer: yes to bootstrap, no to every subsequent step.
    token = pw.set_project_wizard_prompter(_scripted(["y", "n", "n", "n"]))
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
    assert project is not None
    assert (tmp_cwd / ".veles").is_dir()
    assert (tmp_cwd / "AGENTS.md").is_file()


def test_provider_override_writes_config(tmp_cwd: Path) -> None:
    token = pw.set_project_wizard_prompter(
        _scripted(
            [
                "y",  # bootstrap
                "y",  # provider override
                "openai",  # provider
                "openai/gpt-4o",  # model
                "n",  # wiki seed (no candidates anyway)
                "n",  # telegram
            ]
        )
    )
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
    assert project is not None
    cfg_path = project.state_dir / "config.toml"
    assert cfg_path.is_file()
    content = cfg_path.read_text(encoding="utf-8")
    assert "openai" in content
    assert "gpt-4o" in content


def test_wiki_seed_copies_docs_into_sources_seed(tmp_cwd: Path) -> None:
    (tmp_cwd / "README.md").write_text("# Hello", encoding="utf-8")
    (tmp_cwd / "docs").mkdir()
    (tmp_cwd / "docs" / "intro.md").write_text("# Intro", encoding="utf-8")
    token = pw.set_project_wizard_prompter(
        _scripted(["y", "n", "y", "n"])  # bootstrap, no provider, yes seed, no tg
    )
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token)
    assert project is not None
    seed_dir = project.wiki_root / "sources" / "seed"
    assert seed_dir.is_dir()
    # The README and the docs/ entry both land under seed_dir.
    found = list(seed_dir.rglob("*.md"))
    assert any(p.name == "README.md" for p in found)
    assert any(p.name == "intro.md" for p in found)


def test_channel_writes_token_and_whitelist(tmp_cwd: Path) -> None:
    # M172: the channel step is registry-driven — pick a type, then fill the
    # platform's cred fields (telegram: bot_token, then whitelist).
    token_p = pw.set_project_wizard_prompter(
        _scripted(
            [
                "y",  # bootstrap
                "n",  # provider override
                "n",  # wiki seed
                "y",  # add a channel?
                "telegram",  # channel type (only registered platform)
                "bot-abc",  # bot_token cred
                "42",  # whitelist (comma-separated → single-entry list)
            ]
        )
    )
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token_p)
    assert project is not None
    cfg = (project.state_dir / "config.toml").read_text(encoding="utf-8")
    # Token now lives in the keychain, not the toml.
    assert "bot-abc" not in cfg
    assert "enabled = true" in cfg
    assert '"42"' in cfg
    from veles.core.secrets import delete_provider_key, get_provider_key

    assert get_provider_key("telegram", project=project.name) == "bot-abc"
    delete_provider_key("telegram", project=project.name)


def test_channel_skips_when_required_field_blank(tmp_cwd: Path) -> None:
    # A blank value for a required cred (telegram bot_token) aborts the step
    # and writes nothing — no half-configured channel block.
    token_p = pw.set_project_wizard_prompter(
        _scripted(
            [
                "y",  # bootstrap
                "n",  # provider
                "n",  # seed
                "y",  # add a channel?
                "telegram",  # channel type
                "",  # bot_token blank (required) → abort
            ]
        )
    )
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token_p)
    assert project is not None
    assert not (project.state_dir / "config.toml").exists()


def test_maybe_wrapper_returns_none_when_gate_blocks(tmp_cwd: Path) -> None:
    assert pw.maybe_run_project_wizard(_args(no_wizard=True), tmp_cwd) is None


# ---------------- daemon step: autostart + suppression (stdin flow, M197) ----------------


def test_run_project_wizard_autostarts_daemon(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stdin daemon step writes `[daemon]` config and, by default, spawns
    the daemon."""
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        pw, "_autostart_daemon", lambda proj, host, port: calls.append((host, port))
    )

    token_p = pw.set_project_wizard_prompter(
        _scripted(
            [
                "y",  # bootstrap
                "n",  # provider override
                "n",  # wiki seed (skipped if no candidates; harmless otherwise)
                "n",  # add a channel?
                "y",  # run as daemon?
                "127.0.0.1",  # host
                "9001",  # port
            ]
        )
    )
    try:
        project = pw.run_project_wizard(tmp_cwd)
    finally:
        pw.reset_project_wizard_prompter(token_p)
    assert project is not None
    cfg = (project.state_dir / "config.toml").read_text(encoding="utf-8")
    assert "[daemon]" in cfg
    assert "9001" in cfg
    assert calls == [("127.0.0.1", 9001)]


def test_run_project_wizard_suppresses_autostart(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`autostart_daemon=False` (set by `veles daemon start`) writes the config
    but does not spawn — the caller starts the daemon itself, so the two don't
    race on the global single-instance pid."""
    calls: list[tuple] = []
    monkeypatch.setattr(pw, "_autostart_daemon", lambda *a: calls.append(a))

    token_p = pw.set_project_wizard_prompter(
        _scripted(["y", "n", "n", "n", "y", "127.0.0.1", "9002"])
    )
    try:
        project = pw.run_project_wizard(tmp_cwd, autostart_daemon=False)
    finally:
        pw.reset_project_wizard_prompter(token_p)
    assert project is not None
    cfg = (project.state_dir / "config.toml").read_text(encoding="utf-8")
    assert "[daemon]" in cfg
    assert calls == []


def test_maybe_wrapper_threads_suppress_flag_into_stdin(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`args._suppress_wizard_daemon_autostart` must reach the stdin wizard as
    `autostart_daemon=False`."""
    monkeypatch.setattr(pw, "should_run_project_wizard", lambda args, cwd: True)

    captured: dict[str, object] = {}

    def _fake_run(cwd, *, skip_bootstrap_confirm=False, autostart_daemon=True):
        captured["autostart_daemon"] = autostart_daemon
        captured["skip_bootstrap_confirm"] = skip_bootstrap_confirm
        return None

    monkeypatch.setattr(pw, "run_project_wizard", _fake_run)

    pw.maybe_run_project_wizard(_args(_suppress_wizard_daemon_autostart=True), tmp_cwd)
    assert captured.get("autostart_daemon") is False


def test_maybe_wrapper_threads_skip_bootstrap_into_stdin(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`args._wizard_init_project_here` must skip the duplicate Initialize?
    prompt in the stdin wizard."""
    monkeypatch.setattr(pw, "should_run_project_wizard", lambda args, cwd: True)

    captured: dict[str, object] = {}

    def _fake_run(cwd, *, skip_bootstrap_confirm=False, autostart_daemon=True):
        captured["skip_bootstrap_confirm"] = skip_bootstrap_confirm
        return None

    monkeypatch.setattr(pw, "run_project_wizard", _fake_run)

    pw.maybe_run_project_wizard(_args(_wizard_init_project_here=True), tmp_cwd)
    assert captured.get("skip_bootstrap_confirm") is True
