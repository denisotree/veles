"""Add-channel wizard (M137) — interactive `veles channel add`.

Reuses the universal `Prompter` abstraction from `cli/wizard.py` (VISION §7): no
new question machinery. A platform's `cred_fields` descriptor
(`channels/platform_registry.py`) drives the prompts, so adding a new channel
type needs zero wizard code — register the platform with its fields and the
wizard handles it. Secrets go to the keychain (`core/secrets.set_provider_key`);
non-secret fields land in the channel's config block — global `[channels.<type>]`
for the unnamed daemon, or `[daemon.<name>.channels.<type>]` for a named session.
"""

from __future__ import annotations

from veles.cli.wizard import Prompter, _default_prompter, _wizard_prompter
from veles.core.project_config import (
    list_daemon_session_names,
    load_project_config,
    save_project_config,
)

_DEFAULT_LABEL = "(default daemon)"


def _resolve_prompter(prompter: Prompter | None) -> Prompter:
    return prompter or _wizard_prompter.get() or _default_prompter


def _channel_block(cfg: dict, session: str | None, channel: str) -> dict:
    """Return (creating parents) the dict for this channel's config block."""
    if session:
        daemon = cfg.setdefault("daemon", {})
        if not isinstance(daemon, dict):
            daemon = cfg["daemon"] = {}
        sess = daemon.setdefault(session, {})
        if not isinstance(sess, dict):
            sess = daemon[session] = {}
        channels = sess.setdefault("channels", {})
        if not isinstance(channels, dict):
            channels = sess["channels"] = {}
    else:
        channels = cfg.setdefault("channels", {})
        if not isinstance(channels, dict):
            channels = cfg["channels"] = {}
    block = channels.setdefault(channel, {})
    if not isinstance(block, dict):
        block = channels[channel] = {}
    return block


def add_channel(
    project,
    *,
    session: str | None = None,
    channel: str | None = None,
    prompter: Prompter | None = None,
) -> int:
    """Run the add-channel flow. Returns a CLI exit code.

    `session`/`channel` pre-fill the corresponding wizard steps when given;
    otherwise the user is asked. Creds are always collected via the prompter so
    secrets never land in argv/history."""
    from veles.channels.platform_registry import (
        ensure_builtins_registered,
        get_platform,
        list_platforms,
    )
    from veles.cli.wizard import _ask_choice

    ensure_builtins_registered()
    ask = _resolve_prompter(prompter)
    cfg = load_project_config(project)

    # 1. daemon session (only ask when named sessions exist).
    if session is None:
        names = list_daemon_session_names(cfg)
        if names:
            choice = _ask_choice(
                ask,
                "Attach channel to which daemon session",
                (_DEFAULT_LABEL, *names),
                default=_DEFAULT_LABEL,
            )
            session = None if choice == _DEFAULT_LABEL else choice

    # 2. channel type.
    platforms = tuple(list_platforms())
    if not platforms:
        print("error: no channel platforms registered.")
        return 1
    if channel is None:
        channel = _ask_choice(
            ask, "Channel type", platforms, default=platforms[0]
        )
    try:
        entry = get_platform(channel)
    except KeyError as exc:
        print(f"error: {exc}")
        return 2

    # 3. collect creds → secrets (keychain) + config fields (config block).
    collected = collect_channel_fields(entry, ask)
    if collected is None:
        print("error: a required field was left blank.")
        return 2
    secrets, config_fields = collected
    apply_channel(
        project, session=session, channel=channel, secrets=secrets, config_fields=config_fields
    )

    where = f"[daemon.{session}.channels.{channel}]" if session else f"[channels.{channel}]"
    scope = f"daemon session {session!r}" if session else "the default daemon"
    print(f"added {channel} channel to {scope} ({where} in config.toml).")
    print("Restart the daemon to pick it up: `veles daemon restart" + (f" --name {session}`" if session else "`"))
    return 0


def collect_channel_fields(entry, ask: Prompter):
    """Drive `entry.cred_fields` through `ask` (a `(prompt, default) -> str`
    prompter). Returns `(secrets, config_fields)` — secrets keyed by field for
    the keychain, config_fields for the channel block — or None when a required
    field was left blank. Shared by the CLI wizard and the TUI flow (the TUI
    collects via modal screens and calls `apply_channel` directly)."""
    secrets: dict[str, str] = {}
    config_fields: dict[str, object] = {}
    for field in entry.cred_fields:
        raw = (ask(field.label, None) or "").strip()
        if not raw:
            if field.required:
                return None
            continue
        if field.secret:
            secrets[field.key] = raw
        elif field.list_value:
            config_fields[field.key] = [x.strip() for x in raw.split(",") if x.strip()]
        else:
            config_fields[field.key] = raw
    return secrets, config_fields


def apply_channel(
    project,
    *,
    session: str | None,
    channel: str,
    secrets: dict[str, str],
    config_fields: dict[str, object],
) -> None:
    """Persist a collected channel binding: secret values to the keychain
    (`set_provider_key(channel, …)`), non-secret fields + `enabled=true` to the
    config block (global `[channels.<type>]` or per-session
    `[daemon.<name>.channels.<type>]`). Pure of any prompting — reusable from
    the CLI wizard and the TUI.

    Keychain writes happen FIRST: if a secret write fails (e.g. no keychain
    backend) we abort before persisting `enabled=true`, so we never leave a
    tokenless-but-enabled block the daemon would warn-and-skip on startup."""
    from veles.core.secrets import set_provider_key

    for value in secrets.values():
        set_provider_key(channel, value, project=project.name)
    cfg = load_project_config(project)
    block = _channel_block(cfg, session, channel)
    for key, value in config_fields.items():
        block[key] = value
    block["enabled"] = True
    save_project_config(project, cfg)


def delete_channel_block(project, channel: str, *, session: str | None = None) -> bool:
    """Drop a channel's config block (no I/O of its own — reusable from the
    TUI). Returns True if a block was removed, False if absent. The keychain
    secret is left in place so a re-add doesn't force re-entering the token."""
    cfg = load_project_config(project)
    if session:
        channels = (
            cfg.get("daemon", {}).get(session, {}).get("channels", {})
            if isinstance(cfg.get("daemon"), dict)
            else {}
        )
    else:
        channels = cfg.get("channels", {})
    if not isinstance(channels, dict) or channel not in channels:
        return False
    del channels[channel]
    save_project_config(project, cfg)
    return True


def remove_channel(project, channel: str, *, session: str | None = None) -> int:
    """CLI wrapper over `delete_channel_block` — returns an exit code + prints."""
    scope = f"daemon session {session!r}" if session else "the default daemon"
    if not delete_channel_block(project, channel, session=session):
        print(f"error: no {channel} channel configured for {scope}.")
        return 1
    print(f"removed {channel} channel from {scope}.")
    return 0
