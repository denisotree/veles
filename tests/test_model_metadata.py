"""M267: model facts come from OpenRouter's catalogue, and never block a run.

Measured 2026-09-22 against the live endpoint: 442 models, 311 declaring
`reasoning` in `supported_parameters`, 219 of them unrecognised by the substring
family list in `model_budgets`. `deepseek/deepseek-v4-flash` was one, and being
misclassified cost it a 4096-token completion budget against `glm-5.3-flash`'s
32000 — the comparison measured the budget, not the models.

The invariant these tests exist for is the *degradation*: a cold cache with no
network must cost one bounded attempt and then behave exactly as before.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime, timedelta

import pytest

from veles.core import model_metadata

# Shape copied from the live response (trimmed to the fields read).
LIVE_PAYLOAD = {
    "data": [
        {
            "id": "deepseek/deepseek-v4-flash",
            "context_length": 1048576,
            "supported_parameters": ["max_tokens", "reasoning", "reasoning_effort", "tools"],
            # Measured: `mandatory: false`, yet it thinks unprompted (34 of 37
            # completion tokens were reasoning). The catalogue does not answer
            # "thinks by default" — see `is_slow_by_default`.
            "reasoning": {"mandatory": False, "default_effort": "high"},
        },
        {
            "id": "openai/gpt-4o",
            "context_length": 128000,
            "supported_parameters": ["max_tokens", "tools"],
        },
    ]
}


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    model_metadata.reset_for_tests()
    yield
    model_metadata.reset_for_tests()


@pytest.fixture()
def no_network(monkeypatch):
    """Any HTTP call is a test failure unless the test asked for one."""

    def _boom(*args, **kwargs):
        raise AssertionError("the network was touched")

    monkeypatch.setattr(model_metadata.urllib.request, "urlopen", _boom)


def _write_cache(tmp_path, *, age: timedelta = timedelta(0), models=None):
    path = tmp_path / ".veles" / "cache" / "models" / "openrouter.meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": (datetime.now(UTC) - age).isoformat(timespec="seconds"),
                "models": models
                if models is not None
                else {
                    "deepseek/deepseek-v4-flash": {
                        "reasoning": True,
                        "reasoning_mandatory": False,
                        "context_length": 1048576,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class _Resp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_fresh_cache_answers_without_any_network(tmp_path, no_network) -> None:
    _write_cache(tmp_path)
    assert model_metadata.model_facts("deepseek/deepseek-v4-flash")["reasoning"] is True


def test_a_stale_cache_is_a_miss(tmp_path, monkeypatch) -> None:
    _write_cache(tmp_path, age=timedelta(hours=25))
    calls: list = []
    monkeypatch.setattr(
        model_metadata.urllib.request,
        "urlopen",
        lambda *a, **k: calls.append(1) or _Resp(LIVE_PAYLOAD),
    )
    assert model_metadata.model_facts("openai/gpt-4o")["reasoning"] is False
    assert len(calls) == 1


def test_a_corrupt_cache_is_a_miss_not_a_crash(tmp_path, monkeypatch) -> None:
    path = _write_cache(tmp_path)
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(model_metadata.urllib.request, "urlopen", lambda *a, **k: _Resp({}))
    assert model_metadata.model_facts("openai/gpt-4o") is None


def test_no_network_gives_up_quietly(monkeypatch) -> None:
    def _dead(*args, **kwargs):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(model_metadata.urllib.request, "urlopen", _dead)
    assert model_metadata.model_facts("deepseek/deepseek-v4-flash") is None


def test_the_fetch_is_bounded_and_attempted_once(monkeypatch) -> None:
    """The 3s ceiling is the whole licence to do this on a provider build; and a
    machine with no network must pay it once, not on every build."""
    seen: list[float] = []

    def _record(url, timeout=None):
        seen.append(timeout)
        raise TimeoutError("too slow")

    monkeypatch.setattr(model_metadata.urllib.request, "urlopen", _record)
    assert model_metadata.model_facts("openai/gpt-4o") is None
    assert model_metadata.model_facts("deepseek/deepseek-v4-flash") is None
    assert seen == [model_metadata._FETCH_TIMEOUT_S]


def test_a_successful_fetch_is_cached_to_disk(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        model_metadata.urllib.request, "urlopen", lambda *a, **k: _Resp(LIVE_PAYLOAD)
    )
    assert model_metadata.model_facts("deepseek/deepseek-v4-flash")["reasoning"] is True
    payload = json.loads(
        (tmp_path / ".veles" / "cache" / "models" / "openrouter.meta.json").read_text()
    )
    assert payload["models"]["deepseek/deepseek-v4-flash"] == {
        "reasoning": True,
        "reasoning_mandatory": False,
        "context_length": 1048576,
    }


def test_an_unlisted_model_has_no_opinion(tmp_path, no_network) -> None:
    _write_cache(tmp_path)
    assert model_metadata.model_facts("vendor/made-up-9") is None
    assert model_metadata.model_facts(None) is None


def test_a_route_prefixed_id_still_resolves(tmp_path, no_network) -> None:
    _write_cache(tmp_path)
    assert model_metadata.model_facts("openrouter/deepseek/deepseek-v4-flash") is not None


def test_refresh_cache_stores_a_catalogue_someone_else_fetched(tmp_path, no_network) -> None:
    model_metadata.refresh_cache(LIVE_PAYLOAD)
    assert model_metadata.model_facts("openai/gpt-4o")["context_length"] == 128000


# ---- what the facts change for a budget ----


def test_the_reported_damage_is_gone(tmp_path, no_network) -> None:
    """The exact case from the 18.09 comparison: deepseek-v4 ran on 4096 tokens
    because no substring matched it, returned 5 empty verdicts out of 12, and was
    called unfit. The failure was truncation, so the cap is what had to move —
    the timeout stays on the family list (see the test below for why)."""
    from veles.core.model_budgets import default_max_tokens_for

    _write_cache(tmp_path)
    assert default_max_tokens_for("deepseek/deepseek-v4-flash") == 32_000  # was 4096


def test_the_capability_does_not_stretch_the_timeout(tmp_path, no_network) -> None:
    """M267b. `supported_parameters: ["reasoning"]` means "can think if asked",
    and 311 of 442 models declare it — including `claude-sonnet-4.6`, which
    Veles never asks and which measured 0 reasoning tokens unprompted on
    2026-09-22. Keying the timeout on the capability took the project's default
    model from a 120s ceiling to 900s, times two SDK retries: 2700s to fail a
    hung request instead of 360s. A cap is not a spend; a timeout is."""
    from veles.core.model_budgets import default_max_tokens_for, request_timeout_for

    _write_cache(
        tmp_path,
        models={"anthropic/claude-sonnet-4.6": {"reasoning": True, "reasoning_mandatory": False}},
    )
    assert default_max_tokens_for("anthropic/claude-sonnet-4.6") == 32_000
    assert request_timeout_for("anthropic/claude-sonnet-4.6") == 120.0


def test_a_mandatory_thinker_does_get_the_long_timeout(tmp_path, no_network) -> None:
    """`reasoning.mandatory` is the catalogue's own "cannot be asked not to" —
    102 of 442 models, 64 of them invisible to the family list."""
    from veles.core.model_budgets import is_slow_by_default, request_timeout_for

    _write_cache(
        tmp_path, models={"vendor/silent-thinker": {"reasoning": True, "reasoning_mandatory": True}}
    )
    assert is_slow_by_default("vendor/silent-thinker") is True
    assert request_timeout_for("vendor/silent-thinker") == 900.0


def test_the_catalogue_overrules_a_substring_match(tmp_path, no_network) -> None:
    """A name that looks like a family but cannot think must not get the big cap
    — otherwise the list is still in charge of the capability question."""
    from veles.core.model_budgets import is_reasoning_model

    _write_cache(tmp_path, models={"vendor/gpt-5-lite": {"reasoning": False}})
    assert is_reasoning_model("vendor/gpt-5-lite") is False


def test_the_family_list_still_governs_the_timeout_it_was_calibrated_for(
    tmp_path, no_network
) -> None:
    """`glm-5.3-flash` is `mandatory: true`, but the OR must keep the family list
    too: `deepseek-v4-flash` is `mandatory: false` and still thinks unprompted, so
    the catalogue alone would under-budget every such model."""
    from veles.core.model_budgets import request_timeout_for

    _write_cache(
        tmp_path, models={"z-ai/glm-5.3-flash": {"reasoning": True, "reasoning_mandatory": False}}
    )
    assert request_timeout_for("z-ai/glm-5.3-flash") == 450.0  # from the family list


def test_without_facts_every_old_answer_stands(monkeypatch) -> None:
    """The fallback is the contract: offline, `model_budgets` behaves exactly as
    it did before M267 — which is what the whole of test_model_budgets asserts."""

    def _dead(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(model_metadata.urllib.request, "urlopen", _dead)
    from veles.core.model_budgets import is_reasoning_model

    assert is_reasoning_model("z-ai/glm-5.3-flash") is True
    assert is_reasoning_model("deepseek/deepseek-v4-flash") is False  # the old blind spot
    assert is_reasoning_model("openai/gpt-4o") is False


def test_listing_models_warms_the_metadata_cache(tmp_path, monkeypatch) -> None:
    """`/model` and `veles models` already pay for this request — the headless
    run should not have to pay for it again."""
    from veles.adapters.openrouter import OpenRouterProvider

    class _Entry:
        def __init__(self, data):
            self._data = data
            self.id = data["id"]

        def model_dump(self):
            return self._data

    model_metadata.reset_for_tests()
    provider = OpenRouterProvider(api_key="sk-test")
    monkeypatch.setattr(
        type(provider._client.models),
        "list",
        lambda self, **kw: [_Entry(d) for d in LIVE_PAYLOAD["data"]],
    )
    assert provider.list_models() == ["deepseek/deepseek-v4-flash", "openai/gpt-4o"]
    assert model_metadata.model_facts("deepseek/deepseek-v4-flash")["reasoning"] is True
