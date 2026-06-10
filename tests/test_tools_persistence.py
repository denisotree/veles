"""M120.1: tools / tool_uses CRUD and telemetry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.risk import RiskClass
from veles.core.tool_result import DEFAULT_MAX_RESULT_CHARS
from veles.core.tools.persistence import (
    ToolRecord,
    ToolTelemetry,
    get_tool,
    inheritance_chain,
    list_tools,
    record_use,
    telemetry,
    telemetry_batch,
    upsert_tool,
)
from veles.core.tools.registry import ToolEntry


@pytest.fixture()
def conn(tmp_path: Path):
    """Reuse SessionStore so we inherit the v3 schema (tools / tool_uses /
    everything else). Yields the raw connection — tests don't need
    SessionStore methods, only direct SQL access."""
    store = SessionStore(tmp_path / "memory.db")
    yield store._conn
    store._conn.close()


def _entry(
    name: str,
    *,
    description: str = "",
    side_effects: list[str] | None = None,
    timeout_s: float | None = None,
    sensitive: bool = False,
    risk_class: RiskClass | None = None,
) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=description or f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kwargs: "ok",
        is_async=False,
        sensitive=sensitive,
        risk_class=risk_class,
        side_effects=list(side_effects) if side_effects else [],
        timeout_s=timeout_s,
        max_result_chars=DEFAULT_MAX_RESULT_CHARS,
    )


# ---- upsert_tool ----


def test_upsert_creates_new_row(conn) -> None:
    tid = upsert_tool(
        conn, _entry("read_file", description="read file contents")
    )
    assert tid > 0
    rec = get_tool(conn, "read_file")
    assert rec is not None
    assert rec.id == tid
    assert rec.scope == "builtin"
    assert rec.origin == "builtin"
    assert rec.description == "read file contents"


def test_upsert_is_idempotent_on_name(conn) -> None:
    """Second upsert with same name returns the same id (natural-key
    upsert), not a duplicate row."""
    tid1 = upsert_tool(conn, _entry("read_file"))
    tid2 = upsert_tool(conn, _entry("read_file", description="updated"))
    assert tid1 == tid2
    rec = get_tool(conn, "read_file")
    assert rec is not None
    assert rec.description == "updated"


def test_upsert_with_explicit_scope_and_origin(conn) -> None:
    upsert_tool(
        conn,
        _entry("custom_search"),
        scope="project",
        origin="agent-generated",
    )
    rec = get_tool(conn, "custom_search")
    assert rec is not None
    assert rec.scope == "project"
    assert rec.origin == "agent-generated"


def test_upsert_serialises_manifest_metadata(conn) -> None:
    """The manifest_json column carries the side_effects / timeout /
    risk_class fields that don't have dedicated columns."""
    upsert_tool(
        conn,
        _entry(
            "run_shell",
            side_effects=["filesystem", "process"],
            timeout_s=30.0,
            sensitive=True,
            risk_class=RiskClass.PROCESS_EXECUTION,
        ),
        scope="builtin",
        origin="builtin",
    )
    rec = get_tool(conn, "run_shell")
    assert rec is not None
    assert rec.manifest_json is not None
    payload = json.loads(rec.manifest_json)
    assert payload["side_effects"] == ["filesystem", "process"]
    assert payload["timeout_s"] == 30.0
    assert payload["sensitive"] is True
    assert payload["risk_class"] == RiskClass.PROCESS_EXECUTION.value


def test_upsert_with_base_tool_resolves_name_to_id(conn) -> None:
    upsert_tool(conn, _entry("base_io"))
    upsert_tool(
        conn,
        _entry("write_file"),
        scope="project",
        origin="agent-generated",
        base_tool_name="base_io",
    )
    rec = get_tool(conn, "write_file")
    base = get_tool(conn, "base_io")
    assert rec is not None and base is not None
    assert rec.base_tool_id == base.id


def test_upsert_unknown_base_tool_stores_null(conn) -> None:
    upsert_tool(
        conn,
        _entry("orphan"),
        base_tool_name="does_not_exist",
    )
    rec = get_tool(conn, "orphan")
    assert rec is not None
    assert rec.base_tool_id is None


# ---- list_tools ----


def test_list_tools_sorted_by_name(conn) -> None:
    for name in ("zeta", "alpha", "gamma"):
        upsert_tool(conn, _entry(name))
    names = [r.name for r in list_tools(conn)]
    assert names == ["alpha", "gamma", "zeta"]


def test_list_tools_filtered_by_scope(conn) -> None:
    upsert_tool(conn, _entry("a"), scope="builtin")
    upsert_tool(conn, _entry("b"), scope="project")
    upsert_tool(conn, _entry("c"), scope="user")
    proj = [r.name for r in list_tools(conn, scope="project")]
    assert proj == ["b"]


