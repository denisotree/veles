"""Atomic rules: LiteralRule, RegexRule, RuleSet."""

from __future__ import annotations

from veles.core.sanitize.rule import LiteralRule, RegexRule, RuleSet


def test_literal_rule_replaces_all_occurrences() -> None:
    r = LiteralRule(name="t", pattern="cat", replacement="<animal>")
    assert r.apply("cat saw cat") == "<animal> saw <animal>"


def test_literal_rule_noop_on_empty_input() -> None:
    r = LiteralRule(name="t", pattern="x", replacement="y")
    assert r.apply("") == ""


def test_literal_rule_noop_on_empty_pattern() -> None:
    """Empty pattern would `str.replace('', 'y')` insert between every
    character — we explicitly guard against that."""
    r = LiteralRule(name="t", pattern="", replacement="y")
    assert r.apply("hello") == "hello"


def test_literal_rule_idempotent_when_replacement_excludes_pattern() -> None:
    r = LiteralRule(name="t", pattern="/Users/foo", replacement="<home>")
    once = r.apply("path: /Users/foo/x")
    twice = r.apply(once)
    assert once == twice == "path: <home>/x"


def test_regex_rule_substitutes_matches() -> None:
    r = RegexRule.build("t", r"\bsk-[A-Za-z0-9]{32,}\b", "sk-<redacted>")
    assert r is not None
    s = "key=sk-" + "a" * 40 + " trailing"
    assert r.apply(s) == "key=sk-<redacted> trailing"


def test_regex_rule_build_returns_none_on_bad_pattern() -> None:
    """A broken regex must not crash sanitize calls — the rule is
    dropped and the rest of the set continues to apply."""
    bad = RegexRule.build("t", r"(unclosed", "x")
    assert bad is None


def test_regex_rule_noop_on_empty_input() -> None:
    r = RegexRule.build("t", r".+", "X")
    assert r is not None
    assert r.apply("") == ""


def test_ruleset_applies_in_order() -> None:
    rs = RuleSet(
        [
            LiteralRule(name="a", pattern="cat", replacement="dog"),
            LiteralRule(name="b", pattern="dog", replacement="wolf"),
        ]
    )
    # The two rules chain: cat → dog → wolf.
    assert rs.apply("cat") == "wolf"


def test_ruleset_skips_when_text_empty() -> None:
    rs = RuleSet([LiteralRule(name="a", pattern="x", replacement="y")])
    assert rs.apply("") == ""


def test_ruleset_len_and_iter() -> None:
    rules = [
        LiteralRule(name=f"r{i}", pattern=str(i), replacement=str(i + 1))
        for i in range(3)
    ]
    rs = RuleSet(rules)
    assert len(rs) == 3
    assert [r.name for r in rs] == ["r0", "r1", "r2"]
