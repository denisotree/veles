---
title: Providers and the provider catalogue
topics: [provider, providers, catalogue, model, key, groq, deepseek, local, antigravity, agy, claude-cli]
related: ["cmd:models", "cmd:secret"]
---

Every provider is an entry in one catalogue: the builtin ones (openrouter,
anthropic, openai, gemini, claude-cli, codex, ollama, llamacpp, openai-compat), the
user's `~/.veles/providers.toml`, and providers that registry modules contribute.
`--provider`, `veles models`, routing and the wizards all read it.

To add a hosted OpenAI-compatible API (Groq, DeepSeek, Mistral, …) or a server the
user runs (LM Studio, vLLM), add an entry to `~/.veles/providers.toml`:
`[providers.<id>]` with `kind = "openai-api"` or `"local"`, `base_url`, and
`key_env = ["<VAR>"]`; store the key with `veles secret set <VAR>`.

`codex` drives the Codex CLI on a ChatGPT subscription (log in once with `codex
login`; `veles models codex` lists your models). `antigravity-cli` (the `agy` CLI, a
Google subscription) is a registry module:
naming it in `[engine] provider`, a route or `--provider` installs it. `gemini-cli`
was removed in 1.2.6.

Example: `veles models groq` after adding a `[providers.groq]` entry.
