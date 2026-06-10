"""Registry mechanics — registration, dispatch, aliases, unknowns.

Tests are pure: no Project, no SessionStore, no Textual. They exercise
`SlashRegistry` itself with synthetic handlers so failures here point to
the framework, not to any individual command."""

from __future__ import annotations

from veles.tui.slash.registry import SlashContext, SlashRegistry, SlashResult


def _ctx() -> SlashContext:
    # Dispatch never touches these in the registry layer; the typed
    # `None`s are fine because no handler in this file reads them.
    return SlashContext(state=None, project=None, store=None)  # type: ignore[arg-type]


def test_dispatch_routes_to_handler_and_strips_command_word():
    seen: list[str] = []

    def handler(rest: str, ctx: SlashContext) -> SlashResult:
        seen.append(rest)
        return SlashResult.ok(f"got {rest!r}")

    reg = SlashRegistry()
    reg.register("/echo", handler, summary="echo")
    result = reg.dispatch("/echo  hello world  ", _ctx())
    assert result is not None
    assert result.text == "got 'hello world'"
    assert seen == ["hello world"]


def test_unknown_command_returns_none():
    reg = SlashRegistry()
    assert reg.dispatch("/nope", _ctx()) is None


def test_alias_routes_to_canonical_handler():
    def handler(rest: str, ctx: SlashContext) -> SlashResult:
        del rest, ctx
        return SlashResult(quit=True)

    reg = SlashRegistry()
    reg.register("/quit", handler, summary="exit", aliases=("/q", "/exit"))
    for cmd in ("/quit", "/q", "/exit"):
        result = reg.dispatch(cmd, _ctx())
        assert result is not None and result.quit, cmd


def test_names_includes_aliases_and_canonical():
    reg = SlashRegistry()
    reg.register("/quit", lambda r, c: SlashResult.ok(), summary="", aliases=("/q",))
    reg.register("/help", lambda r, c: SlashResult.ok(), summary="")
    assert reg.names() == ["/help", "/q", "/quit"]


def test_dispatch_rejects_non_slash_line():
    reg = SlashRegistry()
    reg.register("/help", lambda r, c: SlashResult.ok(), summary="")
    result = reg.dispatch("help", _ctx())
    # Not None — it's reported as an error so tests see a clear signal.
    assert result is not None
    assert result.is_error
