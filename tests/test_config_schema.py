"""M201 — config validation: a typo in a security-relevant section must be
flagged, not silently ignored.

`config.toml` is free-form TOML read via `get_section`, so a mistyped key
(`whitlist` for `whitelist`) leaves the real control unset — and an empty
whitelist means "allow everyone". The validator flags unknown keys in the
sections that gate access (channels, daemon, mcp.servers); `veles doctor`
surfaces them as errors.
"""

from __future__ import annotations

import veles.channels.telegram  # noqa: F401 -- registers the telegram platform
from veles.core.config_schema import validate_config


def test_valid_channel_config_has_no_findings() -> None:
    cfg = {"channels": {"telegram": {"enabled": True, "bot_token": "x", "whitelist": ["@a"]}}}
    assert validate_config(cfg) == []


def test_typo_whitelist_in_channel_is_flagged() -> None:
    cfg = {"channels": {"telegram": {"enabled": True, "bot_token": "x", "whitlist": ["@a"]}}}
    findings = validate_config(cfg)
    assert any(f.key == "whitlist" and f.section == "channels.telegram" for f in findings)


def test_daemon_named_session_unknown_key_flagged() -> None:
    cfg = {"daemon": {"work": {"host": "127.0.0.1", "prot": 8765}}}  # 'prot' typo of 'port'
    findings = validate_config(cfg)
    assert any(f.key == "prot" and f.section == "daemon.work" for f in findings)


def test_daemon_legacy_scalar_keys_are_valid() -> None:
    cfg = {"daemon": {"enabled": True, "host": "127.0.0.1", "port": 8765}}
    assert validate_config(cfg) == []


def test_daemon_channels_subtable_is_validated() -> None:
    cfg = {"daemon": {"work": {"channels": {"telegram": {"bot_token": "x", "whitlist": []}}}}}
    findings = validate_config(cfg)
    assert any(f.key == "whitlist" and "channels.telegram" in f.section for f in findings)


def test_mcp_server_unknown_key_flagged() -> None:
    cfg = {"mcp": {"servers": {"gh": {"command": "npx", "comand": "oops"}}}}
    findings = validate_config(cfg)
    assert any(f.key == "comand" and f.section == "mcp.servers.gh" for f in findings)


def test_unknown_platform_does_not_crash() -> None:
    cfg = {"channels": {"myplatform": {"enabled": True, "weird_key": 1}}}
    # get_platform raises for an unknown platform; the validator must degrade,
    # not crash — it still validates the generic base keys.
    validate_config(cfg)  # no exception


def test_doctor_reports_config_typo_as_error(tmp_path) -> None:
    from veles.core.doctor import run_all
    from veles.core.project import init_project
    from veles.core.project_config import save_project_config

    project = init_project(tmp_path / "proj", name="t")
    save_project_config(project, {"channels": {"telegram": {"enabled": True, "whitlist": ["@a"]}}})
    report = run_all(project)
    cfg_check = next(r for r in report.results if r.name == "config_schema")
    assert cfg_check.status == "error"
    assert "whitlist" in cfg_check.message
