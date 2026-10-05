"""The platform lookup is a view over `platform` contributions."""

from __future__ import annotations

import pytest

from tests.channels.fake_platform import FAKE_SPEC, contributing
from veles.core.contributions import CONTRIBUTION_POINTS
from veles.core.platforms import get_platform, list_platforms


def test_platform_is_a_point() -> None:
    assert "platform" in CONTRIBUTION_POINTS


def test_lookup_reads_contributions() -> None:
    with contributing({"slackish": FAKE_SPEC}):
        assert "slackish" in list_platforms()
        assert get_platform("slackish").caps.asks_questions
        with pytest.raises(KeyError, match="slackish"):
            get_platform("nope")
    assert "slackish" not in list_platforms()


def test_a_non_spec_platform_is_refused_at_load() -> None:
    from veles.core.modules import ModuleAPI, ModuleRegistry

    with pytest.raises(ValueError):
        ModuleAPI(ModuleRegistry(), "m").contribute("platform", "x", object())


def test_telegram_is_contributed_by_its_builtin_module() -> None:
    # Until it moves to the registry (release C, Task 13).
    assert "telegram" in list_platforms()
