"""M77: tiny clipboard layer for the TUI.

Dependency-free — uses platform-native subprocess tools (pbcopy/pbpaste
on macOS, xclip/wl-paste on Linux, Get-Clipboard on Windows). On
unsupported platforms or missing tools, the operations return False /
None so the UI can degrade gracefully.

Image paste is best-effort:
- macOS: osascript writes the clipboard PNG to a temp file.
- Linux: `xclip -selection clipboard -t image/png -o` or `wl-paste --type image/png`.
- Other: not supported (returns False).

Tests inject fake implementations via the module-level singletons.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _which(name: str) -> str | None:
    return shutil.which(name)


# ---------------- text ----------------


def copy_text(text: str) -> bool:
    """Best-effort copy to system clipboard. True on success."""
    if not text:
        return False
    try:
        if sys.platform == "darwin" and _which("pbcopy"):
            return _run_stdin(["pbcopy"], text)
        if sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") and _which("wl-copy"):
                return _run_stdin(["wl-copy"], text)
            if _which("xclip"):
                return _run_stdin(["xclip", "-selection", "clipboard"], text)
            if _which("xsel"):
                return _run_stdin(["xsel", "--clipboard", "--input"], text)
        if sys.platform == "win32":
            return _run_stdin(["clip"], text)
    except OSError:
        return False
    return False


def paste_text() -> str | None:
    """Return clipboard text, or None when empty / unsupported."""
    try:
        if sys.platform == "darwin" and _which("pbpaste"):
            return _run_capture(["pbpaste"])
        if sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") and _which("wl-paste"):
                return _run_capture(["wl-paste", "--no-newline"])
            if _which("xclip"):
                return _run_capture(["xclip", "-selection", "clipboard", "-o"])
            if _which("xsel"):
                return _run_capture(["xsel", "--clipboard", "--output"])
        if sys.platform == "win32" and _which("powershell"):
            return _run_capture(["powershell", "-Command", "Get-Clipboard"])
    except OSError:
        return None
    return None


# ---------------- image ----------------


def paste_image(target: Path) -> bool:
    """Write the clipboard image (PNG) to `target`. Returns True on
    success, False when there's no image in clipboard or tooling missing.
    Creates parent directories as needed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin":
            # AppleScript: try to coerce the clipboard to PNG (`«class PNGf»`).
            # The TID-eval pattern fails silently when the clipboard isn't an
            # image, so we measure success by the resulting file size.
            script = (
                'try\n'
                '  set pngData to (the clipboard as «class PNGf»)\n'
                f'  set fd to open for access POSIX file "{target}" with write permission\n'
                '  set eof of fd to 0\n'
                '  write pngData to fd\n'
                '  close access fd\n'
                'end try'
            )
            subprocess.run(
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                timeout=5,
            )
            return target.exists() and target.stat().st_size > 0
        if sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") and _which("wl-paste"):
                with open(target, "wb") as fh:
                    proc = subprocess.run(
                        ["wl-paste", "--type", "image/png"],
                        stdout=fh,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        check=False,
                    )
                if proc.returncode == 0 and target.stat().st_size > 0:
                    return True
                target.unlink(missing_ok=True)
                return False
            if _which("xclip"):
                with open(target, "wb") as fh:
                    proc = subprocess.run(
                        ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                        stdout=fh,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        check=False,
                    )
                if proc.returncode == 0 and target.stat().st_size > 0:
                    return True
                target.unlink(missing_ok=True)
                return False
    except (OSError, subprocess.SubprocessError):
        return False
    return False


# ---------------- helpers ----------------


def _run_stdin(cmd: list[str], text: str) -> bool:
    try:
        proc = subprocess.run(
            cmd, input=text, encoding="utf-8", check=False, timeout=5
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _run_capture(cmd: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", check=False, timeout=5
        )
        if proc.returncode != 0:
            return None
        return proc.stdout
    except (OSError, subprocess.SubprocessError):
        return None


__all__ = ["copy_text", "paste_image", "paste_text"]
