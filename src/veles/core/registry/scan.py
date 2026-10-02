"""Static hints for a registry reviewer — never a verdict, never blocking.

Walks every `.py` file and names the lines worth a human look: process execution,
network access, eval/exec and dynamic imports, environment (secrets) reads, and
file writes.
"""

from __future__ import annotations

import ast
from pathlib import Path

_NETWORK = frozenset(
    {"socket", "urllib", "http", "httpx", "requests", "aiohttp", "ftplib", "smtplib", "websockets"}
)
_PROCESS = frozenset({"subprocess", "pty", "multiprocessing"})
_DYNAMIC = frozenset({"eval", "exec", "compile", "__import__"})


def scan_python(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            findings.append(f"{rel}: could not parse ({exc})")
            continue
        for node in ast.walk(tree):
            finding = _classify(node)
            if finding:
                findings.append(f"{rel}:{getattr(node, 'lineno', 0)}: {finding}")
    return findings


_NATIVE_SUFFIXES = (".so", ".pyd", ".dylib", ".dll")


def native_binaries(root: Path) -> list[str]:
    """Compiled libraries in a payload — code a reviewer cannot read."""
    return [
        f"{p.relative_to(root).as_posix()}: native binary (unreviewable code)"
        for p in sorted(root.rglob("*"))
        if p.is_file() and (p.suffix in _NATIVE_SUFFIXES or ".so." in p.name)
    ]


def non_sdk_imports(root: Path) -> list[str]:
    """`<file>:<line> <module>` for every import of Veles outside `veles.sdk` in a
    module's runtime code. Tests are exempt: they run in registry CI against a
    pinned Veles and may build fixtures from internals."""
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/") or path.name.startswith("test_") or path.name == "conftest.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            continue  # `scan_python` already reports it
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found += [f"{rel}:{node.lineno} {n}" for n in names if _outside_sdk(n)]
    return found


def _outside_sdk(name: str) -> bool:
    if name != "veles" and not name.startswith("veles."):
        return False
    return not (name == "veles.sdk" or name.startswith("veles.sdk."))


def _classify(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import | ast.ImportFrom):
        names = (
            [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
        )
        for name in names:
            top = name.split(".")[0]
            if top in _PROCESS:
                return f"process execution ({name})"
            if top in _NETWORK:
                return f"network access ({name})"
            if name == "importlib":
                return "dynamic import (importlib)"
        return None
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in _DYNAMIC:
            return f"dynamic code ({func.id})"
        if isinstance(func, ast.Name) and func.id == "open" and _writes(node):
            return "file write (check the target path)"
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            dotted = f"{func.value.id}.{func.attr}"
            if dotted in {"os.system", "os.popen", "os.execv", "os.spawnv"}:
                return f"process execution ({dotted})"
            if dotted == "os.getenv":
                return "environment read (secrets?)"
        return None
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    ):
        return "environment read (secrets?)"
    return None


def _writes(call: ast.Call) -> bool:
    mode: ast.expr | None = call.args[1] if len(call.args) > 1 else None
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    return (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and any(c in mode.value for c in "wax+")
    )
