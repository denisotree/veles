"""The LLM provider catalogue (M299, release E).

Three sources, merged by provider id, in this order:

- `core/providers.toml`, shipped with Veles — the builtin providers;
- `~/.veles/providers.toml` — the user adds `openai-api` / `local` entries and
  may override a builtin entry's settings (never its kind);
- modules — `api.contribute("provider", "<id>", ProviderSpec(...))`; a builtin
  id is refused at load, an id the user file defines is skipped.

A project has no catalogue of its own: a cloned repository could otherwise point
the user's key at a base URL of its choosing. Models are not stored here — the
model list of a provider is fetched live (`cli/repl/model_fetcher.py`).
"""

from __future__ import annotations

import functools
import logging
import os
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from veles.core.project import Project
    from veles.core.provider import Provider

logger = logging.getLogger(__name__)

Wire = Literal["openai-wire", "anthropic-wire", "gemini-wire", "cli", "other"]
ModelList = Literal["cached", "live", "curated"]

_BUILTIN_TOML = Path(__file__).with_name("providers.toml")


@dataclass(frozen=True, slots=True)
class ProviderContext:
    """What a spec's `build` gets: the provider id, the run's model (a local
    backend probes tool support per model) and the active project."""

    name: str
    model: str | None = None
    project: Project | None = None


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One provider. `build` makes a chat-only provider; `build_tool_aware` (a CLI
    delegate) one that reaches Veles tools over MCP. `wire` tells vision and
    embeddings which client to build; `model_list` how `veles models` lists."""

    label: str
    build: Callable[[ProviderContext], Provider]
    tagline: str = ""
    key_env: tuple[str, ...] = ()
    key_required: bool = True
    wire: Wire = "other"
    base_url: str | None = None
    base_url_env: str | None = None
    model_list: ModelList = "curated"
    build_tool_aware: Callable[[ProviderContext], Provider] | None = None

    @property
    def needs_key(self) -> bool:
        return bool(self.key_env) and self.key_required

    def effective_base_url(self) -> str | None:
        env = os.environ.get(self.base_url_env) if self.base_url_env else None
        return env or self.base_url


# Ids that once named a provider. Naming one gives this line, not "unknown".
RETIRED: dict[str, str] = {
    "gemini-cli": (
        "the gemini-cli provider was removed in 1.2.6 — Google no longer serves the "
        "Gemini CLI to personal accounts; use `gemini` with GEMINI_API_KEY, or "
        "`antigravity-cli`"
    ),
}

_warned: set[str] = set()
_user_cache: dict[str, Any] = {}


def _warn_once(message: str) -> None:
    if message not in _warned:
        _warned.add(message)
        logger.warning(message)


@functools.cache
def _builtin_entries() -> dict[str, dict[str, Any]]:
    with _BUILTIN_TOML.open("rb") as fh:
        return dict(tomllib.load(fh).get("providers", {}))


def builtin_ids() -> frozenset[str]:
    return frozenset(_builtin_entries())


def user_catalog_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "providers.toml"


def _user_entries() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """The user file's entries and what is wrong with it; cached by mtime."""
    path = user_catalog_path()
    try:
        st = path.stat()
    except OSError:
        return {}, []
    key = (str(path), st.st_mtime_ns, st.st_size)
    if _user_cache.get("key") == key:
        return _user_cache["entries"], _user_cache["problems"]
    problems: list[str] = []
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh).get("providers", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"{path}: {exc} — using the builtin providers only")
        raw = {}
    if not isinstance(raw, dict):  # `[[providers]]`: an array, not a table of tables
        problems.append(f"{path}: [providers] must be tables like [providers.<id>]; ignored")
        raw = {}
    entries = {n: e for n, e in raw.items() if isinstance(e, dict)}
    problems += [f"{path}: [providers.{n}] is not a table" for n in raw if n not in entries]
    _user_cache.update(key=key, entries=entries, problems=problems)
    return entries, problems


def _entries() -> tuple[dict[str, dict[str, Any]], list[str]]:
    from veles.core.provider_kinds import USER_KINDS

    merged = {n: dict(e) for n, e in _builtin_entries().items()}
    user, problems = _user_entries()
    problems = list(problems)
    for name, entry in user.items():
        if name in merged:
            merged[name].update({k: v for k, v in entry.items() if k != "kind"})
        elif entry.get("kind") in USER_KINDS:
            merged[name] = dict(entry)
        else:
            problems.append(
                f"{user_catalog_path()}: [providers.{name}] kind {entry.get('kind')!r} — a "
                f"user entry is one of {', '.join(sorted(USER_KINDS))}; skipped"
            )
    return merged, problems


