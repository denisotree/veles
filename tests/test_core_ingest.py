"""M85: prompt + user-message templates live in core/ingest, shared by
the CLI (`veles add`, `veles ingest`) and the TUI (`/wiki add` from M83)."""

from __future__ import annotations

from veles.modules.wiki.ingest import INGEST_SYSTEM_PROMPT, ingest_user_message


def test_system_prompt_mentions_required_tools():
    assert "fetch_url" in INGEST_SYSTEM_PROMPT
    assert "read_file" in INGEST_SYSTEM_PROMPT
    assert "wiki_write_page" in INGEST_SYSTEM_PROMPT
    assert "wiki_append_log" in INGEST_SYSTEM_PROMPT


def test_system_prompt_lists_categories():
    for cat in ("concepts", "entities", "sources"):
        assert cat in INGEST_SYSTEM_PROMPT


def test_user_message_includes_source_verbatim():
    msg = ingest_user_message("https://example.com/post")
    assert "https://example.com/post" in msg
    assert msg.startswith("Ingest this source:")


def test_user_message_handles_local_path():
    msg = ingest_user_message("./docs/foo.md")
    assert "./docs/foo.md" in msg
