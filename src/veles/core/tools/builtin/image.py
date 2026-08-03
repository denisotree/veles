"""Image multimodal tools (M50) — same two-tier philosophy as M49 PDF.

Two complementary tools, agent picks based on task class:

- `image_ocr(path, lang="eng")` — Tesseract OCR. Deterministic,
  free, local. Best for screenshots, photos of text documents,
  scans of forms. Soft deps: `pytesseract` + `Pillow` + system
  `tesseract` binary. Returns plain text.

- `image_describe(path, prompt=...)` — vision-capable LLM call.
  Semantic. Best for diagrams, architecture pictures, photos of
  scenes. Routed via `route("vision", project)`, which with no
  explicit route falls back to the project's `[engine]` model — a
  multimodal engine therefore needs no configuration at all. Pin a
  different one with `veles route set vision <provider>:<model>`
  (needed when the engine is text-only) or `[vision] model` in
  `.veles/config.toml`.

Both tools sandboxed via M37 `resolve_safe`; failures degrade to
user-visible `<error: ...>` strings rather than raising.

M226 moved the per-provider wire formats and the OCR call into
`core/vision/backends.py` — the channel-side vision adapter runs the
same code on a photo that arrives in chat.
"""

from __future__ import annotations

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.core.vision.adapter import DEFAULT_PROMPT as _DEFAULT_DESCRIBE_PROMPT
from veles.core.vision.backends import OCRUnavailable, describe, detect_mime, ocr_bytes

_VISION_OUTPUT_CAP = 32_000


@tool(risk_class=RiskClass.COMPUTE_ONLY)
def image_ocr(path: str, lang: str = "eng") -> str:
    """Run Tesseract OCR on an image and return the extracted text.

    Tier-1 deterministic / free / local. Path sandboxed (M37). `lang`
    accepts Tesseract language codes ("eng", "rus", "eng+rus", etc.);
    each must have its language pack installed
    (`apt install tesseract-ocr-rus`, etc.). Soft deps:
    `pytesseract` + `Pillow` + system `tesseract` binary.
    """
    try:
        p = resolve_safe(path)
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>"
    if not p.is_file():
        return f"<error: {p} not found>"
    try:
        text = ocr_bytes(p.read_bytes(), lang)
    except OCRUnavailable as exc:
        return f"<error: {exc}>"
    except Exception as exc:
        return f"<error: OCR failed: {type(exc).__name__}: {exc}>"
    return text or "<warning: OCR returned empty (image may have no text)>"


@tool(risk_class=RiskClass.COMPUTE_ONLY)
def image_describe(path: str, prompt: str = _DEFAULT_DESCRIBE_PROMPT) -> str:
    """Describe an image via the routed vision-capable LLM.

    Tier-2 semantic / paid. Routed by task `vision` (set with
    `veles route set vision <provider>:<model>`), falling back to the
    project's `[engine]` model. Path sandboxed (M37). The `prompt` field
    directs the model: defaults to a transcription + summary; pass a
    custom prompt for targeted questions.
    """
    from veles.core.context import current_project
    from veles.core.model_resolver import ConfigurationError
    from veles.core.provider_factory import has_api_key
    from veles.core.routing import route

    try:
        p = resolve_safe(path)
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>"
    if not p.is_file():
        return f"<error: {p} not found>"

    project = current_project()
    if project is None:
        return "<error: image_describe needs an active project for routing>"

    try:
        provider_name, model = route("vision", project)
    except ConfigurationError as exc:
        return f"<error: {exc}>"
    if not has_api_key(provider_name):
        return (
            f"<error: no API key for routed vision provider {provider_name!r}; "
            f"set the env var or run `veles route set vision <provider>:<model>`>"
        )

    try:
        text = describe(provider_name, model, p.read_bytes(), detect_mime(p), prompt)
    except ValueError as exc:  # provider has no vision wire format
        return f"<error: {exc}>"
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>"

    text = (text or "").strip()
    if not text:
        return "<warning: vision provider returned empty response>"
    return _truncate(text)


def _truncate(text: str) -> str:
    if len(text) <= _VISION_OUTPUT_CAP:
        return text
    suffix = f"\n\n<truncated at {_VISION_OUTPUT_CAP} chars>"
    return text[: _VISION_OUTPUT_CAP - len(suffix)] + suffix
