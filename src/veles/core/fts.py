"""Build FTS5 MATCH expressions from free text (M230).

Shared by every full-text search surface — `core/memory` (turns + insights) and
the optional wiki engine (`modules/wiki`). It lives in its own module rather
than in `core/memory` so the wiki engine, which is a *pluggable module* and
otherwise has no reason to know about the memory subsystem, can reuse it without
importing one.

The rule the whole module exists for: **short queries AND, long queries OR.**
Recall is keyed on the raw user prompt, and FTS5's implicit operator between
quoted phrases is AND — so ANDing every token of a paragraph demands that one
stored row contain all of them. Volatile tokens (timestamps, ids, metric values)
guarantee that never happens, and the failure is invisible: an empty result set,
no block injected, nothing logged.
"""

from __future__ import annotations

import re

# Above this many indexable words a query is prose, not a keyword lookup.
_AND_MAX_WORDS = 4
# Cap on the OR fan-out, so a pasted wall of text can't become a 500-term MATCH.
_MAX_OR_TERMS = 8
_MIN_WORD_LEN = 3

# Words carrying no retrieval signal, in both languages the project is used in.
#
# The interrogatives and modals matter more than they look. Under OR, a word
# present in a large share of stored rows matches nearly everything, so a
# question sharing no *topic* with anything stored ("how do I configure
# quaternion interpolation…") would match purely on "how" — trading the old
# silent-empty failure for a worse one, since an injected memory block reads to
# the model as relevant while an absent one says nothing.
_STOPWORDS_EN = (
    "a an the this that these those is are was were be been being do does did "
    "of for to in on at by with from and or not no if then than as it its "
    "how what when where why which who whom whose "
    "can could should would will shall may might must "
    "i me my we us our you your it he she they them their there here "
    "about into over under between after before "
)
# Bilingual site — targeted noqa per line, per the convention in pyproject's
# `allowed-confusables` note. Without these a Russian prompt spends its OR budget
# on "что" / "когда" / "только".
_STOPWORDS_RU = (
    "и в во не что он на я с со как а то все она так его но да ты к у же вы за бы "  # noqa: RUF001
    "по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг "  # noqa: RUF001
    "ли если или быть был него до вас нибудь опять уж вам"
)
STOPWORDS = frozenset(_STOPWORDS_EN.split()) | frozenset(_STOPWORDS_RU.split())

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _quote(term: str) -> str:
    """Quote one term for FTS5, doubling any embedded quote per its grammar."""
    return '"' + term.replace('"', '""') + '"'


def escape_query(query: str) -> str:
    """Return an FTS5 MATCH expression for `query`, or '' when it is blank.

    Short queries keep strict AND — the right semantics for a keyword lookup,
    and the pre-M230 behaviour, so nothing about existing search changes.

    Long queries switch to OR, ranked by bm25. Pruning noise alone does not fix
    the AND failure (measured: even after dropping numbers and stopwords the
    surviving content words are rarely all present in one row), so the operator
    has to change. Since the AND path returned *nothing* for these queries,
    ranked OR cannot regress relevance — but the stopword list has to be good
    enough that a topically unrelated query still comes back empty rather than
    matching on function words. Callers additionally cap with `limit`.
    """
    tokens = query.split()
    if not tokens:
        return ""

    # Count what FTS will actually index, not whitespace runs: a compact JSON
    # blob is one whitespace token but a dozen indexed words.
    words = _WORD_RE.findall(query)
    if len(words) <= _AND_MAX_WORDS:
        return " ".join(_quote(t) for t in tokens)

    seen: set[str] = set()
    distinctive: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in seen or lowered in STOPWORDS:
            continue
        if len(word) < _MIN_WORD_LEN:
            continue
        # Mostly-digit tokens are ids, metric values and timestamp fragments
        # ("87", "17T10", "00Z") — they never recur across runs, so they would
        # spend the OR budget on terms that cannot match anything.
        if sum(c.isdigit() for c in word) * 2 >= len(word):
            continue
        seen.add(lowered)
        distinctive.append(word)
    # Longer words are the cheap proxy for "more distinctive" without corpus stats.
    distinctive.sort(key=len, reverse=True)
    terms = distinctive[:_MAX_OR_TERMS] or words[:_MAX_OR_TERMS]
    return " OR ".join(_quote(t) for t in terms)


__all__ = ["STOPWORDS", "escape_query"]
