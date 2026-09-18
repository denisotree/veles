"""M252: a real tool dispatch lands a `tool_uses` row.

**Why these tests go through `_dispatch` and never call `record_use`.**
`record_use` had no production caller at all before M252 — the only callers were
tests, including `test_tool_authoring_e2e.py`, which invokes it by hand and
passes. That is precisely why the gap survived: every test asserted the
persistence layer works, none asserted anything *calls* it. A test that reaches
`record_use` directly re-creates the blind spot it is supposed to close, so
every assertion here starts from a tool call.
"""

from __future__ import annotations

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.provider import ToolCall
from veles.core.tool_dispatch import _dispatch
from veles.core.tools.registry import Registry, ToolEntry


def _entry(name: str, handler) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"tool {name}",
        parameter_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": [],
        },
        handler=handler,
        is_async=False,
    )


def _registry(name: str, handler) -> Registry:
    reg = Registry()
    reg.register(_entry(name, handler))
    return reg


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    tok = set_active_project(p)
    yield p
    reset_active_project(tok)


def _uses(project) -> list[tuple[str, int, str | None]]:
    """(tool name, ok, error_kind) for every recorded use."""
    store = SessionStore(project.memory_db_path)
    try:
        rows = store._conn.execute(
            "SELECT t.name, u.ok, u.error_kind, u.session_id, u.latency_ms"
            " FROM tool_uses u JOIN tools t ON t.id = u.tool_id"
            " ORDER BY u.invoked_at"
        ).fetchall()
    finally:
        store.close()
    return [(r["name"], r["ok"], r["error_kind"]) for r in rows]


def _session(project, key: str = "a") -> str:
    """A real `sessions` row. `tool_uses.session_id` is a foreign key into it,
    which is also what production hands to `_dispatch` — the agent's session id
    always comes from `store.create_session`."""
    store = SessionStore(project.memory_db_path)
    try:
        return store.create_session(title=key)
    finally:
        store.close()


def _call(reg: Registry, name: str, session_id: str | None = None):
    return _dispatch(
        reg,
        ToolCall(id="c1", name=name, arguments={"text": "hi"}),
        log=lambda _msg: None,
        session_id=session_id,
    )


def test_a_successful_dispatch_is_recorded(project) -> None:
    reg = _registry("echo", lambda text="": text)
    _call(reg, "echo")
    assert _uses(project) == [("echo", 1, None)]


def test_a_failing_dispatch_is_recorded_as_an_error(project) -> None:
    def _boom(text: str = "") -> str:
        raise ValueError("nope")

    reg = _registry("boom", _boom)
    _call(reg, "boom")
    assert _uses(project) == [("boom", 0, "ValueError")]


def test_the_tool_is_catalogued_on_first_use(project) -> None:
    """`record_use` is a silent no-op without a catalogue row — which is every
    builtin, since nothing catalogues them. The upsert has to come first or the
    telemetry stays empty in exactly the common case."""
    from veles.core.tools.persistence import get_tool

    reg = _registry("echo", lambda text="": text)
    _call(reg, "echo")

    store = SessionStore(project.memory_db_path)
    try:
        assert get_tool(store._conn, "echo") is not None
    finally:
        store.close()


def test_repeated_dispatches_accumulate(project) -> None:
    reg = _registry("echo", lambda text="": text)
    for _ in range(3):
        _call(reg, "echo")
    assert len(_uses(project)) == 3


def test_session_id_and_latency_are_stored(project) -> None:
    sid = _session(project)
    reg = _registry("echo", lambda text="": text)
    _call(reg, "echo", session_id=sid)

    store = SessionStore(project.memory_db_path)
    try:
        row = store._conn.execute("SELECT session_id, latency_ms FROM tool_uses").fetchone()
    finally:
        store.close()
    assert row["session_id"] == sid
    assert row["latency_ms"] >= 0


def test_a_dangling_session_id_still_records_the_use(project) -> None:
    """`session_id` is a foreign key. A caller holding an id whose row is not in
    THIS database (a sub-agent against another store, a pruned session) used to
    lose the row to an IntegrityError — the exact silent loss M252 removes. The
    count survives unattributed; only the grouping is given up."""
    reg = _registry("echo", lambda text="": text)
    _call(reg, "echo", session_id="not-a-real-session")

    store = SessionStore(project.memory_db_path)
    try:
        row = store._conn.execute("SELECT session_id, ok FROM tool_uses").fetchone()
    finally:
        store.close()
    assert row is not None
    assert row["session_id"] is None
    assert row["ok"] == 1


def test_a_refused_call_records_nothing(project) -> None:
    """Telemetry is about tools that ran. A call the model made for a tool that
    isn't in the active toolset never reaches the handler."""
    reg = _registry("echo", lambda text="": text)
    _dispatch(
        reg,
        ToolCall(id="c1", name="ghost", arguments={}),
        log=lambda _msg: None,
        session_id=_session(project),
    )
    assert _uses(project) == []


def test_no_active_project_is_not_an_error(project) -> None:
    """A bare sub-agent or unit test has no project — dispatch must still work."""
    tok = set_active_project(None)
    try:
        reg = _registry("echo", lambda text="": text)
        message = _call(reg, "echo")
    finally:
        reset_active_project(tok)
    assert message.content == "hi"


def test_telemetry_reaches_the_pattern_detector(project) -> None:
    """The consequence that matters beyond the uses/ok% columns: M121b's
    detector — the "propose a skill after 3 repetitions" loop — reads
    `tool_uses`, so it could never fire on a table nothing ever wrote to.

    Three sessions repeating the same two-tool sequence is exactly the shape it
    is built to spot."""
    from veles.core.skill_pattern_detector import detect_patterns

    reg = Registry()
    reg.register(_entry("search", lambda text="": text))
    reg.register(_entry("read", lambda text="": text))
    for n in range(3):
        sid = _session(project, key=f"s{n}")
        _call(reg, "search", session_id=sid)
        _call(reg, "read", session_id=sid)

    store = SessionStore(project.memory_db_path)
    try:
        patterns = detect_patterns(store._conn, min_repetitions=3, min_calls=2)
    finally:
        store.close()
    assert [p.tools for p in patterns] == [("search", "read")]
