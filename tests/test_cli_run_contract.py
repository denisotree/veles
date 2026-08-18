"""M232: the `veles run` subprocess contract.

`veles run` is the supported way to embed Veles in someone else's pipeline: the
caller reads stdout as the answer, stderr as diagnostics, and the exit code as
the outcome. Every property below was *observed* behaviour that nothing asserted
— a refactor moving `<session=…>` into stdout, adding a banner, or collapsing the
exit code would have broken every embedder silently. These tests are the lock.

Out of contract, deliberately, and asserted as such where cheap:
  * `--stream` — stdout then carries every round's prose, including narration
    emitted before tool calls, not just the final answer.
  * `--manager` — returns before the session line and the exit-code mapping.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

import pytest

import veles.cli as cli
from veles.cli.commands.run import EXIT_BY_REASON, cmd_run
from veles.core.project import Project, init_project
from veles.core.provider import ProviderError


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    return init_project(tmp_path / "proj", name="proj")


def _args(**overrides: Any) -> argparse.Namespace:
    base = dict(
        prompt="hi",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        max_iterations=10,
        max_tokens_total=1000,
        verbose=False,
        stream=False,
        project_root=None,
        resume=None,
        manager=False,
        verify=False,
        no_agents_md=True,
        no_index=True,
        no_compress=True,
        no_curator=True,
        no_insights=True,
        no_proposer=True,
        no_route_refresh=True,
        no_suggest_promote=True,
        compressor_model=None,
        compress_threshold_tokens=50_000,
        plan=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class _Result:
    """Stand-in for RunResult — only the fields `cmd_run` touches."""

    def __init__(self, text: str = "the answer", stopped_reason: str = "completed") -> None:
        self.text = text
        self.stopped_reason = stopped_reason
        self.session_id = "sess-1"
        self.history: list[Any] = []
        self.iterations = 1


class _Agent:
    """Stand-in for the built Agent — `run()` is the only thing the CLI calls."""

    def __init__(self, result: _Result) -> None:
        self._result = result

    def run(self, _prompt: str, **_kwargs: Any) -> _Result:
        return self._result


def _stub_run(monkeypatch: pytest.MonkeyPatch, result: _Result) -> None:
    """Stub the *model*, not the CLI plumbing.

    Deliberately patched at `build_command_agent` rather than at
    `_run_agent_streaming_aware`: the final `print(result.text)` and the
    streaming branch both live inside the latter, so stubbing it would have made
    the stdout assertions test the stub instead of the contract.
    """
    monkeypatch.setattr(cli, "build_command_agent", lambda *a, **k: _Agent(result))


# ---- 1. stdout carries the answer and nothing else ---------------------------


def test_stdout_is_exactly_the_answer_plus_newline(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _stub_run(monkeypatch, _Result(text="the answer"))
    cmd_run(_args(), project)
    captured = capsys.readouterr()
    assert captured.out == "the answer\n"


# ---- 2. diagnostics stay on stderr ------------------------------------------


def test_session_marker_and_summary_go_to_stderr_only(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _stub_run(monkeypatch, _Result())
    cmd_run(_args(verbose=True), project)
    captured = capsys.readouterr()
    assert "<session=" in captured.err
    assert "<finished after" in captured.err
    for marker in ("<session=", "<finished after", "<verify:", "error:", "warning:"):
        assert marker not in captured.out


def test_provider_error_message_goes_to_stderr_not_stdout(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    class _Exploding:
        def run(self, *_a: Any, **_k: Any):
            raise ProviderError("upstream exploded")

    monkeypatch.setattr(cli, "build_command_agent", lambda *a, **k: _Exploding())
    rc = cmd_run(_args(), project)
    captured = capsys.readouterr()
    assert rc == 1
    assert "error: upstream exploded" in captured.err
    assert captured.out == ""


# ---- 3. exit codes distinguish the failure modes (M228) ----------------------


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("completed", 0),
        ("max_iterations", 3),
        ("budget_exhausted", 4),
        ("empty", 5),
        ("cancelled", 6),
    ],
)
def test_exit_code_per_stopped_reason(
    project: Project, monkeypatch: pytest.MonkeyPatch, reason: str, expected: int
) -> None:
    _stub_run(monkeypatch, _Result(stopped_reason=reason))
    assert cmd_run(_args(), project) == expected


def test_unknown_stopped_reason_degrades_to_generic_failure(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reason added later must never be mistaken for success."""
    _stub_run(monkeypatch, _Result(stopped_reason="something_new"))
    assert cmd_run(_args(), project) == 1


