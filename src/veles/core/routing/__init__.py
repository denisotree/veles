"""Ensemble routing — task-type → (provider, model) lookup.

Re-exports the public surface from `ensemble`.
"""

from veles.core.routing.ensemble import (
    DEFAULT_TASKS,
    KNOWN_TASKS,
    RoutingConfig,
    effective_route,
    load_routing_config,
    parse_spec,
    provider_to_spec,
    reset_project_route,
    route,
    set_project_route,
)
from veles.core.routing.nl_override import (
    agents_md_sha256,
    load_nl_routing_config,
    load_nl_state,
    make_nl_extractor,
    nl_routing_path,
    nl_state_path,
    refresh_nl_routing,
    save_nl_routing_config,
    save_nl_state,
)

__all__ = [
    "DEFAULT_TASKS",
    "KNOWN_TASKS",
    "RoutingConfig",
    "agents_md_sha256",
    "effective_route",
    "load_nl_routing_config",
    "load_nl_state",
    "load_routing_config",
    "make_nl_extractor",
    "nl_routing_path",
    "nl_state_path",
    "parse_spec",
    "provider_to_spec",
    "refresh_nl_routing",
    "reset_project_route",
    "route",
    "save_nl_routing_config",
    "save_nl_state",
    "set_project_route",
]
