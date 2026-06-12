"""Compose the active rule set from three sources, in order of
precedence (lower wins on overlap):

1. Built-in rules from `builtin.py`.
2. User-global TOML at `~/.veles/sanitize.toml`.
3. Project-local TOML at `<project>/.veles/sanitize.toml`.

The composed `RuleSet` is cached per project (LRU, small) — most Veles
processes serve one project for their entire lifetime, so the first
sanitize call pays the disk read and every subsequent one is a tight
loop over already-compiled rules.

TOML schema (both files share it):

    [[rule]]
    type = "literal"          # or "regex"
    pattern = "AKIA[A-Z0-9]{16}"
    replacement = "AKIA<redacted>"

Malformed entries are logged and skipped rather than crashing — a
broken local rule must not take the agent down. A missing file is not
an error.
"""

from __future__ import annotations

import logging
import threading
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from veles.core.project import Project
from veles.core.sanitize.builtin import builtin_rules
from veles.core.sanitize.rule import LiteralRule, RegexRule, Rule, RuleSet

logger = logging.getLogger(__name__)

_GLOBAL_CONFIG_REL = Path(".veles") / "sanitize.toml"
_PROJECT_CONFIG_REL = Path(".veles") / "sanitize.toml"
_lock = threading.Lock()


def _global_config_path() -> Path:
    return Path.home() / _GLOBAL_CONFIG_REL


def _project_config_path(project_root: Path) -> Path:
    return project_root / _PROJECT_CONFIG_REL


def _parse_toml_rules(path: Path) -> list[Rule]:
    if not path.is_file():
        return []
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning("sanitize: cannot read %s: %s", path, exc)
        return []
    raw_rules = data.get("rule") or []
    if not isinstance(raw_rules, list):
        logger.warning("sanitize: %s — `rule` must be an array of tables", path)
        return []
    out: list[Rule] = []
    for i, raw in enumerate(raw_rules):
        rule = _build_rule_from_dict(raw, source=f"{path}#{i}")
        if rule is not None:
            out.append(rule)
    return out


def _build_rule_from_dict(raw: Any, source: str) -> Rule | None:
    if not isinstance(raw, dict):
        logger.warning("sanitize: %s — rule entry is not a table", source)
        return None
    rule_type = raw.get("type", "literal")
    pattern = raw.get("pattern")
    replacement = raw.get("replacement", "")
    if not isinstance(pattern, str) or not pattern:
        logger.warning("sanitize: %s — missing/empty `pattern`", source)
        return None
    if not isinstance(replacement, str):
        logger.warning("sanitize: %s — `replacement` must be a string", source)
        return None
    name = raw.get("name") or f"user:{source}"
    if rule_type == "literal":
        return LiteralRule(name=name, pattern=pattern, replacement=replacement)
    if rule_type == "regex":
        return RegexRule.build(name, pattern, replacement)
    logger.warning("sanitize: %s — unknown `type` %r (expected literal|regex)", source, rule_type)
    return None


# LRU keyed by `(project_name, project_root_str)` so a `None` project
# and a real project don't collide. project_root is part of the key
# because two different projects can share a name in pathological
# multi-project setups.
@lru_cache(maxsize=8)
def _load_cached(project_name: str | None, project_root_str: str | None) -> RuleSet:
    project_root = Path(project_root_str) if project_root_str else None
    rules: list[Rule] = []
    rules.extend(builtin_rules(project_name, project_root))
    rules.extend(_parse_toml_rules(_global_config_path()))
    if project_root is not None:
        rules.extend(_parse_toml_rules(_project_config_path(project_root)))
    return RuleSet(rules)


def load_rules(project: Project | None) -> RuleSet:
    """Return the active rule set for `project` (or context-free if None).

    Thread-safe by the LRU's own internals; we wrap the call in a lock
    just to keep cache-clear and cache-fill from racing on shutdown."""
    with _lock:
        if project is None:
            return _load_cached(None, None)
        return _load_cached(project.name, str(project.root.resolve()))


def clear_cache() -> None:
    """Drop the cached rule sets. Call when the active project changes
    or a TOML file is edited mid-process."""
    with _lock:
        _load_cached.cache_clear()
