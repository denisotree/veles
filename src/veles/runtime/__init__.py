"""What every front end (CLI, REPL, daemon, modules) needs to run an agent.

Sits above `core` and below the front ends:

- `prompt` — the system prompt (identity, AGENTS.md, rules, recall, …);
- `registry` — the run's tools and skills, and a provider that can call them;
- `run` — the history compressor, the token budget and the run itself;
- `learning` — the post-turn learning steps (curator, insights, proposer, …).
"""
