"""Natural-language ensemble override in AGENTS.md (M43b).

VISION §5.3 + PLAN.md §3.5.1: ensembles ship as a *typed* TOML config
(M43 — `routing.toml`) *plus* a natural-language override read from
the project's AGENTS.md. The NL flow is intentionally lighter-touch:
the user writes prose like

    ## Models / Routing

    Use Opus for planning and architecture. Default to Sonnet for
    everyday tasks. Haiku is fine for compression and insight
    extraction. Vision queries should go through gpt-4o.

…and a tool-less sub-Agent translates that into structured entries
that land in `<project>/.veles/routing.nl.toml`. The manual TOML
(`routing.toml`, edited via `veles route set`) always wins; NL is
strictly a *fallback* layer in `route()` resolution.

State file `routing.nl.state.json` records the SHA256 of the AGENTS.md
that produced the current NL TOML; the auto-trigger re-runs the
extractor only when the file changes, so a regular `veles run` doesn't
pay an LLM call per turn.

Design notes:

- `find_routing_hints(agents_md)` is a deterministic, LLM-free scan that
  returns the relevant snippets (sections matching `## Routing` /
  `## Models` / `## Ensembles`, plus standalone lines containing keyword
  patterns like `use … for …`). Empty result short-circuits the
  sub-Agent and we write an empty `routing.nl.toml` so resolution
  silently degrades to defaults — matching the VISION §5.3 promise
  that NL override is optional, not mandatory.

- The sub-Agent sees only the snippets, not the full AGENTS.md. Cheaper
  + safer + keeps the LLM's attention on the routing-relevant context.

- `parse_extractor_output(raw)` is JSON-tolerant: strips ```json fences,
  ignores unknown keys, validates task names against `DEFAULT_TASKS`,
  validates provider names against `PROVIDER_API_KEY_ENVS`. Garbage
  entries are dropped silently so a noisy LLM run doesn't poison the
  TOML.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.core.project import Project
from veles.core.routing.ensemble import DEFAULT_TASKS, RoutingConfig, parse_spec

_NL_TOML_FILENAME = "routing.nl.toml"
_NL_STATE_FILENAME = "routing.nl.state.json"

_SECTION_HEADER_RE = re.compile(r"^##+\s+(.*?)\s*$", re.MULTILINE)
_HEADING_KEYWORDS = frozenset(
    {"routing", "models", "model", "ensemble", "ensembles", "llm", "llms"}
)
_INLINE_PATTERNS = (
    re.compile(r"\buse\s+\S+\s+(?:for|to)\b", re.IGNORECASE),
    re.compile(r"\brout(?:e|ing)\b", re.IGNORECASE),
    re.compile(r"\bdefault(?:\s+to|\s+model)\b", re.IGNORECASE),
)

_SYSTEM_PROMPT = """You parse natural-language model routing hints from a project's AGENTS.md into
structured entries. Output STRICT JSON only — no prose, no markdown fences.

Schema:
    {"entries": [{"task": "<one of: default|curator|compressor|insights|skills|advisor|vision>",
                   "provider": "<openrouter|anthropic|openai|gemini|ollama|llamacpp|openai-compat>",
                   "model": "<bare model name or openrouter slug>"}]}

If no actionable hints are present, output exactly: {"entries": []}

Only emit entries you are confident the user actually meant. Skip ambiguous lines.
Skip entries that name a task outside the schema. Skip entries that name a provider you
don't recognise. Do not invent provider names. Do not invent model names.
"""


# ---- hint extraction ----


def find_routing_hints(agents_md: str) -> list[str]:
    """Return AGENTS.md snippets that look routing-related.

    Two passes:
    1. Walk H2/H3 headings; if a heading word is in `_HEADING_KEYWORDS`,
       take the body of the section (until the next heading) as one chunk.
    2. Scan top-level lines that match any `_INLINE_PATTERNS` regex (e.g.
       "use opus for planning"). Stand-alone hints land as one-line
       chunks.

    Empty input or no routing-flavoured content → `[]`.
    """
    if not agents_md or not agents_md.strip():
        return []
    chunks: list[str] = []
    chunks.extend(_extract_keyword_sections(agents_md))
    if not chunks:
        # Heading-less fallback: only scan top-level lines if no obvious section
        # was identified. Avoids double-counting lines already inside a captured
        # section.
        chunks.extend(_extract_inline_lines(agents_md))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        norm = c.strip()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _extract_keyword_sections(text: str) -> list[str]:
    """Sections whose heading contains a routing keyword."""
    matches = list(_SECTION_HEADER_RE.finditer(text))
    out: list[str] = []
    for i, m in enumerate(matches):
        heading_text = m.group(1).lower()
        if not any(kw in heading_text for kw in _HEADING_KEYWORDS):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            out.append(f"## {m.group(1)}\n{body}")
    return out


def _extract_inline_lines(text: str) -> list[str]:
    """Standalone lines matching any inline-hint regex."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(p.search(stripped) for p in _INLINE_PATTERNS):
            out.append(stripped)
    return out


