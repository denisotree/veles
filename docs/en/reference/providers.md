# Providers

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles is provider-agnostic. Pass `--provider <id>` to any agent command, or set
a default in config. Model IDs use the provider's own naming.

## The provider catalogue

Every provider Veles knows is an entry in one catalogue, built from three sources:

1. **Builtin** — the table below, shipped with Veles.
2. **Yours** — `~/.veles/providers.toml`: a hosted OpenAI-compatible API or a server
   you run, by adding an entry (see
   [add your own provider](../how-to/configure-providers.md#add-your-own-provider)).
   An entry with a builtin id overrides that provider's settings (its `base_url`, say).
3. **Modules** — a registry module contributes a provider (`antigravity-cli`). Naming
   one in `[engine] provider`, a route or `--provider` installs it from your connected
   registries on the next run, like a declared channel.

`--provider`, `veles models`, the setup wizards, routing and `veles doctor` all read the
catalogue, so a provider from any source works everywhere a builtin does. An unknown
id is a one-line error listing what exists; `veles doctor` also checks
`~/.veles/providers.toml` and every provider your routes name.

| Provider | Kind | API key | Notes |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **Default.** Relays hundreds of models; model IDs like `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegate | — (CLI session) | Delegates to a local `claude` CLI in JSON-stream mode |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | optional `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (required, no default) |

`gemini-cli` was removed in 1.2.6 — Google no longer serves the Gemini CLI to personal
accounts. Use `gemini` with an API key, or the `antigravity-cli` module.

Default provider: `openrouter`. There is **no hardcoded default model** — set one
via the setup wizard, `[engine] model`, or `--model` (otherwise the agent reports
"no model configured"). Per-task routes inherit `[engine]` as their base unless
overridden in `[routing.tasks]` — see [per-task routing](../how-to/per-task-routing.md).

## Local providers

`ollama`, `llamacpp`, and `openai-compat` need no API key. List installed models
with `veles models <provider>` (always live for local providers).

**Tool calling is detected** from what the backend advertises: ollama reports each
model's capabilities, a llama.cpp server its chat template's. `VELES_LOCAL_TOOLS=1`
forces tool calling on, `=0` off; unset means detect.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Override endpoints with the `*_BASE_URL` env vars (see
[environment variables](environment-variables.md)).

## CLI delegation (`claude-cli`, `antigravity-cli`)

If you hold a Claude or Google subscription, Veles can run its CLI headless and act
as coordinator — no separate API key. `claude-cli` is builtin; `antigravity-cli`
(the `agy` CLI) is a registry module that installs itself when you name it.

The delegate is only the model: Veles' tools reach it over an MCP bridge, and every
call goes through Veles' trust ladder. The bridge's config lives in a directory of
the running process, `.veles/tmp/delegate-<pid>/`, removed when it exits. `agy` runs
in a scratch workspace outside your project (under `~/.veles/tmp/`), so the project's
own `.agents/` config never reaches it, behind a gate that denies its own shell and
file tools.

## Multimodal status (vision / speech-to-text)

Veles defines a `VisionAdapter` and an STT adapter protocol (`modules/vision.py`,
`modules/stt.py`) plus a process-global registry, **but no concrete adapter ships
and nothing registers one at daemon startup**. So a photo or voice message sent to
a channel currently returns a "not configured" notice rather than being analysed.
The `vision` routing task exists for when an adapter is wired. See
[connect Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Choosing a model

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

To use different models for different jobs (cheap for compression, strong for
planning), see [per-task routing](../how-to/per-task-routing.md).
