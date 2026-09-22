"""Per-model response budgets: how long to wait, how much to let it write (M247).

Sibling of `model_windows.py`, which answers "how big is the *input* window?".
This answers the two output-side questions that were previously fixed constants
and wrong for a whole class of models:

  - `request_timeout_for(model)` — the HTTP timeout. Was a flat 120s in
    `adapters/openrouter.py`.
  - `default_max_tokens_for(model)` — the completion cap. Was a flat 4096 in
    `Agent.__init__`, and nothing on the interactive paths ever overrode it.

**Why a flat budget is wrong.** A reasoning model spends its completion budget
on a hidden thinking channel before it writes a single visible character, and
it is slow while doing so. Both constants broke on `z-ai/glm-5.3-flash`
(2026-09-02):

  - at `max_tokens=4096`/16000 it returned `completion == max_tokens` with an
    EMPTY `content` — the whole budget went to reasoning. Empty text means
    GoalMode never sees its `<ready>` marker, so INTERVIEW looped, burning the
    full budget every turn, and the failure read as "the model is being dumb"
    rather than "we truncated it";
  - at 120s the per-chunk read timeout fired mid-stream and killed a 2.7-hour
    research run.

The economics also differ, which is the point the flat constant hides: a strong
reasoning model thinks for a long time and gets there in one pass, while a
weaker model burns *more* tokens overall by producing a mediocre answer and
iterating on it. Budgeting them identically penalises the model that is
actually cheaper per finished task.

Same best-effort substring matching as `model_windows` — adapter metadata is
not uniform across providers, and an unknown model gets the conservative
non-reasoning defaults.
"""

from __future__ import annotations

# Non-reasoning defaults — what the old constants were, kept as the floor.
_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_TIMEOUT_S = 120.0

# Reasoning defaults. The completion cap has to cover thinking *plus* the
# answer, and the timeout has to cover generating all of it.
_REASONING_MAX_TOKENS = 32_000
_REASONING_TIMEOUT_S = 900.0

# Substrings that mark a model as reasoning-first — the FALLBACK since M267,
# not the answer. Measured against OpenRouter's catalogue on 2026-09-22: of 442
# models, 311 declare `reasoning` and this list recognises 92 of them. The 219
# it misses included `deepseek-v4`, which was therefore budgeted at 4096 tokens
# against `glm-5.3-flash`'s 32000 and written off as unfit when it was truncated.
# Still the right fallback: it needs no network, and it answers for ids the
# catalogue does not carry (local backends, private routes, brand-new models).
_REASONING_MARKERS = (
    "glm-5",
    "glm-4.7",
    "deepseek-r",
    "qwen3.8",
    "qwen3.5",
    "-thinking",
    "o1-",
    "o3-",
    "o4-",
    "gpt-5",
    "magistral",
    "qwq",
)

# Families that stream reasoning but stay brisk; they do not need the long
# timeout even though they match a marker above.
_FAST_REASONING_MARKERS = ("flash", "mini", "turbo")


def _matches_family(model: str) -> bool:
    m = model.lower()
    return any(marker in m for marker in _REASONING_MARKERS)


def is_reasoning_model(model: str | None) -> bool:
    """True when `model` *can* spend completion budget on a thinking channel.

    Asks the provider's own catalogue first (M267) and falls back to the family
    substrings when it has no answer — offline, or a model it does not list.

    This is the capability, which is the right question for a completion cap and
    the wrong one for a timeout — see `request_timeout_for`."""
    if not model:
        return False
    from veles.core.model_metadata import model_facts

    facts = model_facts(model)
    if facts is not None:
        return bool(facts["reasoning"])
    return _matches_family(model)


def default_max_tokens_for(model: str | None) -> int:
    """Completion cap for `model`.

    Reasoning models get a much larger cap because the visible answer is only
    the tail of the budget. Note a `flash`/`mini` variant is NOT exempt: being
    fast per token says nothing about how many thinking tokens it emits, and
    `glm-5.3-flash` is exactly the model that returned an empty answer at 16k.

    Keyed on the *capability* (`is_reasoning_model`) rather than on "thinks by
    default": a cap is not a spend, so over-capping a model that stays quiet
    costs nothing, while under-capping one that thinks truncates its answer —
    which is the whole reported failure. The asymmetry runs the other way for
    the timeout, which is why the two are keyed differently.
    """
    return _REASONING_MAX_TOKENS if is_reasoning_model(model) else _DEFAULT_MAX_TOKENS


