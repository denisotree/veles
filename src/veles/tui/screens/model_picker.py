"""Pick a model id.

Lists are sourced through `_model_fetcher.fetch_models()`:

- Cloud providers (`openrouter`, `openai`, `gemini`) — live API with a
  24h disk cache; `refresh=True` (mapped from `/model refresh` or
  `veles models … --refresh`) bypasses the cache.
- Local providers (`ollama`, `llamacpp`, `openai-compat`) — always
  live, no cache, so a newly-installed model shows up immediately.
- Everyone else (`anthropic`, `claude-cli`, `gemini-cli`) — curated
  fallback from `cli.repl.model_catalog._CURATED_MODELS_BY_PROVIDER`.

Any live-fetch failure (missing key, network error, malformed response)
collapses to the curated list and is reported via the picker title
suffix (`[live]` / `[cached]` / `[curated]`).
"""

from __future__ import annotations

from veles.tui.screens.base_picker import PickerItem, PickerScreen

_SOURCE_SUFFIX = {
    "live": "[live]",
    "cache": "[cached]",
    "curated": "[curated]",
}


class ModelPickerScreen(PickerScreen[str]):
    def __init__(
        self,
        provider: str,
        current: str | None = None,
        *,
        refresh: bool = False,
    ) -> None:
        from veles.cli.repl.model_fetcher import fetch_models

        result = fetch_models(provider, refresh=refresh)
        items: list[PickerItem[str]] = []
        for model in result.models:
            marker = "* " if model == current else "  "
            items.append(
                PickerItem(
                    label=f"{marker}{model}",
                    haystack=model,
                    value=model,
                )
            )
        suffix = _SOURCE_SUFFIX.get(result.source, f"[{result.source}]")
        title = f"Pick a model for provider {provider!r} {suffix} (Esc to cancel)"
        if result.source == "curated" and not result.models:
            empty_message = (
                f"no models for provider {provider!r}: "
                "no API key, endpoint unreachable, or provider has no listing"
            )
        else:
            empty_message = f"no models match the filter for provider {provider!r}"
        super().__init__(
            title=title,
            items=items,
            empty_message=empty_message,
            placeholder="filter by model id…",
        )
