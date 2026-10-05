"""The Telegram channel imports Veles only through `veles.sdk` — the rule
`veles registry validate` applies to it once it ships from the registry
(release C). Temporary: the registry's own validation replaces this test when
the package leaves core."""

from __future__ import annotations

from pathlib import Path

from veles.core.registry.scan import non_sdk_imports

_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "veles" / "channels" / "telegram"


def test_telegram_imports_veles_only_through_the_sdk() -> None:
    assert non_sdk_imports(_PACKAGE) == []
