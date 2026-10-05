"""M116b: the daemon reports each session's token usage and context window, so a
channel's /tokens and /context have something to show."""

from __future__ import annotations

from veles.core.agent import RunResult, UsageSnapshot
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.in_process_backend import InProcessRunBackend
from veles.daemon.server import build_state, make_app


class _Agent:
    def __init__(self, prompt_tokens: int) -> None:
        self._prompt = prompt_tokens

    def run(self, prompt: str, *, on_text_delta, event_listener=None):
        on_text_delta("ok")
        return RunResult(
            text="ok",
            iterations=1,
            stopped_reason="completed",
            session_id="ses-u",
            usage=UsageSnapshot(
                prompt_tokens=self._prompt,
                completion_tokens=20,
                total_tokens=self._prompt + 20,
                cache_read_tokens=5,
                last_prompt_tokens=self._prompt,
            ),
        )


def _state(tmp_path, sizes: list[int]):
    project = init_project(tmp_path / "p", name="p")
    agents = iter([_Agent(n) for n in sizes])

    def factory(session_id, *, prompt=None, **_kw):
        return next(agents)

    return build_state(
        project=project,
        store=SessionStore(project.memory_db_path),
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
        default_model="anthropic/claude-sonnet-4.6",
    )


async def _turn(backend: InProcessRunBackend) -> None:
    run = await backend.submit_run("hi", session_id="ses-u")
    async for event in backend.stream_events(run["run_id"]):
        if event["type"] in ("completed", "error"):
            break


async def test_usage_sums_runs_and_keeps_the_latest_prompt_size(tmp_path) -> None:
    state = _state(tmp_path, [100, 150])
    backend = InProcessRunBackend(state)
    await _turn(backend)
    await _turn(backend)
    usage = await backend.get_session_usage("ses-u")
    assert usage["tokens_in"] == 250 and usage["tokens_out"] == 40
    assert usage["cache_read"] == 10 and usage["last_prompt_tokens"] == 150
    assert usage["context_window"] > 0 and usage["model"] == "anthropic/claude-sonnet-4.6"
    assert usage["since_daemon_start"] is True


async def test_in_process_health_names_the_model_like_the_http_one(tmp_path) -> None:
    """A gateway inside the daemon reads `health()["model"]` for `/settings`."""
    health = await InProcessRunBackend(_state(tmp_path, [])).health()
    assert health["model"] == "anthropic/claude-sonnet-4.6"


async def test_an_unknown_session_reports_zeros(tmp_path) -> None:
    backend = InProcessRunBackend(_state(tmp_path, []))
    usage = await backend.get_session_usage("nope")
    assert usage["tokens_in"] == 0 and usage["last_prompt_tokens"] == 0


async def test_the_http_route_returns_the_same(tmp_path, aiohttp_client) -> None:
    state = _state(tmp_path, [100])
    await _turn(InProcessRunBackend(state))
    token = state.token_store.add("t").token
    client = await aiohttp_client(make_app(state))
    resp = await client.get(
        "/v1/sessions/ses-u/usage", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["tokens_in"] == 100 and body["session_id"] == "ses-u"
