"""Agent-ops module (M204): agent-callable command tools, outside the core.

Tools that expose Veles *operations* (scheduling jobs, deep research) to the
agent live here — the invariant is that command tools are module-resident and
pluggable, never baked into `src/veles/core/`. Imported unconditionally by
`_load_skills` (no engine gate: these are agent operations present whenever
the agent runs — unlike the wiki tools, which exist only when the layout pack
enables the wiki content engine).
"""
