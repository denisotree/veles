"""Coverage for each ported slash command. Mirrors `tests/test_tui.py`
(legacy M48/M48b/M58) scenarios but exercises the pure-handler shape so
no Console / prompt_toolkit setup is needed.

Most tests run on the `slash_ctx` fixture: a fresh project + session
store under `./tmp/pytest/...`. Commands that need pre-populated wiki
pages or recorded sessions seed them inline.
"""

from __future__ import annotations

from veles.cli.repl.slash import build_default_registry
from veles.core.provider import Message
from veles.modules.wiki.wiki import Wiki


def _reg():
    return build_default_registry()


# ---------------- basics ----------------


def test_help_lists_every_top_level_command(slash_ctx):
    res = _reg().dispatch("/help", slash_ctx)
    assert res is not None and not res.is_error
    for cmd in (
        "/help",
        "/quit",
        "/clear",
        "/session",
        "/save",
        "/history",
        "/wiki",
        "/model",
        "/theme",
        "/mode",
        "/schema",
        "/self-doc",
    ):
        assert cmd in res.text, cmd


def test_help_omits_removed_commands(slash_ctx):
    """M80: /load /show /search /init removed (picker-only, via the now-deleted
    Textual chat UI's Ctrl+R/Ctrl+T hotkeys). `/theme` was reinstated in M187
    Task 5 as a real slash command once Ctrl+T had no replacement — see
    `test_bare_theme_opens_picker` and friends below."""
    res = _reg().dispatch("/help", slash_ctx)
    assert res is not None
    for cmd in ("/load", "/show", "/search ", "/init"):
        assert cmd not in res.text, cmd


def test_quit_returns_quit_flag(slash_ctx):
    res = _reg().dispatch("/quit", slash_ctx)
    assert res is not None and res.quit


def test_quit_aliases(slash_ctx):
    reg = _reg()
    assert reg.dispatch("/q", slash_ctx).quit  # type: ignore[union-attr]
    assert reg.dispatch("/exit", slash_ctx).quit  # type: ignore[union-attr]


def test_session_with_no_session(slash_ctx):
    res = _reg().dispatch("/session", slash_ctx)
    assert res is not None
    assert "no session" in res.text


def test_clear_resets_session_and_signals_chat_clear(slash_ctx):
    slash_ctx.state.session_id = "old"
    slash_ctx.state.last_assistant_text = "old reply"
    res = _reg().dispatch("/clear", slash_ctx)
    assert res is not None
    assert res.clear_chat
    assert slash_ctx.state.session_id is None
    assert slash_ctx.state.last_assistant_text is None


# ---------------- save / history / load / show ----------------


def test_save_without_response_errors(slash_ctx):
    res = _reg().dispatch("/save my-note", slash_ctx)
    assert res is not None and res.is_error


def test_save_writes_to_queries_and_logs(slash_ctx):
    slash_ctx.state.last_assistant_text = "# Hello\n\nNote body."
    res = _reg().dispatch("/save hello-note", slash_ctx)
    assert res is not None and not res.is_error
    assert "wiki/queries/hello-note.md" in res.text
    wiki = Wiki(slash_ctx.project.wiki_root)
    body = wiki.read_page("wiki/queries/hello-note.md")
    assert "Note body." in body


def test_save_without_slug_errors(slash_ctx):
    slash_ctx.state.last_assistant_text = "x"
    res = _reg().dispatch("/save", slash_ctx)
    assert res is not None and res.is_error


def test_history_empty(slash_ctx):
    res = _reg().dispatch("/history", slash_ctx)
    assert res is not None and "no sessions" in res.text


def test_history_lists_sessions(slash_ctx):
    store = slash_ctx.store
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="ping"))
    res = _reg().dispatch("/history", slash_ctx)
    assert res is not None and not res.is_error
    assert sid in res.text


# ---------------- wiki (M83) ----------------


def test_wiki_bare_returns_usage(slash_ctx):
    res = _reg().dispatch("/wiki", slash_ctx)
    assert res is not None and res.is_error
    assert "add" in res.text and "query" in res.text


