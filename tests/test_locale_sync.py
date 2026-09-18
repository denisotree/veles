"""CI invariant: a translated doc must not silently fall behind the English one.

**How the gap got here.** M226 added a `[vision]` section to
`reference/configuration.md` and noted "15 other locales still to sync". Nothing
enforced it, so the sync never happened — and every later English edit widened
the same gap. By 2026-09-18 four files had drifted across all 14 locales,
including `how-to/embed-veles-run.md`, which exists only in English. Translations
do not rot on their own; they rot because nothing notices.

**What is checked.** The count of `##`/`###` headings per file. Not the text —
that would be a translation-quality test, which this cannot be — but the
*structure*, which is what "this page documents the same things" reduces to. A
new English section with no counterpart is the exact failure mode, and it is
visible in the count.

`_BASELINE` records the drift that already existed when the lock went in, as
`"<relative path>": <number of locales behind>`. **Counts may shrink, never
grow**: syncing one locale lowers the number, a new unsynced English section
raises it and fails. A file missing from a locale entirely counts as behind.

Untranslated by design is fine — remove the file from `docs/en` or add it here
with a reason. Silence is what is not fine.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parent.parent / "docs"
_EN = _DOCS / "en"
# Working directories, not translations.
_NOT_LOCALES = {"en", "assets", "plans", "audit", "superpowers"}
_HEADING = re.compile(r"^#{2,3} ", re.MULTILINE)

# path -> how many of the 14 locales were behind on 2026-09-18.
# `reference/configuration.md` left this list the same day: all 14 caught up
# with the four sections they were missing (M226 [vision], M250 pinning,
# M257 retention + log rotation).
_BASELINE = {
    "how-to/embed-veles-run.md": 14,  # M233; never translated at all
    "how-to/run-as-daemon.md": 14,  # M234 added the HTTP section
    "reference/cli.md": 14,
}


def _locales() -> list[str]:
    return sorted(d.name for d in _DOCS.iterdir() if d.is_dir() and d.name not in _NOT_LOCALES)


def _heading_count(path: Path) -> int:
    return len(_HEADING.findall(path.read_text(encoding="utf-8")))


def locale_drift() -> dict[str, list[str]]:
    """relative path -> locales whose structure differs from English (or which
    lack the file). Exposed so the same scan can be run while syncing."""
    out: dict[str, list[str]] = {}
    locales = _locales()
    for english in sorted(_EN.rglob("*.md")):
        rel = english.relative_to(_EN)
        expected = _heading_count(english)
        behind = [
            loc
            for loc in locales
            if not (_DOCS / loc / rel).exists() or _heading_count(_DOCS / loc / rel) != expected
        ]
        if behind:
            out[str(rel)] = behind
    return out


def test_locales_do_not_fall_further_behind() -> None:
    drift = locale_drift()
    worse = {
        path: f"{len(locs)} locales behind (baseline {_BASELINE.get(path, 0)}): " + ", ".join(locs)
        for path, locs in drift.items()
        if len(locs) > _BASELINE.get(path, 0)
    }
    assert not worse, (
        "English docs gained structure these translations did not:\n"
        + "\n".join(f"  {p}: {why}" for p, why in sorted(worse.items()))
        + "\n\nTranslate the new section, or raise the baseline with a reason."
    )


def test_baseline_shrinks_as_locales_are_synced() -> None:
    """A baseline entry that overstates the gap is a licence to drift back to
    it. Lower the number when a locale is caught up."""
    drift = locale_drift()
    stale = {
        path: (recorded, len(drift.get(path, [])))
        for path, recorded in _BASELINE.items()
        if len(drift.get(path, [])) < recorded
    }
    assert not stale, (
        "These are now better than the baseline claims — lower it so the gap "
        "cannot silently reopen: "
        + ", ".join(f"{p}: {was} -> {now}" for p, (was, now) in sorted(stale.items()))
    )


def test_every_locale_is_actually_checked() -> None:
    """Guards the filter above: if `_NOT_LOCALES` ever swallowed a real
    language, the lock would pass by checking nothing."""
    locales = _locales()
    assert len(locales) == 14, f"expected 14 translations, found {len(locales)}: {locales}"
    assert "ru" in locales and "ja" in locales and "zh-CN" in locales
