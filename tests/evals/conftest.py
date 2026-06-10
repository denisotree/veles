"""Eval-suite gate: opt-in via VELES_EVALS=1.

Adversarial scenarios live here (Tier ε, M70). Running them is slow-ish
(some scenarios spawn temp projects, write artifacts, exercise the
permission engine end-to-end), and the failure mode is different from a
unit-test red light: an eval failure means "production behaviour drifted
in a way that could let a real attack through", not "this line is wrong".

So the suite is gated. Default CI doesn't run it; only an explicit
`VELES_EVALS=1 pytest tests/evals/` will. The launch-gate before tagging
a release is: this suite must be green on the target commit.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip every item in tests/evals/ unless VELES_EVALS=1 is set."""
    if os.environ.get("VELES_EVALS") == "1":
        return
    skip_eval = pytest.mark.skip(
        reason="adversarial eval suite is opt-in; set VELES_EVALS=1 to run"
    )
    for item in items:
        if "tests/evals/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip_eval)