def _spec_from_entry(name: str, entry: dict[str, Any]) -> ProviderSpec | None:
    from veles.core.provider_kinds import KINDS

    kind = KINDS.get(str(entry.get("kind")))
    if kind is None:
        _warn_once(f"provider {name!r}: unknown kind {entry.get('kind')!r}; skipped")
        return None
    key_env = entry.get("key_env", ())
    if isinstance(key_env, str):
        key_env = (key_env,)
    if not isinstance(key_env, list | tuple) or not all(isinstance(e, str) for e in key_env):
        _warn_once(f"provider {name!r}: key_env must be a name or a list of names; skipped")
        return None
    return ProviderSpec(
        label=str(entry.get("label") or name),
        tagline=str(entry.get("tagline") or ""),
        build=functools.partial(kind.build, entry),
        key_env=tuple(str(e) for e in key_env),
        key_required=kind.key_required,
        wire=kind.wire,
        base_url=entry.get("base_url"),
        base_url_env=entry.get("base_url_env"),
        model_list=kind.model_list,
        build_tool_aware=(
            functools.partial(kind.build_tool_aware, entry) if kind.build_tool_aware else None
        ),
    )


def catalog() -> dict[str, ProviderSpec]:
    """Every provider, in wizard order: builtin, the user's, then modules'."""
    from veles.core.contributions import contributions

    entries, problems = _entries()
    for message in problems:
        _warn_once(message)
    specs: dict[str, ProviderSpec] = {}
    for name, entry in entries.items():
        spec = _spec_from_entry(name, entry)
        if spec is not None:
            specs[name] = spec
    for c in contributions("provider"):
        if c.name in specs:
            _warn_once(
                f"module {c.module!r}: provider {c.name!r} is defined in "
                f"{user_catalog_path()} — the user entry wins"
            )
            continue
        if isinstance(c.obj, ProviderSpec):  # the point checks it; this narrows the type
            specs[c.name] = c.obj
    return specs


def list_providers() -> list[str]:
    return list(catalog())


def find_provider(name: str) -> ProviderSpec | None:
    return catalog().get(name)


def get_provider(name: str) -> ProviderSpec:
    specs = catalog()
    if name not in specs:
        raise KeyError(f"no provider {name!r}; available: {', '.join(specs)}")
    return specs[name]


def is_cli_provider(name: str) -> bool:
    spec = find_provider(name)
    return spec is not None and spec.wire == "cli"


def tui_label(name: str) -> str:
    """'<label> (<tagline>)' for the first-run wizard; plain label without one."""
    spec = get_provider(name)
    return f"{spec.label} ({spec.tagline})" if spec.tagline else spec.label


def user_catalog_problems() -> list[str]:
    """What is wrong with ~/.veles/providers.toml: parse errors, a kind a user
    entry can't use, an `openai-api` entry without `base_url`."""
    problems = _entries()[1]
    user, _ = _user_entries()
    problems += [
        f"{user_catalog_path()}: [providers.{n}] has no base_url"
        for n, e in user.items()
        if e.get("kind") == "openai-api" and not e.get("base_url")
    ]
    return problems


def openai_wire_endpoint(name: str) -> tuple[str, str]:
    """`(base_url, api_key)` of an OpenAI-wire provider — vision and embeddings
    build their own SDK client from it. Never the SDK's default URL: a key for one
    company must not reach another's endpoint."""
    from veles.core.provider_factory import require_api_key, resolve_api_key

    spec = get_provider(name)
    if spec.wire != "openai-wire":
        raise ValueError(f"provider {name!r} does not speak the OpenAI wire format")
    url = spec.effective_base_url()
    if url is None:
        hint = spec.base_url_env or "base_url in ~/.veles/providers.toml"
        raise ValueError(f"{name} has no base_url — set {hint}")
    if spec.needs_key:
        return url, require_api_key(name)
    return url, resolve_api_key(name) or "local"  # the SDK insists on a non-empty key


__all__ = [
    "RETIRED",
    "ModelList",
    "ProviderContext",
    "ProviderSpec",
    "Wire",
    "builtin_ids",
    "catalog",
    "find_provider",
    "get_provider",
    "is_cli_provider",
    "list_providers",
    "openai_wire_endpoint",
    "tui_label",
    "user_catalog_path",
    "user_catalog_problems",
]
