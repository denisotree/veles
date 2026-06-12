"""Ensure the pytest basetemp parent exists before any tmp_path is used.

`pyproject.toml` pins `--basetemp=./tmp/pytest` to keep scratch dirs inside
the repo. pytest creates that leaf with a plain `mkdir` and expects the
parent `tmp/` to already exist — true after the first local run, but not on
a fresh checkout (CI, new clones), where every `tmp_path` test would error
at setup with `FileNotFoundError: .../tmp/pytest`. Create the parent here,
before any fixture requests a temp dir.
"""

from __future__ import annotations

import os


def pytest_configure() -> None:
    os.makedirs("tmp", exist_ok=True)
