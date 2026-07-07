"""Shared async channel-add modal flow (M172).

A single registry-driven channel collector reused by every Textual
channel-setup entry point — the `veles daemon` picker (key `c`,
`screens/daemon_picker.py`) and the project wizard's daemon/channel step
(`veles daemon start` in a fresh dir, `wizard/project_steps.py`). It mirrors
the synchronous `collect_channel_fields` in `cli/channel_wizard.py`: same
platform registry, same `CredField` labels, same `(secrets, config_fields)`
shape feeding `apply_channel`. So all four channel-setup flows (`channel add`,
picker, stdin wizard, TUI wizard) stay in lockstep — adding a channel platform
needs zero wizard code, only a `platform_registry` entry.

The channel-type `ChoiceScreen` is ALWAYS shown, even with a single registered
platform: the "pick a type, then configure it" shape is the point — it is the
visible extension seam, not an optimisation to skip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

CollectResult = tuple[str, dict[str, str], dict[str, object]]
"""`(channel, secrets, config_fields)` — ready to hand straight to
`cli.channel_wizard.apply_channel`."""


async def collect_channel_via_modals(app: App, *, title: str) -> CollectResult | None:
    """Pick a channel type from the platform registry, then drive its
    `cred_fields` through modal `InputScreen`s.

    Returns `(channel, secrets, config_fields)` or `None` when the user
    cancels at any screen or leaves a required field blank. Secrets (the
    `secret=True` creds) are kept apart from plain config fields so the caller
    can route them to the keychain vs the config block via `apply_channel`.
    """
    from veles.channels.platform_registry import (
        ensure_builtins_registered,
        get_platform,
        list_platforms,
    )
    from veles.tui.wizard.screens.choice import ChoiceItem, ChoiceScreen
    from veles.tui.wizard.screens.input import InputScreen
    from veles.tui.wizard.step import CANCEL_SENTINEL

    ensure_builtins_registered()
    platforms = list_platforms()
    if not platforms:
        return None
    channel = await app.push_screen_wait(
        ChoiceScreen(
            title,
            [ChoiceItem(p, p) for p in platforms],
            default=platforms[0],
        )
    )
    if not channel or channel == CANCEL_SENTINEL:
        return None
    entry = get_platform(channel)
    secrets: dict[str, str] = {}
    config_fields: dict[str, object] = {}
    for cred in entry.cred_fields:
        value = await app.push_screen_wait(
            InputScreen(f"{channel}: {cred.label}", password=cred.secret)
        )
        if value == CANCEL_SENTINEL:
            return None
        value = (value or "").strip()
        if not value:
            if cred.required:
                return None
            continue
        if cred.secret:
            secrets[cred.key] = value
        elif cred.list_value:
            config_fields[cred.key] = [x.strip() for x in value.split(",") if x.strip()]
        else:
            config_fields[cred.key] = value
    return channel, secrets, config_fields
