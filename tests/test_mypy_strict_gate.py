"""Tier δ M60 — mypy --strict gate over the Sprint ε modules.

We don't strict-check the full source tree (legacy surface still drifts);
the gate is targeted at the new modules I authored after the Sprint ε
hardening trunk. The file list lives in pyproject.toml under
[tool.mypy].files — running `uv run mypy` with no args checks exactly
those.

This test invokes mypy programmatically so the CI signal lives in
pytest, where the rest of the project's quality bar already runs.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_mypy_strict_passes_on_sprint_epsilon_modules() -> None:
    """Run `mypy` with the configuration from pyproject.toml.

    Skipped when mypy isn't installed (dev-only dep). Asserts exit code
    0 and surfaces the full output on failure so failing types are easy
    to read in CI logs.
    """
    try:
        import mypy  # noqa: F401
    except ImportError:
        pytest.skip("mypy not installed (dev dependency)")
    result = subprocess.run(
        [sys.executable, "-m", "mypy"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"mypy --strict failed:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n"
    )
