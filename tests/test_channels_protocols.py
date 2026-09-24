"""RunBackend Protocol — structural conformance for both the in-process and the
HTTP backend, so a gateway can type its backend as `RunBackend` and call every
method without `Any`."""

from __future__ import annotations

import inspect

import pytest

from veles.channels.protocols import RunBackend

_METHODS = [
    name
    for name, member in inspect.getmembers(RunBackend)
    if not name.startswith("_") and callable(member)
]


def _backends():
    from veles.channels.daemon_client import DaemonClient
    from veles.daemon.in_process_backend import InProcessRunBackend

    return [InProcessRunBackend, DaemonClient]


@pytest.mark.parametrize("backend", _backends(), ids=lambda b: b.__name__)
def test_backend_implements_every_protocol_method(backend) -> None:
    missing = [m for m in _METHODS if not callable(getattr(backend, m, None))]
    assert not missing, f"{backend.__name__} lacks {missing}"


def test_the_protocol_covers_what_the_gateway_calls() -> None:
    assert {"get_session", "update_session", "cancel_goal", "run_dream", "health"} <= set(_METHODS)
