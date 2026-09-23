"""Agent-run assembly shared by every front end (CLI, REPL, daemon, modules).

Sits above `core` and below the front ends: `assembly` builds what a run needs
(system prompt, compressor, skills registry, tool-aware provider, token budget);
`learning` holds the post-turn learning hooks (curator, insights, proposer, …).
"""
