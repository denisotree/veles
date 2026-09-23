"""`---`-delimited frontmatter for Veles markdown files (SKILL.md, notes, layout ops).

The parser is a deliberate flat-key subset of YAML — strings, ints, bools,
null, inline lists, and one nesting level of list-of-dicts — so no YAML
dependency is needed.
"""

from __future__ import annotations

from typing import Any


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Returns ({}, text) if no frontmatter.

    Supports flat key-value pairs plus a single nesting level: a top-level key
    whose value is empty opens a list-of-dicts context; subsequent indented
    `- key: value` lines become list items (each a dict), and further indented
    `key: value` lines fill the most recent dict.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm: dict[str, Any] = {}
    body_start: int | None = None
    current_list_key: str | None = None
    current_dict: dict[str, Any] | None = None

    for i in range(1, len(lines)):
        raw_line = lines[i]
        if raw_line.strip() == "---":
            body_start = i + 1
            break
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = raw_line.lstrip()

        if indent == 0:
            current_list_key = None
            current_dict = None
            if ":" not in stripped:
                continue
            key, _, raw_val = stripped.partition(":")
            key = key.strip()
            raw_val = raw_val.strip()
            if not raw_val:
                # Open a list-of-dicts context for the next indented lines.
                current_list_key = key
                fm[key] = []
                continue
            fm[key] = _coerce_value(raw_val)
            continue

        if current_list_key is None:
            continue
        if stripped.startswith("- "):
            current_dict = {}
            fm[current_list_key].append(current_dict)
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                k, _, v = rest.partition(":")
                current_dict[k.strip()] = _coerce_value(v.strip())
        elif current_dict is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            current_dict[k.strip()] = _coerce_value(v.strip())

    if body_start is None:
        return {}, text
    body = "\n".join(lines[body_start:]).lstrip("\n")
    return fm, body


def render_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Canonical text with `---`-delimited frontmatter. Lists-of-dicts render as
    indented blocks; everything else stays on one line."""
    out = ["---"]
    for key, value in fm.items():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            out.append(f"{key}:")
            for item in value:
                first = True
                for k, v in item.items():
                    prefix = "  - " if first else "    "
                    out.append(f"{prefix}{k}: {_format_value(v)}")
                    first = False
            continue
        out.append(f"{key}: {_format_value(value)}")
    out.append("---")
    out.append("")
    out.append(body.lstrip("\n"))
    return "\n".join(out)


def _coerce_value(raw: str) -> Any:
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        items = [item.strip() for item in inner.split(",") if item.strip()]
        return [_coerce_scalar(it) for it in items]
    return _coerce_scalar(raw)


def _coerce_scalar(raw: str) -> Any:
    s = raw.strip()
    if not s:
        return ""
    lower = s.lower()
    if lower == "null":
        return None
    if lower in ("true", "false"):
        return lower == "true"
    if s.lstrip("-").isdigit():
        return int(s)
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    return str(value)


__all__ = ["parse_frontmatter", "render_frontmatter"]
