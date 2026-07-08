"""Tool-call argument integrity on the OpenAI-compatible wire.

Live failure (2026-07-08, openrouter + anthropic/claude-sonnet-5): EVERY tool
call in a turn died with `TypeError: list_files() got an unexpected keyword
argument '_raw'`. Two defects compound:

1. The stream accumulator buckets tool-call deltas by `delta.index`, but some
   providers/models emit parallel tool calls with a missing/None index — all
   argument chunks then concatenate into ONE bucket (`{"a":1}{"b":2}`), JSON
   decode fails, and `decode_tool_args` wraps it as `{"_raw": …}`.
2. `Registry.dispatch` then calls `handler(**{"_raw": …})` → TypeError. The
   `_raw` contract says "surface to the model", so dispatch must return a
   clean error string the model can react to, never explode.
"""

from __future__ import annotations

from types import SimpleNamespace

from veles.core.openai_wire import OpenAICompatibleProvider
from veles.core.provider import Message, StreamEnd


def _chunk(tool_calls=None, content=None, finish=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=delta, finish_reason=finish)],
    )


def _tc(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks

    def create(self, **_kw):
        return iter(self._chunks)


def _provider(chunks) -> OpenAICompatibleProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions(chunks)))
    return OpenAICompatibleProvider(client=client)


def _stream_end(provider):
    events = list(provider.stream_message([Message(role="user", content="hi")], model="m"))
    return next(e for e in events if isinstance(e, StreamEnd)).response


def test_indexed_parallel_calls_decode_cleanly() -> None:
    chunks = [
        _chunk([_tc(0, id="c1", name="list_files", arguments='{"path"')]),
        _chunk([_tc(0, arguments=': "a"}'), _tc(1, id="c2", name="read_file", arguments="{")]),
        _chunk([_tc(1, arguments='"path": "b"}')]),
        _chunk(finish="tool_calls"),
    ]
    resp = _stream_end(_provider(chunks))
    assert [tc.name for tc in resp.tool_calls] == ["list_files", "read_file"]
    assert resp.tool_calls[0].arguments == {"path": "a"}
    assert resp.tool_calls[1].arguments == {"path": "b"}


def test_none_index_parallel_calls_split_by_id() -> None:
    """The live bug: no `index` on the deltas. A delta carrying a NEW id must
    start a new call; id-less continuations belong to the last one — argument
    strings from different calls must never concatenate."""
    chunks = [
        _chunk([_tc(None, id="c1", name="list_files", arguments='{"path": "a"')]),
        _chunk([_tc(None, arguments="}")]),  # continuation of c1
        _chunk([_tc(None, id="c2", name="read_file", arguments='{"path": "b"}')]),
        _chunk(finish="tool_calls"),
    ]
    resp = _stream_end(_provider(chunks))
    assert [tc.name for tc in resp.tool_calls] == ["list_files", "read_file"]
    assert resp.tool_calls[0].arguments == {"path": "a"}  # NOT {"_raw": ...}
    assert resp.tool_calls[1].arguments == {"path": "b"}


def test_dispatch_surfaces_undecodable_args_instead_of_typeerror() -> None:
    """Even when garbled args slip through, the model must get a readable
    error it can react to — never a TypeError from `handler(**{"_raw": …})`."""
    import veles.core.tools.builtin  # noqa: F401 — register list_files
    from veles.core.tools.registry import registry

    out = registry.dispatch("list_files", {"_raw": '{"path": "a"}{"path": "b"}'})
    assert out.startswith("<error")
    assert "JSON" in out or "json" in out
