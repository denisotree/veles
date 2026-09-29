"""External memory providers (Tier δ, M55 follow-up).

Providers come from modules: a module calls `api.add_memory_provider(name, factory)`
in `register()`, and `build_extra_providers()` builds whatever `[memory.external.<name>]`
sections the user configured against the factories the currently-loaded modules
registered. Veles core ships no concrete external adapters — see the registry
extensions for those (Honcho, Mem0, Supermemory, ...).
"""

from veles.core.memory.providers.builder import build_extra_providers

__all__ = ["build_extra_providers"]
