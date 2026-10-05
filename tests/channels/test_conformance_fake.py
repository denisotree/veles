"""The channel checks a module-channel's own tests call (`veles.sdk.channel_checks`),
run on the test platform."""

from __future__ import annotations

import pytest

from tests.channels.fake_platform import FAKE_SPEC
from veles.sdk.channel_checks import (
    PROBE_TEXT,
    check_builds_from_config,
    check_config_keys,
    check_delivers,
)


async def test_fake_platform_passes_the_channel_checks(tmp_path) -> None:
    gw = check_builds_from_config(
        FAKE_SPEC, config={"room": "r"}, secrets={"token": "t"}, session_dir=tmp_path
    )
    check_config_keys(FAKE_SPEC, {"enabled": True, "room": "r", "token": "t"})
    await check_delivers(gw, "42")
    assert gw.sent == [("42", PROBE_TEXT)]


def test_an_undeclared_config_key_fails_the_check() -> None:
    with pytest.raises(AssertionError, match="rooom"):
        check_config_keys(FAKE_SPEC, {"enabled": True, "rooom": "r"})


def test_the_checks_do_not_import_pytest() -> None:
    """`veles.sdk` imports every submodule in a running Veles, without pytest."""
    import ast
    from pathlib import Path

    import veles.sdk.channel_checks as checks

    tree = ast.parse(Path(checks.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in getattr(node, "names", [])
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name and name.startswith("pytest") for name in imported)
