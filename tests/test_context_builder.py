"""Tests for core/context_builder.py — Tier ε M67 cache invariant."""

from __future__ import annotations

from veles.core.cache_hints import CACHE_BREAKPOINT_SENTINEL
from veles.core.context_builder import (
    DEFAULT_SEPARATOR,
    assemble_system_prompt,
    stable_text,
)
from veles.core.tools.registry import Registry, ToolEntry
from veles.core.trace import hash_text, hash_tools

# ---------- assemble_system_prompt ----------


def test_no_parts_returns_none() -> None:
    prompt, stable = assemble_system_prompt([], [])
    assert prompt is None
    assert stable == ""


def test_stable_only_no_breakpoint() -> None:
    """Stable-only prompt doesn't need a sentinel — there's nothing volatile
    to mark a boundary against."""
    prompt, stable = assemble_system_prompt(["alpha", "beta"], [])
    assert prompt == "alpha" + DEFAULT_SEPARATOR + "beta"
    assert stable == prompt
    assert CACHE_BREAKPOINT_SENTINEL not in prompt


def test_volatile_only_returns_unchanged() -> None:
    """No stable portion → no cache to protect; pass volatile through."""
    prompt, stable = assemble_system_prompt([], ["dynamic"])
    assert prompt == "dynamic"
    assert stable == ""


def test_both_parts_inject_breakpoint_between() -> None:
    prompt, stable = assemble_system_prompt(["AGENTS.md content"], ["memory-block"])
    assert prompt is not None
    assert CACHE_BREAKPOINT_SENTINEL in prompt
    # Stable text appears before the sentinel, volatile after.
    before, _, after = prompt.partition(CACHE_BREAKPOINT_SENTINEL)
    assert "AGENTS.md content" in before
    assert "memory-block" in after
    assert stable == "AGENTS.md content"


def test_falsy_entries_filtered() -> None:
    prompt, stable = assemble_system_prompt(
        ["", "stable", None, ""],  # type: ignore[list-item]
        ["", "vol"],
    )
    assert "stable" in (prompt or "")
    assert "vol" in (prompt or "")
    assert stable == "stable"


def test_stable_hash_invariant_under_volatile_change() -> None:
    """Cache invariant: same stable_parts -> same hash, regardless of
    volatile changes. This is the property M68 relies on to detect drift."""
    _, stable_a = assemble_system_prompt(["S1", "S2"], ["V_alpha"])
    _, stable_b = assemble_system_prompt(["S1", "S2"], ["V_beta"])
    assert hash_text(stable_a) == hash_text(stable_b)


def test_stable_text_helper() -> None:
    assert stable_text(["a", "b"]) == "a" + DEFAULT_SEPARATOR + "b"
    assert stable_text([]) == ""
    assert stable_text(["", "x"]) == "x"


# ---------- deterministic Registry.list_schemas ----------


def test_list_schemas_sorted_by_name() -> None:
    """Tool bundle is part of the cache prefix. Insertion order must NOT
    leak into the wire-format; we sort alphabetically."""
    reg = Registry()
    for n in ["zebra", "alpha", "mango", "banana"]:
        reg.register(
            ToolEntry(
                name=n,
                description="d",
                parameter_schema={"type": "object"},
                handler=lambda: "",
                is_async=False,
            )
        )
    names = [s["function"]["name"] for s in reg.list_schemas()]
    assert names == ["alpha", "banana", "mango", "zebra"]


def test_list_schemas_stable_across_two_orderings() -> None:
    """Two registries with the same tools in different insertion orders
    must emit identical bundle hashes via M68 hash_tools."""
    reg_a = Registry()
    reg_b = Registry()
    pairs = [("x", "X-doc"), ("y", "Y-doc"), ("z", "Z-doc")]
    for n, d in pairs:
        reg_a.register(
            ToolEntry(
                name=n,
                description=d,
                parameter_schema={"type": "object"},
                handler=lambda: "",
                is_async=False,
            )
        )
    for n, d in reversed(pairs):
        reg_b.register(
            ToolEntry(
                name=n,
                description=d,
                parameter_schema={"type": "object"},
                handler=lambda: "",
                is_async=False,
            )
        )
    assert hash_tools(reg_a.list_schemas()) == hash_tools(reg_b.list_schemas())