def test_exit_codes_avoid_shell_reserved_range() -> None:
    """126/127/128+n are shell-reserved; a caller must be able to tell ours apart."""
    assert all(0 <= code < 125 for code in EXIT_BY_REASON.values())
    assert len(set(EXIT_BY_REASON.values())) == len(EXIT_BY_REASON)


# ---- 4. a skipped unapproved tool is never silent (M229) ---------------------


def test_unapproved_tool_file_warns_on_stderr(project: Project, capsys) -> None:
    """An unapproved tool file must announce itself, loudly and greppably.

    It is dropped from the toolset without the model seeing the tool *or* a
    refusal, so the agent can answer confidently having never reached its data
    source — and still exit 0. Printed rather than logged: relying on logging's
    lastResort stderr handler makes the visibility accidental, and it vanishes
    as soon as an embedder configures logging.
    """
    from veles.cli._runtime import _load_skills

    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "unapproved_probe.py").write_text(
        "from veles.core.tools.registry import tool\n\n\n"
        "@tool()\n"
        "def unapproved_probe(q: str) -> str:\n"
        '    """Probe."""\n'
        "    return q\n"
    )

    registry = _load_skills(
        project,
        ("read_file",),
        provider=cast(Any, object()),
        model="openai/gpt-4o-mini",
    )

    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert "unapproved_probe" in captured.err
    assert "veles tool approve" in captured.err
    assert "unapproved_probe" not in registry.list_names()


# ---- 5. `--stream` is explicitly OUTSIDE the stdout contract -----------------


def test_stream_puts_intermediate_narration_on_stdout(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Documented hazard, asserted so nobody 'fixes' the docs to claim otherwise.

    Under `--stream` the delta callback is installed per round, so stdout gets
    every round's prose — including narration emitted before a tool call — not
    just the final answer. A stdout-parsing embedder must not pass `--stream`.
    """

    class _Streaming:
        def run(self, _prompt: str, on_text_delta=None, **_kwargs: Any) -> _Result:
            if on_text_delta is not None:
                on_text_delta("let me check that first...")
            return _Result(text="the answer")

    monkeypatch.setattr(cli, "build_command_agent", lambda *a, **k: _Streaming())
    cmd_run(_args(stream=True), project)

    out = capsys.readouterr().out
    assert "let me check that first..." in out
    assert out != "the answer\n"


# ---- 6. non-TTY never blocks on a permission prompt --------------------------


def test_non_tty_trust_prompt_refuses_instead_of_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a TTY the trust ladder must deny, not wait on input().

    An embedder pipes stdout/stderr; if the prompter ever reached `input()` the
    subprocess would hang until the caller's timeout instead of returning.
    """
    import veles.core.trust as trust

    monkeypatch.setattr(trust.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(
        "builtins.input", lambda *_a: pytest.fail("prompted for input without a TTY")
    )
    choice = trust._default_prompter("run_shell", {"command": "rm -rf /"}, "test")
    assert choice is trust.TrustChoice.REFUSE


def test_non_tty_critical_confirm_refuses_instead_of_blocking(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from veles.core import critical_ops

    monkeypatch.setattr(critical_ops.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(
        "builtins.input", lambda *_a: pytest.fail("prompted for input without a TTY")
    )
    assert critical_ops.confirm_critical("dispatch fetch_url", "summary") is False
    assert "non-TTY" in capsys.readouterr().err
