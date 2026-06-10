"""Concrete external memory providers (Tier δ, M55 follow-up).

M55 shipped the `MemoryProvider` Protocol and the `MemoryRouter.extra_providers`
wire-up. This sub-package carries the actual adapters: Honcho and Mem0
today, with room for more (Supermemory, a corporate KB, ...) on the same
pattern.

Every adapter follows the same rules:
  - Lazy SDK import — `pip install honcho-ai` / `mem0ai` is the user's
    decision. We only attempt the import when `recall()` is first called.
  - Soft failure — ImportError, auth error, or network error → empty
    `list[RecallHit]`. A broken external provider must not block the
    project's primary recall (wiki + turns).
  - No magic ENV reads at module import time — the factory in
    `builder.py` reads config and constructs providers explicitly.
"""

from veles.core.memory.providers.builder import build_extra_providers
from veles.core.memory.providers.honcho import HonchoMemoryProvider
from veles.core.memory.providers.mem0 import Mem0MemoryProvider
from veles.core.memory.providers.supermemory import SupermemoryProvider

__all__ = [
    "HonchoMemoryProvider",
    "Mem0MemoryProvider",
    "SupermemoryProvider",
    "build_extra_providers",
]
