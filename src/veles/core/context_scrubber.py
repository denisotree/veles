"""Strip `<memory-context>...</memory-context>` blocks from assistant output.

M22 injects a `<memory-context>` block into the system prompt to surface
recalled wiki pages. If the model echoes any part of that markup back
into its reply (rewrite-style tasks, or just confused output), the tag
ends up in `Message.content`, gets persisted, and on the next turn the
prompt builder appends *another* `<memory-context>` — so the original
echoed markup now sits inside the cache-stable prefix and the model
sees a self-injected sentinel block. The scrubber removes such echoes
before persistence so the leak can't bootstrap.

Two surfaces:
- `scrub_text(text)` — one-shot for fully-collected provider responses.
- `MemoryContextScrubber` — stateful, for streaming. `feed(chunk)`
  returns the prefix that's safe to forward; partial tags at the chunk
  boundary stay buffered until the next call. `finalize()` flushes any
  trailing buffer; if a `<memory-context>` open never closed before the
  stream ended, everything from the open onward is dropped.
"""

from __future__ import annotations

import re

OPEN_TAG = "<memory-context>"
CLOSE_TAG = "</memory-context>"

_BLOCK_RE = re.compile(re.escape(OPEN_TAG) + r".*?" + re.escape(CLOSE_TAG), re.DOTALL)


def scrub_text(text: str) -> str:
    """Remove every `<memory-context>...</memory-context>` block.

    A trailing unclosed `<memory-context>` opener and everything after
    it is also stripped — the model never finished writing the block,
    so emitting the prefix would still leak the sentinel.
    """
    if not text:
        return text
    cleaned = _BLOCK_RE.sub("", text)
    open_idx = cleaned.rfind(OPEN_TAG)
    if open_idx >= 0:
        cleaned = cleaned[:open_idx]
    return cleaned


def _longest_prefix_match(buf: str, marker: str) -> int:
    """Return length of longest suffix of `buf` that is a prefix of `marker`.

    Used to decide how many trailing chars of the buffer must stay
    pending because they could still complete the marker on the next
    chunk. Bounded by `len(marker) - 1`.
    """
    max_check = min(len(buf), len(marker) - 1)
    for n in range(max_check, 0, -1):
        if marker.startswith(buf[-n:]):
            return n
    return 0


class MemoryContextScrubber:
    """Streaming-safe stripper. Construct one per stream; reuse across feeds."""

    __slots__ = ("_buf", "_inside")

    def __init__(self) -> None:
        self._buf: str = ""
        self._inside: bool = False

    def feed(self, chunk: str) -> str:
        """Append `chunk`, return the prefix that's safe to emit now."""
        if not chunk:
            return ""
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._inside:
                idx = self._buf.find(CLOSE_TAG)
                if idx >= 0:
                    self._buf = self._buf[idx + len(CLOSE_TAG) :]
                    self._inside = False
                    continue
                keep = _longest_prefix_match(self._buf, CLOSE_TAG)
                self._buf = self._buf[-keep:] if keep else ""
                break
            idx = self._buf.find(OPEN_TAG)
            if idx >= 0:
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(OPEN_TAG) :]
                self._inside = True
                continue
            keep = _longest_prefix_match(self._buf, OPEN_TAG)
            if keep:
                out.append(self._buf[:-keep])
                self._buf = self._buf[-keep:]
            else:
                out.append(self._buf)
                self._buf = ""
            break
        return "".join(out)

    def finalize(self) -> str:
        """Flush remaining buffer once the stream is complete.

        Inside an unclosed `<memory-context>` block: drop everything (the
        block was incomplete and would re-leak on next-turn injection).
        Outside: emit the buffer literally — partial-open prefixes turn
        out to be regular text in retrospect.
        """
        if self._inside:
            self._buf = ""
            self._inside = False
            return ""
        out = self._buf
        self._buf = ""
        return out