# ---- sub-Agent extractor ----


@dataclass(frozen=True, slots=True)
class _NLEntry:
    task: str
    provider: str
    model: str


_VALID_NL_PROVIDERS = frozenset(
    {
        "openrouter",
        "anthropic",
        "openai",
        "gemini",
        "ollama",
        "llamacpp",
        "openai-compat",
    }
)


def _strip_code_fence(text: str) -> str:
    """Drop a leading ```lang line and trailing ``` from an LLM reply, if present."""
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()


def _coerce_nl_entry(entry: Any, valid_tasks: set[str]) -> _NLEntry | None:
    """Validate one extractor JSON entry; return None on any defect."""
    if not isinstance(entry, dict):
        return None
    task = entry.get("task")
    provider = entry.get("provider")
    model = entry.get("model")
    if not isinstance(task, str) or task not in valid_tasks:
        return None
    if not isinstance(provider, str) or provider not in _VALID_NL_PROVIDERS:
        return None
    if not isinstance(model, str) or not model.strip():
        return None
    return _NLEntry(task=task, provider=provider, model=model.strip())


def parse_extractor_output(raw: str) -> list[_NLEntry]:
    """JSON-tolerant parse of the sub-Agent's reply.

    Strips fenced-code markers (```json / ```), tolerates extra
    whitespace, refuses non-object payloads. Invalid entries (unknown
    task, unknown provider, empty model) are skipped silently so one
    noisy entry doesn't void the whole batch.
    """
    text = _strip_code_fence((raw or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return []
    valid_tasks = set(DEFAULT_TASKS.keys())
    return [entry for entry in (_coerce_nl_entry(e, valid_tasks) for e in raw_entries) if entry]


def make_nl_extractor(*, provider, model: str):
    """Return a callable `(agents_md_text) -> list[_NLEntry]`.

    The sub-Agent is tool-less and capped at one iteration. On any
    failure the function returns `[]` so a flaky parse never blocks
    the parent run.
    """
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    def _extract(agents_md_text: str) -> list[_NLEntry]:
        hints = find_routing_hints(agents_md_text)
        if not hints:
            return []
        snippet = "\n\n".join(hints)[:4_000]
        try:
            sub = Agent(
                provider=provider,
                registry=Registry(),
                model=model,
                max_iterations=1,
                system_prompt=_SYSTEM_PROMPT,
                max_tokens=512,
            )
            result = sub.run(snippet)
        except Exception:
            return []
        return parse_extractor_output(result.text or "")

    return _extract


# ---- nl-config persistence ----


def nl_routing_path(project: Project) -> Path:
    return project.state_dir / _NL_TOML_FILENAME


def nl_state_path(project: Project) -> Path:
    return project.state_dir / _NL_STATE_FILENAME


def load_nl_routing_config(project: Project) -> RoutingConfig:
    """Permissive parse of `routing.nl.toml`. Missing / corrupt → empty."""
    path = nl_routing_path(project)
    if not path.is_file():
        return RoutingConfig()
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return RoutingConfig()
    if not isinstance(data, dict):
        return RoutingConfig()
    routing = data.get("routing")
    if not isinstance(routing, dict):
        return RoutingConfig()
    tasks_raw = routing.get("tasks")
    if not isinstance(tasks_raw, dict):
        return RoutingConfig()
    tasks: dict[str, str] = {}
    for name, spec in tasks_raw.items():
        if isinstance(name, str) and isinstance(spec, str) and ":" in spec:
            tasks[name] = spec
    return RoutingConfig(tasks=tasks)


def save_nl_routing_config(project: Project, config: RoutingConfig) -> None:
    """Atomic write of the NL-derived routing config."""
    project.state_dir.mkdir(parents=True, exist_ok=True)
    path = nl_routing_path(project)
    text = _render_toml(config)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def entries_to_routing_config(entries: list[_NLEntry]) -> RoutingConfig:
    """Convert the sub-Agent's parsed entries into a `RoutingConfig`.

    Later entries for the same task win — matches the LLM intuition
    that the bottom of a paragraph usually overrides the top.
    """
    tasks: dict[str, str] = {}
    for e in entries:
        spec = f"{e.provider}:{e.model}"
        try:
            parse_spec(spec)
        except ValueError:
            continue
        tasks[e.task] = spec
    return RoutingConfig(tasks=tasks)


def _render_toml(config: RoutingConfig) -> str:
    header = (
        "# routing.nl.toml — auto-generated from natural-language hints in AGENTS.md.\n"
        "# Do NOT edit by hand; run `veles route refresh --force` or delete this file\n"
        "# to regenerate. Manual overrides go in routing.toml (via `veles route set`)\n"
        "# and always take precedence over this file.\n\n"
    )
    if not config.tasks:
        return header + "[routing.tasks]\n"
    lines = [header.rstrip() + "\n", "[routing.tasks]"]
    for name in sorted(config.tasks):
        spec = config.tasks[name].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{name} = "{spec}"')
    return "\n".join(lines) + "\n"


# ---- state file ----


@dataclass(slots=True)
class NLRoutingState:
    agents_md_sha256: str = ""
    parsed_at: float = 0.0
    entries_count: int = 0
    error: str | None = field(default=None)


def load_nl_state(project: Project) -> NLRoutingState:
    path = nl_state_path(project)
    if not path.is_file():
        return NLRoutingState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return NLRoutingState()
    if not isinstance(data, dict):
        return NLRoutingState()
    return NLRoutingState(
        agents_md_sha256=str(data.get("agents_md_sha256", "")),
        parsed_at=float(data.get("parsed_at", 0.0) or 0.0),
        entries_count=int(data.get("entries_count", 0) or 0),
        error=data.get("error") if isinstance(data.get("error"), str) else None,
    )


def save_nl_state(project: Project, state: NLRoutingState) -> None:
    project.state_dir.mkdir(parents=True, exist_ok=True)
    path = nl_state_path(project)
    body = {
        "agents_md_sha256": state.agents_md_sha256,
        "parsed_at": state.parsed_at,
        "entries_count": state.entries_count,
    }
    if state.error:
        body["error"] = state.error
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def agents_md_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- top-level driver ----


def refresh_nl_routing(
    project: Project,
    agents_md_text: str,
    *,
    extractor,
    force: bool = False,
) -> NLRoutingState:
    """Run the NL extractor against the current AGENTS.md and persist the result.

    Idempotency:
    - When the AGENTS.md SHA matches the stored state and `force=False`,
      this returns the existing state without invoking the sub-Agent.

    Side effects:
    - Always overwrites `routing.nl.toml` when a parse actually ran.
      Empty results write a TOML with an empty `[routing.tasks]` section
      so `load_nl_routing_config` finds an explicit "nothing here" file
      rather than falling back to defaults silently.
    - Updates `routing.nl.state.json` with the new SHA + timestamp.

    `extractor` is the callable produced by `make_nl_extractor` (or a
    test stub returning `list[_NLEntry]` directly).
    """
    sha = agents_md_sha256(agents_md_text)
    prior = load_nl_state(project)
    if not force and prior.agents_md_sha256 == sha:
        return prior
    entries = extractor(agents_md_text)
    config = entries_to_routing_config(entries)
    save_nl_routing_config(project, config)
    new_state = NLRoutingState(
        agents_md_sha256=sha,
        parsed_at=time.time(),
        entries_count=len(entries),
    )
    save_nl_state(project, new_state)
    return new_state
