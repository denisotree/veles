"""Health-check framework (Tier δ, M59).

`veles doctor` walks a fixed list of checks against the current user-global
and project state. Each check returns a `CheckResult` carrying a status
level, a short message, and an optional fix hint. The CLI renders them as
human-readable text or as JSON for scripting.

The check set surfaces the Sprint ε machinery deliberately: traces, events,
approvals, cache fragmentation, permission engine wiring. A green doctor
run means the agent is observable, gated, and reproducible.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Literal

from veles.core.approval import list_approvals
from veles.core.project import Project
from veles.core.trace import cache_fragmentation_alert, read_records, trace_path_for_project

CheckStatus = Literal["ok", "warn", "error", "info"]

# Soft thresholds (override only if measured failures justify it).
_TRACES_SIZE_WARN_BYTES = 40 * 1024 * 1024  # warn at 40 MB; rotation at 50.
_EVENTS_SIZE_WARN_BYTES = 40 * 1024 * 1024
_AUTOPILOT_REVIEW_WINDOW_S = 7 * 24 * 60 * 60

_PROVIDER_KEY_ENVS: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


@dataclass(slots=True, frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    fix_hint: str = ""
    details: dict[str, object] = field(default_factory=dict)

    def is_failing(self) -> bool:
        return self.status == "error"


@dataclass(slots=True)
class DoctorReport:
    results: list[CheckResult]

    @property
    def has_errors(self) -> bool:
        return any(r.status == "error" for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.status == "warn" for r in self.results)

    def to_json(self) -> str:
        return json.dumps(
            {"results": [asdict(r) for r in self.results]},
            ensure_ascii=False,
            indent=2,
        )

    def to_text(self) -> str:
        glyph = {"ok": "✓", "warn": "!", "error": "✗", "info": "·"}
        lines: list[str] = []
        for r in self.results:
            head = f"  {glyph[r.status]} [{r.status.upper():5}] {r.name}: {r.message}"
            lines.append(head)
            if r.fix_hint:
                lines.append(f"      → {r.fix_hint}")
        summary = (
            f"\n{len([r for r in self.results if r.status == 'ok'])} ok, "
            f"{len([r for r in self.results if r.status == 'warn'])} warn, "
            f"{len([r for r in self.results if r.status == 'error'])} error"
        )
        return "\n".join(lines) + summary


# ---- individual checks ----


def _check_python_version() -> CheckResult:
    minor = sys.version_info.minor
    major = sys.version_info.major
    if (major, minor) >= (3, 13):
        return CheckResult(
            name="python_version",
            status="ok",
            message=f"Python {major}.{minor}.{sys.version_info.micro}",
        )
    return CheckResult(
        name="python_version",
        status="error",
        message=f"Python {major}.{minor} is below the supported 3.13",
        fix_hint="install Python 3.13+ (uv recommended) and re-run",
    )


def _check_user_home() -> CheckResult:
    from veles.core.user_paths import user_home

    home = user_home()
    if not home.exists():
        return CheckResult(
            name="user_home",
            status="info",
            message=f"{home} not created yet (first-run wizard will set it up)",
            fix_hint=(
                "run `veles tui` to trigger the first-run wizard, or `veles init` inside a project"
            ),
        )
    if not os.access(home, os.W_OK):
        return CheckResult(
            name="user_home",
            status="error",
            message=f"{home} exists but is not writable",
            fix_hint=f"check ownership / permissions on {home}",
        )
    return CheckResult(
        name="user_home",
        status="ok",
        message=f"{home} is writable",
    )


def _check_user_config() -> CheckResult:
    from veles.core.user_config import user_config_path

    cfg = user_config_path()
    if not cfg.exists():
        return CheckResult(
            name="user_config",
            status="info",
            message="no user-global config.toml (defaults apply)",
            fix_hint="the first-run wizard creates it; or hand-write per docs",
        )
    try:
        import tomllib

        with cfg.open("rb") as f:
            tomllib.load(f)
    except Exception as exc:
        return CheckResult(
            name="user_config",
            status="error",
            message=f"config.toml present but unparseable: {exc}",
            fix_hint=f"fix or remove {cfg}",
        )
    return CheckResult(name="user_config", status="ok", message=f"{cfg} parses cleanly")


def _check_provider_keys() -> CheckResult:
    present = sorted(p for p, env in _PROVIDER_KEY_ENVS.items() if os.environ.get(env))
    if not present:
        return CheckResult(
            name="provider_keys",
            status="warn",
            message="no provider API keys set in environment",
            fix_hint=("export at least one of: " + ", ".join(sorted(_PROVIDER_KEY_ENVS.values()))),
        )
    return CheckResult(
        name="provider_keys",
        status="ok",
        message=f"keys present for: {', '.join(present)}",
        details={"providers": present},
    )


def _check_active_project(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(
            name="active_project",
            status="info",
            message="no active project at cwd (some checks will be skipped)",
            fix_hint="cd into a project directory or run `veles init`",
        )
    if not project.state_dir.exists():
        return CheckResult(
            name="active_project",
            status="error",
            message=f"project {project.name!r} resolved but state_dir missing",
            fix_hint=f"recreate via `veles init` in {project.root}",
        )
    if not os.access(project.state_dir, os.W_OK):
        return CheckResult(
            name="active_project",
            status="error",
            message=f"project state_dir not writable: {project.state_dir}",
            fix_hint="check filesystem permissions",
        )
    return CheckResult(
        name="active_project",
        status="ok",
        message=f"{project.name!r} at {project.root}",
        details={"root": str(project.root), "state_dir": str(project.state_dir)},
    )


def _check_agents_md(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(name="agents_md", status="info", message="no active project")
    p = project.root / "AGENTS.md"
    if not p.exists():
        return CheckResult(
            name="agents_md",
            status="warn",
            message="AGENTS.md missing — agent has no scoped instructions",
            fix_hint=f"create {p} with project conventions and layout",
        )
    if p.stat().st_size == 0:
        return CheckResult(
            name="agents_md",
            status="warn",
            message="AGENTS.md is empty",
            fix_hint="describe the project layout, conventions, workflows",
        )
    return CheckResult(
        name="agents_md",
        status="ok",
        message=f"AGENTS.md present ({p.stat().st_size} bytes)",
    )


def _check_symlinks(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(name="symlinks", status="info", message="no active project")
    issues: list[str] = []
    for name in ("CLAUDE.md", "GEMINI.md"):
        p = project.root / name
        if not p.exists() and not p.is_symlink():
            issues.append(f"{name} missing")
            continue
        if not p.is_symlink():
            issues.append(f"{name} is a regular file, not a symlink to AGENTS.md")
            continue
        try:
            target = os.readlink(p)
        except OSError as exc:
            issues.append(f"{name}: {exc}")
            continue
        if target != "AGENTS.md":
            issues.append(f"{name} points at {target!r}, not AGENTS.md")
    if issues:
        return CheckResult(
            name="symlinks",
            status="warn",
            message="; ".join(issues),
            fix_hint="run `veles init --force` to re-create symlinks (preserves AGENTS.md)",
        )
    return CheckResult(name="symlinks", status="ok", message="CLAUDE.md and GEMINI.md → AGENTS.md")


def _check_wiki_files(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(name="wiki_files", status="info", message="no active project")
    missing: list[str] = []
    for name in ("INDEX.md", "LOG.md"):
        if not (project.root / name).exists():
            missing.append(name)
    if missing:
        return CheckResult(
            name="wiki_files",
            status="warn",
            message=f"missing: {', '.join(missing)}",
            fix_hint="run `veles wiki reindex` to regenerate INDEX.md",
        )
    return CheckResult(name="wiki_files", status="ok", message="INDEX.md and LOG.md present")


def _check_trace_health(project: Project | None) -> CheckResult:
    """Tier ε observability surface: file size + cache fragmentation."""
    if project is None:
        return CheckResult(name="trace_health", status="info", message="no active project")
    path = trace_path_for_project(project.state_dir)
    if not path.exists():
        return CheckResult(
            name="trace_health",
            status="info",
            message="no traces.jsonl yet — first `veles run` will create it",
        )
    size = path.stat().st_size
    if size > _TRACES_SIZE_WARN_BYTES:
        return CheckResult(
            name="trace_health",
            status="warn",
            message=f"traces.jsonl is {size // (1024 * 1024)} MB (rotation at 50 MB)",
            fix_hint="rotation is automatic; archive old siblings via cron if needed",
        )
    # Cache-fragmentation alert (M68): >=5 consecutive zero-cache turns.
    records = read_records(path)
    alert = cache_fragmentation_alert(records, min_streak=5)
    if alert is not None:
        return CheckResult(
            name="trace_health",
            status="warn",
            message=(
                "possible cache fragmentation: 5+ turns with stable prompt "
                f"and zero cache_read_tokens (model={alert['models']})"
            ),
            fix_hint="check cache_hints.py wiring; verify provider supports prompt caching",
            details=alert,
        )
    return CheckResult(
        name="trace_health",
        status="ok",
        message=f"traces.jsonl: {size} bytes, {len(records)} records",
        details={"size_bytes": size, "records": len(records)},
    )


def _check_events_health(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(name="events_health", status="info", message="no active project")
    path = project.state_dir / "events.jsonl"
    if not path.exists():
        return CheckResult(
            name="events_health",
            status="info",
            message="no events.jsonl yet",
        )
    size = path.stat().st_size
    if size > _EVENTS_SIZE_WARN_BYTES:
        return CheckResult(
            name="events_health",
            status="warn",
            message=f"events.jsonl is {size // (1024 * 1024)} MB (rotation at 50 MB)",
        )
    return CheckResult(name="events_health", status="ok", message=f"events.jsonl: {size} bytes")


def _check_approval_audit(project: Project | None) -> CheckResult:
    if project is None:
        return CheckResult(name="approval_audit", status="info", message="no active project")
    records = list_approvals(project.state_dir)
    cutoff = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - _AUTOPILOT_REVIEW_WINDOW_S)
    )
    recent = [r for r in records if r.get("decided_at", "") >= cutoff]
    autopilot = [r for r in recent if r.get("via_autopilot") is True]
    if not records:
        return CheckResult(
            name="approval_audit",
            status="info",
            message="no approval records yet",
        )
    if autopilot:
        return CheckResult(
            name="approval_audit",
            status="info",
            message=(
                f"{len(autopilot)} autopilot-granted approvals in the last 7 days; "
                "review periodically"
            ),
            details={"autopilot_count": len(autopilot), "total_recent": len(recent)},
        )
    return CheckResult(
        name="approval_audit",
        status="ok",
        message=f"{len(records)} approvals total, {len(recent)} in last 7 days, all user-granted",
    )


# ---- runner ----


CheckFn = Callable[[], CheckResult] | Callable[[Project | None], CheckResult]


def run_all(project: Project | None) -> DoctorReport:
    """Run every check in fixed order; return aggregated report."""
    no_arg: list[Callable[[], CheckResult]] = [
        _check_python_version,
        _check_user_home,
        _check_user_config,
        _check_provider_keys,
    ]
    project_aware: list[Callable[[Project | None], CheckResult]] = [
        _check_active_project,
        _check_agents_md,
        _check_symlinks,
        _check_wiki_files,
        _check_trace_health,
        _check_events_health,
        _check_approval_audit,
    ]
    results: list[CheckResult] = [c() for c in no_arg]
    results.extend(c(project) for c in project_aware)
    return DoctorReport(results=results)
