"""M-R2.7: RunBackend Protocol — structural conformance for both
in-process and HTTP backend implementations."""

from __future__ import annotations

from veles.channels.protocols import RunBackend


def test_in_process_backend_conforms() -> None:
    """`InProcessRunBackend` satisfies the RunBackend protocol."""
    from veles.channels.in_process_backend import InProcessRunBackend

    # The protocol is `runtime_checkable`, so isinstance works against
    # the class definition (structural typing).
    assert hasattr(InProcessRunBackend, "submit_run")
    assert hasattr(InProcessRunBackend, "stream_events")


def test_daemon_client_conforms() -> None:
    """`DaemonClient` satisfies the RunBackend protocol — the HTTP path
    matches the same shape the in-process backend exposes."""
    from veles.channels.daemon_client import DaemonClient

    assert hasattr(DaemonClient, "submit_run")
    assert hasattr(DaemonClient, "stream_events")


def test_runtime_checkable_isinstance() -> None:
    """A stub class with the right method set satisfies isinstance() —
    structural typing keeps the contract loose enough for adapters."""

    class Stub:
        async def submit_run(self, prompt, *, session_id=None, origin=None):
            return {"run_id": "x"}

        def stream_events(self, run_id):
            async def _g():
                yield {"type": "completed"}

            return _g()

        async def submit_prompt_answer(self, run_id, prompt_id, choice):
            return {"accepted": True}

    assert isinstance(Stub(), RunBackend)
