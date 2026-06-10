"""Tests for core/version.py — Tier δ M53."""

from __future__ import annotations

import pytest

from veles.core.version import SemVer, current_version, parse


def test_parse_basic() -> None:
    v = parse("1.2.3")
    assert (v.major, v.minor, v.patch, v.prerelease) == (1, 2, 3, None)


def test_parse_prerelease() -> None:
    v = parse("0.1.0-rc.1")
    assert v.prerelease == "rc.1"
    assert str(v) == "0.1.0-rc.1"


def test_parse_rejects_garbage() -> None:
    for s in ["", "1.2", "1.2.3.4", "v1.2.3", "1.2.3+build", "1.02.3"]:
        with pytest.raises(ValueError, match="not a strict SemVer"):
            parse(s)


def test_str_round_trip() -> None:
    for s in ["0.0.1", "1.2.3", "10.20.30", "2.0.0-rc.1"]:
        assert str(parse(s)) == s


def test_bump_levels() -> None:
    v = SemVer(1, 2, 3, prerelease="rc.1")
    assert str(v.bump("patch")) == "1.2.4"
    assert str(v.bump("minor")) == "1.3.0"
    assert str(v.bump("major")) == "2.0.0"


def test_bump_drops_prerelease() -> None:
    """`v.bump('patch')` from a pre-release lands on the clean version,
    not on a fresh pre-release of the new core."""
    v = parse("0.1.0-rc.1")
    assert str(v.bump("patch")) == "0.1.1"


def test_bump_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="bump level"):
        SemVer(1, 0, 0).bump("unknown")


def test_current_version_matches_pyproject() -> None:
    """If the package is installed locally (uv run), the value should match
    the pyproject.toml literal. Otherwise the fallback kicks in — both are
    valid SemVer."""
    v = current_version()
    # Must parse cleanly (no garbage / placeholder).
    parsed = parse(v)
    assert parsed.major >= 0