def test_list_tools_filtered_by_origin(conn) -> None:
    upsert_tool(conn, _entry("a"), origin="builtin")
    upsert_tool(conn, _entry("b"), origin="agent-generated")
    upsert_tool(conn, _entry("c"), origin="manual")
    agent_made = [r.name for r in list_tools(conn, origin="agent-generated")]
    assert agent_made == ["b"]


# ---- record_use ----


def test_record_use_writes_telemetry_row(conn) -> None:
    upsert_tool(conn, _entry("read_file"))
    uid = record_use(conn, tool_name="read_file", ok=True, latency_ms=12)
    assert uid > 0
    row = conn.execute(
        "SELECT ok, latency_ms FROM tool_uses WHERE id = ?", (uid,)
    ).fetchone()
    assert row["ok"] == 1
    assert row["latency_ms"] == 12


def test_record_use_on_unknown_tool_is_noop(conn) -> None:
    """A dispatch before the catalogue is synced shouldn't crash the
    call — record_use returns 0 instead of raising."""
    uid = record_use(conn, tool_name="never_seen", ok=True)
    assert uid == 0


def test_record_use_carries_error_kind(conn) -> None:
    upsert_tool(conn, _entry("read_file"))
    record_use(
        conn,
        tool_name="read_file",
        ok=False,
        latency_ms=5,
        error_kind="permission_denied",
    )
    row = conn.execute(
        "SELECT ok, error_kind FROM tool_uses ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["ok"] == 0
    assert row["error_kind"] == "permission_denied"


def test_record_use_with_session_link(conn) -> None:
    """When session_id is supplied and exists, the FK populates."""
    conn.execute(
        "INSERT INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        ("sess-1", 0.0, 0.0),
    )
    upsert_tool(conn, _entry("read_file"))
    record_use(conn, tool_name="read_file", ok=True, session_id="sess-1")
    row = conn.execute(
        "SELECT session_id FROM tool_uses ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["session_id"] == "sess-1"


# ---- telemetry ----


def test_telemetry_zero_when_never_used(conn) -> None:
    upsert_tool(conn, _entry("read_file"))
    t = telemetry(conn, "read_file")
    assert isinstance(t, ToolTelemetry)
    assert t.use_count == 0
    assert t.success_rate == 0.0
    assert t.last_used_at is None
    assert t.avg_latency_ms is None


def test_telemetry_aggregates_counts_and_rate(conn) -> None:
    upsert_tool(conn, _entry("read_file"))
    record_use(conn, tool_name="read_file", ok=True, latency_ms=10, now=100.0)
    record_use(conn, tool_name="read_file", ok=True, latency_ms=20, now=200.0)
    record_use(conn, tool_name="read_file", ok=False, latency_ms=15, now=300.0)
    t = telemetry(conn, "read_file")
    assert t.use_count == 3
    assert t.success_count == 2
    assert t.error_count == 1
    assert t.success_rate == pytest.approx(2 / 3)
    assert t.last_used_at == 300.0
    assert t.avg_latency_ms == pytest.approx(15.0)


def test_telemetry_unknown_tool_returns_zero_record(conn) -> None:
    """Don't raise on unknown — the UI wants 'no uses' over a 404."""
    t = telemetry(conn, "never_made")
    assert t.use_count == 0
    assert t.tool_name == "never_made"


def test_telemetry_batch_one_query(conn) -> None:
    for name in ("a", "b"):
        upsert_tool(conn, _entry(name))
    record_use(conn, tool_name="a", ok=True, latency_ms=10)
    record_use(conn, tool_name="a", ok=True, latency_ms=20)
    record_use(conn, tool_name="b", ok=False, latency_ms=5)

    out = telemetry_batch(conn, ["a", "b", "c"])
    assert set(out.keys()) == {"a", "b", "c"}
    assert out["a"].use_count == 2
    assert out["b"].use_count == 1
    # `c` doesn't exist in tools — batch returns zero record uniformly.
    assert out["c"].use_count == 0


# ---- inheritance_chain ----


def test_inheritance_chain_walks_base_pointers(conn) -> None:
    upsert_tool(conn, _entry("io_base"))
    upsert_tool(conn, _entry("file_io"), base_tool_name="io_base")
    upsert_tool(conn, _entry("typed_writer"), base_tool_name="file_io")

    chain = inheritance_chain(conn, "typed_writer")
    names = [r.name for r in chain]
    assert names == ["typed_writer", "file_io", "io_base"]


def test_inheritance_chain_single_node_when_no_parent(conn) -> None:
    upsert_tool(conn, _entry("standalone"))
    chain = inheritance_chain(conn, "standalone")
    assert [r.name for r in chain] == ["standalone"]


def test_inheritance_chain_unknown_name_returns_empty(conn) -> None:
    assert inheritance_chain(conn, "never_made") == []


def test_inheritance_chain_types_are_records(conn) -> None:
    upsert_tool(conn, _entry("base"))
    upsert_tool(conn, _entry("child"), base_tool_name="base")
    chain = inheritance_chain(conn, "child")
    assert all(isinstance(r, ToolRecord) for r in chain)
