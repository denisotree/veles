# Providers

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles is provider-agnostic. Pass `--provider <name>` to any agent command, or set
a default in config. Model IDs use the provider's own naming.

| Provider | Kind | API key | Notes |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **Default.** Relays hundreds of models; model IDs like `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | Delegates to a local `claude` CLI in JSON-stream mode |
| `gemini-cli` | Subprocess | — (CLI session) | Delegates to a local `gemini` CLI |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (required, no default) |

Defaults: provider `openrouter`, model `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`.

## Local providers

`ollama`, `llamacpp`, and `openai-compat` need no API key. List installed models
with `veles models <provider>` (always live for local providers).

**Tool calling is off by default** on local providers — many local models emit
malformed tool calls. Enable it once you've picked a tool-capable model:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Override endpoints with the `*_BASE_URL` env vars (see
[environment variables](environment-variables.md)).

## CLI delegation (`claude-cli`, `gemini-cli`)

If you hold a Claude or Gemini CLI subscription, Veles can run the binary in
JSON-streaming mode and act as coordinator — keeping the loop local-first without
a separate API key. Veles tools reach the subprocess only when an MCP bridge is
configured.

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
