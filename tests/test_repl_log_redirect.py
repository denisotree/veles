"""REPL log redirect (live 2026-07-08).

`logger.warning` lines from `veles.*` (e.g. tool_dispatch's `tool.error
name=… err=…`) used to hit the default stderr handler and print straight
into the inline REPL's chat area — redundant noise: the HUD already marks
failed tools and every tool error is persisted to events.jsonl. During a
REPL session the `veles` logger routes to `.veles/repl.log` instead.
"""

from __future__ import annotations

import logging
from pathlib import Path

from veles.cli.commands.repl import _veles_log_redirect
from veles.core.project import init_project


def test_redirect_sends_veles_logs_to_file_not_stderr(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path, name="t")
    logger = logging.getLogger("veles.core.tool_dispatch")
    with _veles_log_redirect(project):
        logger.warning("tool.error name=%s err=%s", "read_file", "TypeError: boom")
    captured = capsys.readouterr()
    assert "tool.error" not in captured.err
    assert "tool.error" not in captured.out
    log_file = project.state_dir / "repl.log"
    assert log_file.is_file()
    assert "tool.error name=read_file err=TypeError: boom" in log_file.read_text(encoding="utf-8")


def test_redirect_restores_propagation_after_exit(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    veles_logger = logging.getLogger("veles")
    before_propagate = veles_logger.propagate
    before_handlers = list(veles_logger.handlers)
    with _veles_log_redirect(project):
        assert veles_logger.propagate is False
    assert veles_logger.propagate == before_propagate
    assert veles_logger.handlers == before_handlers
