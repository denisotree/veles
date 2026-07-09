"""Ingest prompt/message wiring for `veles add`.

M85 gave `veles add` a shared user-message template. M203 makes `add`
content-aware: instead of a hardcoded "write a single wiki page" prompt, it
routes through `build_run_system_prompt` so the llm-wiki layout behaviour
(topic extraction → find-or-create-or-patch) is injected — the same prompt a
`veles run` migration turn gets. These tests pin the mechanical wiring; the
topical-vs-date-named behaviour itself is a live eval (see the M203 design doc).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache
from veles.core.project import init_project
from veles.modules.wiki.ingest import ingest_user_message


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---------- user message (unchanged; still used by the REPL /wiki add) ----------


def test_user_message_includes_source_verbatim():
    msg = ingest_user_message("https://example.com/post")
    assert "https://example.com/post" in msg
    assert msg.startswith("Ingest this source")


def test_user_message_handles_local_path():
    msg = ingest_user_message("./docs/foo.md")
    assert "./docs/foo.md" in msg


def test_user_message_embeds_prefetched_content():
    """B1 (2026-07-07 audit): the ingest agent has no fetch_url, so a URL
    source is pre-fetched by the CLI and its (untrusted-wrapped) content is
    handed to the agent inline — the message must carry the content and tell
    the agent NOT to fetch it again."""
    wrapped = '<untrusted source="https://x.com">\nfetched body\n</untrusted>'
    msg = ingest_user_message("https://x.com", content=wrapped)
    assert "https://x.com" in msg
    assert "fetched body" in msg
    assert "not" in msg.lower() and "fetch" in msg.lower()  # "do not fetch it again"
    # still content-aware
    assert "topic" in msg.lower()


def test_user_message_carries_content_aware_directive():
    """M203: the kickoff turn itself must steer a weak model to topic pages —
    behaviour.md alone (conditional, ambient) let gpt-4o-mini fall back to a
    single date-named dump. The always-read user turn spells out topics +
    create-or-patch + no-date-named-page."""
    msg = ingest_user_message("./diary/2025-02-27.md").lower()
    assert "topic" in msg
    # explicit prohibition on the exact failure mode
    assert "never" in msg and ("named after the file" in msg or "date" in msg)
    # create-or-patch framing
    assert "wiki_search" in msg or "patch" in msg


# ---------- M203: add routes through the content-aware run prompt ----------


def test_ingest_system_prompt_injects_layout_behaviour(isolated_home: Path, tmp_path: Path):
    """`veles add` must build its system prompt via `build_run_system_prompt`,
    so the llm-wiki behaviour (M190/M203) is injected — not the retired
    single-page dump."""
    from tests.conftest import StubProvider
    from veles.cli.commands.ingest import ingest_system_prompt

    project = init_project(tmp_path / "proj", name="proj")
    prompt = ingest_system_prompt(project, StubProvider(), ("read_file", "wiki_write_page"))

    assert prompt is not None
    assert "Layout behaviour instructions" in prompt
    # M203 multi-topic framing is present…
    assert "several distinct topics" in prompt.lower()
    # …and the old 1:1 "single wiki page" dump is gone.
    assert "write a single wiki page" not in prompt.lower()