def test_wiki_add_queues_ingest_prompt(slash_ctx):
    res = _reg().dispatch("/wiki add https://example.com/post", slash_ctx)
    assert res is not None and not res.is_error
    assert res.submit_prompt is not None
    assert "https://example.com/post" in res.submit_prompt
    assert "Ingest" in res.submit_prompt


def test_wiki_add_without_source_errors(slash_ctx):
    res = _reg().dispatch("/wiki add", slash_ctx)
    assert res is not None and res.is_error


def test_wiki_query_queues_search_prompt(slash_ctx):
    res = _reg().dispatch("/wiki query what do we know about quokkas", slash_ctx)
    assert res is not None and not res.is_error
    assert res.submit_prompt is not None
    assert "quokkas" in res.submit_prompt
    assert "wiki_search" in res.submit_prompt


def test_wiki_query_without_question_errors(slash_ctx):
    res = _reg().dispatch("/wiki query", slash_ctx)
    assert res is not None and res.is_error


def test_wiki_unknown_subcommand_errors(slash_ctx):
    res = _reg().dispatch("/wiki dance", slash_ctx)
    assert res is not None and res.is_error
    assert "add/query" in res.text or "add" in res.text


# ---------------- /model ----------------


def test_bare_model_opens_picker(slash_ctx):
    """Phase 5: `/model` with no args defers to the App's model picker
    (Ctrl+M would be Enter on most terminals, so the slash is the
    canonical entry point)."""
    res = _reg().dispatch("/model", slash_ctx)
    assert res is not None and res.open_picker == "models"


def test_model_set_updates_state(slash_ctx):
    res = _reg().dispatch("/model openai/gpt-4o", slash_ctx)
    assert res is not None and not res.is_error
    assert slash_ctx.state.model == "openai/gpt-4o"


def test_model_refresh_opens_picker_with_refresh_sentinel(slash_ctx):
    """`/model refresh` carries the refresh intent to the App via a
    sentinel name; the App reads `:refresh` and bypasses the cache when
    instantiating the picker."""
    res = _reg().dispatch("/model refresh", slash_ctx)
    assert res is not None
    assert res.open_picker == "models:refresh"
    # `refresh` is the picker intent, not a model id — state must stay put.
    assert slash_ctx.state.model != "refresh"


# ---------------- /theme ----------------


def test_bare_theme_opens_picker(slash_ctx):
    """M187 Task 5: `/theme` with no args defers to the App's theme picker,
    mirroring `/model`."""
    res = _reg().dispatch("/theme", slash_ctx)
    assert res is not None and res.open_picker == "themes"


def test_theme_set_updates_state_and_persists(slash_ctx, tmp_path, monkeypatch):
    from veles.core import user_config as _user_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    res = _reg().dispatch("/theme dracula", slash_ctx)
    assert res is not None and not res.is_error
    assert slash_ctx.state.theme_name == "dracula"
    assert _user_config.load_user_config().tui_theme == "dracula"  # persisted


def test_theme_set_unknown_name_errors_without_touching_state(slash_ctx):
    slash_ctx.state.theme_name = "everforest"
    res = _reg().dispatch("/theme not-a-real-theme", slash_ctx)
    assert res is not None and res.is_error
    assert slash_ctx.state.theme_name == "everforest"  # unchanged


# ---------------- /schema ----------------


def test_schema_validate_ok(slash_ctx):
    res = _reg().dispatch("/schema", slash_ctx)
    # Fresh init_project writes an AGENTS.md with all sections.
    assert res is not None and not res.is_error


def test_schema_fix_stubbed(slash_ctx):
    res = _reg().dispatch("/schema fix", slash_ctx)
    assert res is not None and res.is_error
    assert "not ported" in res.text


# ---------------- /self-doc ----------------


def test_self_doc_refreshes(slash_ctx):
    res = _reg().dispatch("/self-doc", slash_ctx)
    # The doc refresh may fail in a freshly-initialized project with no
    # source files; what we want to assert is that the handler doesn't
    # crash and produces *some* output (success or a captured failure).
    assert res is not None
    assert res.text  # either rendered doc body, or an error message
