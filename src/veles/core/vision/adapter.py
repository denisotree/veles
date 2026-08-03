"""Provider-backed vision adapter (M226).

Before this, `modules/vision.get_vision_adapter()` was an empty registry:
core shipped no implementation, so every photo a channel received hit the
"no vision adapter is configured" notice even when the project's own
model could see perfectly well.

The default is now zero-config: the adapter describes the image with the
model the project already routes `vision` to, which with no explicit
route is the `[engine]` model itself. Flexibility comes from
`[vision]` in `.veles/config.toml`:

    [vision]
    mode = "model"                  # model (default) | ocr | ocr+model | off
    model = "openrouter:z-ai/glm-4.6v"   # optional pin, else route("vision")
    ocr_lang = "rus+eng"
    prompt = "Describe this image…"       # optional

Pick `model` when the engine is multimodal, pin `model =` when it isn't
(a cloud vision model, or a local llava/qwen-vl via ollama), `ocr+model`
for scans and screenshots where verbatim text matters, `ocr` for a
purely local/free pipeline, `off` to keep images out of the LLM entirely
(the channel then just saves the file and lets the agent decide).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from veles.core.project import Project
from veles.core.vision.backends import OCRUnavailable, describe, ocr_bytes
from veles.modules.vision import VisionError

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Describe this image. List visible text verbatim, then summarise "
    "the scene / diagram / chart content in 3-5 short sentences."
)
_MODES = ("model", "ocr", "ocr+model", "off")
_OUTPUT_CAP = 32_000


@dataclass(frozen=True, slots=True)
class VisionSettings:
    mode: str = "model"
    spec: str | None = None  # "<provider>:<model>"; None → route("vision", project)
    ocr_lang: str = "eng"
    prompt: str = DEFAULT_PROMPT

    @property
    def uses_ocr(self) -> bool:
        return self.mode in ("ocr", "ocr+model")

    @property
    def uses_model(self) -> bool:
        return self.mode in ("model", "ocr+model")


def load_vision_settings(project: Project) -> VisionSettings:
    """Read `[vision]` from the project config, falling back to the user
    config so one `~/.veles/config.toml` can set the house default. An
    unknown `mode` warns and behaves as `model` — a typo must not make
    images silently disappear."""
    from veles.core.project_config import get_section, load_project_config
    from veles.core.user_config import get_user_section

    project_section = get_section(load_project_config(project), "vision")
    merged: dict = {**get_user_section("vision"), **project_section}
    mode = str(merged.get("mode") or "model").strip().lower()
    if mode not in _MODES:
        logger.warning("[vision] mode=%r is not one of %s — using 'model'", mode, list(_MODES))
        mode = "model"
    spec = merged.get("model")
    prompt = merged.get("prompt")
    return VisionSettings(
        mode=mode,
        spec=str(spec) if spec else None,
        ocr_lang=str(merged.get("ocr_lang") or "eng"),
        prompt=str(prompt) if prompt else DEFAULT_PROMPT,
    )


@dataclass(slots=True)
class RoutedVisionAdapter:
    """`VisionAdapter` over the project's own routing + OCR.

    Resolution happens per call, not at construction: `veles route set
    vision …` and config edits take effect without restarting the daemon,
    and a project whose vision model is temporarily unreachable recovers
    on the next photo."""

    project: Project
    settings: VisionSettings
    name: str = "routed"

    def describe_image(self, image_bytes: bytes, mime: str) -> str:
        chunks: list[str] = []
        if self.settings.uses_ocr:
            try:
                text = ocr_bytes(image_bytes, self.settings.ocr_lang)
            except OCRUnavailable as exc:
                # A missing tesseract must not kill the model pass.
                logger.warning("vision: OCR unavailable (%s)", exc)
                if not self.settings.uses_model:
                    raise VisionError(str(exc)) from exc
            else:
                if text:
                    chunks.append(f"[image text (OCR)]\n{text}")
        if self.settings.uses_model:
            chunks.append(self._model_pass(image_bytes, mime))
        combined = "\n\n".join(c for c in chunks if c.strip())
        if not combined:
            raise VisionError("vision produced no text for this image")
        return _truncate(combined)

    def _model_pass(self, image_bytes: bytes, mime: str) -> str:
        provider_name, model = self._resolve_route()
        try:
            text = describe(provider_name, model, image_bytes, mime, self.settings.prompt)
        except ValueError as exc:  # provider can't do vision
            raise VisionError(
                f"{exc}. Pin one with `[vision] model` or "
                "`veles route set vision <provider>:<model>`"
            ) from exc
        except Exception as exc:
            raise VisionError(f"{provider_name}: {type(exc).__name__}: {exc}") from exc
        return (text or "").strip()

    def _resolve_route(self) -> tuple[str, str]:
        from veles.core.model_resolver import ConfigurationError
        from veles.core.provider_factory import has_api_key
        from veles.core.routing import parse_spec, route

        if self.settings.spec:
            try:
                provider_name, model = parse_spec(self.settings.spec)
            except ValueError as exc:
                raise VisionError(f"[vision] model={self.settings.spec!r} is malformed") from exc
        else:
            try:
                provider_name, model = route("vision", self.project)
            except ConfigurationError as exc:
                raise VisionError(str(exc)) from exc
        if not has_api_key(provider_name):
            raise VisionError(
                f"no API key for vision provider {provider_name!r}; set it or point "
                "`[vision] model` at a provider you have configured"
            )
        return provider_name, model


def build_vision_adapter(project: Project) -> RoutedVisionAdapter | None:
    """Adapter for `register_vision_adapter`, or None when `[vision] mode`
    is `off` — the caller then leaves the registry empty and channels fall
    back to handing the agent the saved file."""
    settings = load_vision_settings(project)
    if settings.mode == "off":
        return None
    return RoutedVisionAdapter(project=project, settings=settings)


def install_vision_adapter(project: Project) -> RoutedVisionAdapter | None:
    """Build + register in one call (daemon / channel startup). Never
    raises: a broken `[vision]` block must not stop a daemon from
    booting — it just leaves images to the agent's own tools."""
    from veles.modules.vision import register_vision_adapter

    try:
        adapter = build_vision_adapter(project)
    except Exception as exc:
        logger.warning("vision: adapter not installed (%s: %s)", type(exc).__name__, exc)
        return None
    register_vision_adapter(adapter)
    if adapter is not None:
        logger.info("vision: adapter installed (mode=%s)", adapter.settings.mode)
    return adapter


def _truncate(text: str) -> str:
    if len(text) <= _OUTPUT_CAP:
        return text
    suffix = f"\n\n<truncated at {_OUTPUT_CAP} chars>"
    return text[: _OUTPUT_CAP - len(suffix)] + suffix


__all__ = [
    "DEFAULT_PROMPT",
    "RoutedVisionAdapter",
    "VisionSettings",
    "build_vision_adapter",
    "install_vision_adapter",
    "load_vision_settings",
]
