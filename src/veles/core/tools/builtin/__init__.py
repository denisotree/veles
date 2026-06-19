"""Builtin tools — imported for their @tool registration side effects."""

# Wiki tools live in the wiki content-engine module (extracted from core,
# 2026-06-19); import for their @tool registration side effect. The toolset
# gating (`engine-wiki`) still hides them for non-wiki layouts.
import veles.modules.wiki.tools  # noqa: F401
from veles.core.tools.builtin import (  # noqa: F401
    advisor,
    ask_user,
    edit_file,
    fetch_url,
    image,
    job_tools,
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
    web_search,
    write_file,
)
