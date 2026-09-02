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

# Substrings that mark a model as reasoning-first. Deliberately a list of
# families rather than exact ids: ids churn, families do not.
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


def is_reasoning_model(model: str | None) -> bool:
    """True when `model` spends completion budget on a thinking channel."""
    if not model:
        return False
    m = model.lower()
    return any(marker in m for marker in _REASONING_MARKERS)


def default_max_tokens_for(model: str | None) -> int:
    """Completion cap for `model`.

    Reasoning models get a much larger cap because the visible answer is only
    the tail of the budget. Note a `flash`/`mini` variant is NOT exempt: being
    fast per token says nothing about how many thinking tokens it emits, and
    `glm-5.3-flash` is exactly the model that returned an empty answer at 16k.
    """
    return _REASONING_MAX_TOKENS if is_reasoning_model(model) else _DEFAULT_MAX_TOKENS


def request_timeout_for(model: str | None) -> float:
    """HTTP timeout (seconds) for one request to `model`."""
    if not is_reasoning_model(model):
        return _DEFAULT_TIMEOUT_S
    m = (model or "").lower()
    if any(marker in m for marker in _FAST_REASONING_MARKERS):
        return _REASONING_TIMEOUT_S / 2
    return _REASONING_TIMEOUT_S


__all__ = [
    "default_max_tokens_for",
    "is_reasoning_model",
    "request_timeout_for",
]
