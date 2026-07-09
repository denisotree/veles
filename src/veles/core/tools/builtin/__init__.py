"""Builtin tools — imported for their @tool registration side effects.

Wiki tools are NOT registered here: they live in the wiki content-engine
module (`veles.modules.wiki.tools`) and register lazily at agent-build time
only when the project's layout enables the wiki engine (`_load_skills` in
cli/_runtime.py). A non-wiki project never imports the wiki module.

Agent-ops command tools (job_add/job_list/job_remove — M204) are NOT here
either: they live in `veles.modules.agentops.tools` (module-resident by
invariant) and are imported unconditionally by `_load_skills`.
"""

from veles.core.tools.builtin import (  # noqa: F401
    advisor,
    ask_user,
    delegate,
    edit_file,
    fetch_url,
    file_ops,
    image,
    list_files,
    memory_query,
    memory_save,
    pdf,
    plan_tool,
    read_file,
    run_shell,
    search_files,
    stat_file,
    task_tools,
    veles_help,
    web_search,
    write_file,
)
