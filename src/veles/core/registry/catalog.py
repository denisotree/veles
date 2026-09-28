"""What the connected registries offer: search and name resolution over the local clones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from veles.core.registry.config import RegistryConfigError, cache_dir, get_source, list_sources
from veles.core.registry.model import Extension, scan_registry
from veles.core.registry.repo import RegistryRepoError, ensure_cache, head_commit


@dataclass(frozen=True, slots=True)
class Found:
    registry: str
    ext: Extension
    commit: str
    root: Path

    @property
    def ref(self) -> str:
        return f"{self.registry}:{self.ext.group}/{self.ext.name}"


class ResolveError(LookupError):
    pass


def available(
    *, registry: str | None = None, sync_missing: bool = True
) -> tuple[list[Found], list[str]]:
    """Every extension in the connected registries, plus warnings for the unreadable ones.

    `sync_missing=False` never touches the network: a registry that was never cloned
    is reported as a warning instead."""
    if registry is not None:
        try:
            sources = [get_source(registry)]
        except RegistryConfigError as exc:
            raise ResolveError(str(exc)) from exc
    else:
        sources = list_sources()
    found: list[Found] = []
    warnings: list[str] = []
    for source in sources:
        if sync_missing:
            try:
                root = ensure_cache(source)
            except RegistryRepoError as exc:
                warnings.append(f"{source.name}: {exc}")
                continue
        else:
            root = cache_dir(source.name)
            if not (root / ".git").is_dir():
                warnings.append(f"{source.name}: not fetched yet — run `veles registry update`")
                continue
        commit = head_commit(root)
        entries, errors = scan_registry(root)
        warnings.extend(f"{source.name}: {path}: {msg}" for path, msg in errors)
        found.extend(Found(source.name, ext, commit, root) for ext in entries)
    return found, warnings


def search(
    query: str = "",
    *,
    kind: str | None = None,
    registry: str | None = None,
    sync_missing: bool = True,
) -> tuple[list[Found], list[str]]:
    found, warnings = available(registry=registry, sync_missing=sync_missing)
    needle = query.strip().lower()

    def matches(f: Found) -> bool:
        if kind is not None and f.ext.kind != kind:
            return False
        haystack = " ".join((f.ext.name, f.ext.description, *f.ext.tags)).lower()
        return needle in haystack

    return [f for f in found if matches(f)], warnings


def resolve(spec: str) -> Found:
    """`name`, `group/name`, `registry:name` or `registry:group/name` → the one matching
    extension.

    A bare `name` is ambiguous whenever more than one registry — or, within one registry,
    more than one group — has an extension by that name (the latter is a state `validate`
    forbids for a published registry, but `resolve` must still disambiguate it: e.g. a
    locally-authored registry not yet validated). `group/name` or `registry:group/name`
    (the `ref` a search result prints) disambiguates either case.
    """
    registry, _, rest = spec.rpartition(":")
    group, sep, name = rest.rpartition("/")
    found, warnings = available(registry=registry or None)

    def _matches(f: Found) -> bool:
        return f.ext.name == name and (not sep or f.ext.group == group)

    matches = [f for f in found if _matches(f)]
    if not matches:
        where = f" in registry {registry!r}" if registry else ""
        label = f"{group}/{name}" if sep else name
        message = (
            f"no extension named {label!r}{where} (try `veles registry update`, then `search`)"
        )
        if warnings:
            message += "; unreachable: " + "; ".join(warnings)
        raise ResolveError(message)
    if len(matches) > 1:
        refs = ", ".join(f.ref for f in matches)
        raise ResolveError(f"{name!r} is ambiguous: {refs} — use one of these refs")
    return matches[0]