def is_slow_by_default(model: str | None) -> bool:
    """True when `model` thinks whether it is asked to or not.

    A *different* question from `is_reasoning_model`, and M267b exists because
    conflating them was a regression. `supported_parameters: ["reasoning"]` says
    the model can think *if asked*; 311 of 442 models declare it, including
    `anthropic/claude-sonnet-4.6`, which Veles never asks — measured unprompted
    on 2026-09-22 it spent 5 completion tokens and **0** reasoning tokens, while
    `deepseek/deepseek-v4-flash` on the same question spent 37 of which **34**
    were reasoning. Budgeting the first as a slow thinker would have taken the
    project's default model from a 120s ceiling to 900s — times the SDK's two
    retries, 2700s to fail a hung request instead of 360s.

    The catalogue's `reasoning.mandatory` marks the models that cannot be asked
    not to (102 of 442, 64 of them invisible to the family list). It is a subset,
    not a replacement: `deepseek-v4-flash` is `mandatory: false` and still thinks
    unprompted, so the family list stays in the OR."""
    if not model:
        return False
    from veles.core.model_metadata import model_facts

    facts = model_facts(model)
    if facts is not None and facts.get("reasoning_mandatory"):
        return True
    return _matches_family(model)


def request_timeout_for(model: str | None) -> float:
    """HTTP timeout (seconds) for one request to `model`.

    Keyed on `is_slow_by_default`, not on the capability: a timeout is a failure
    *ceiling*, and setting it high for a model that answers in two seconds only
    buys a longer hang. The completion cap is the opposite — see
    `default_max_tokens_for`."""
    if not is_slow_by_default(model):
        return _DEFAULT_TIMEOUT_S
    m = (model or "").lower()
    if any(marker in m for marker in _FAST_REASONING_MARKERS):
        return _REASONING_TIMEOUT_S / 2
    return _REASONING_TIMEOUT_S


# ---- project overrides (M266) ----
#
# The name is a bad source for a timeout *in principle*: it names a family,
# while the response time is set by the backend serving it, which the family
# does not own — `glm-5.3-flash` runs at 33 tok/s on one backend and 0.8 tok/s
# on another, a forty-fold spread behind one id. So the derived number above is
# a default, not an answer, and a project must be able to say otherwise.
#
# `request_timeout_for("z-ai/glm-5.3-flash")` is 450s, and the SDK retries twice
# by default — up to 1350s on a single turn, inside an investigation budgeted at
# 900s. Nothing could override either: `[engine.request.<provider>]` (M250) goes
# into the request *body*, while both of these are client parameters.
#
#     [engine]
#     request_timeout_s = 180
#     max_retries = 1
#
# Read here rather than in the adapter so the rule for where a budget comes from
# lives in one module. Only the OpenRouter adapter takes these today — the
# Anthropic/OpenAI/Gemini clients are built without either parameter, and the
# keys are ignored there.


def _engine_section() -> dict[str, object]:
    """`[engine]` of the active project's config, or `{}` outside a project."""
    from veles.core.context import current_project
    from veles.core.project_config import get_section, load_project_config

    project = current_project()
    if project is None:
        return {}
    return get_section(load_project_config(project), "engine")


def _config_error(key: str, value: object, expected: str) -> Exception:
    from veles.core.config_schema import ConfigError
    from veles.core.context import current_project
    from veles.core.project_config import project_config_path

    project = current_project()
    assert project is not None  # only reached from inside `_engine_section`'s project
    return ConfigError(
        f"[engine] {key} = {value!r} is not {expected}.",
        path=project_config_path(project),
    )


def resolve_request_timeout(model: str | None, *, explicit: float | None = None) -> float:
    """Seconds to wait for one request: explicit → `[engine]` → per-model default.

    Raises `ConfigError` on a non-positive or non-numeric `request_timeout_s`.
    A bad *value* is caught here rather than in `config_schema`, whose finding
    shape is "unknown key"; this runs on every provider build, which is loud
    enough — the cost is that `veles doctor` flags a misspelt key but not a
    nonsense value."""
    if explicit is not None:
        return explicit
    raw = _engine_section().get("request_timeout_s")
    if raw is None:
        return request_timeout_for(model)
    if isinstance(raw, bool) or not isinstance(raw, int | float) or raw <= 0:
        raise _config_error("request_timeout_s", raw, "a positive number of seconds")
    return float(raw)


def resolve_max_retries(*, explicit: int | None = None) -> int | None:
    """Retries per request: explicit → `[engine]` → None (the SDK's own default).

    None rather than a number on the miss, so an unconfigured project keeps the
    SDK default byte for byte instead of freezing today's value into Veles."""
    if explicit is not None:
        return explicit
    raw = _engine_section().get("max_retries")
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise _config_error("max_retries", raw, "a non-negative integer")
    return raw


__all__ = [
    "default_max_tokens_for",
    "is_reasoning_model",
    "is_slow_by_default",
    "request_timeout_for",
    "resolve_max_retries",
    "resolve_request_timeout",
]
