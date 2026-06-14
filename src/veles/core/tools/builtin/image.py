"""Image multimodal tools (M50) — same two-tier philosophy as M49 PDF.

Two complementary tools, agent picks based on task class:

- `image_ocr(path, lang="eng")` — Tesseract OCR. Deterministic,
  free, local. Best for screenshots, photos of text documents,
  scans of forms. Soft deps: `pytesseract` + `Pillow` + system
  `tesseract` binary. Returns plain text.

- `image_describe(path, prompt=...)` — vision-capable LLM call.
  Semantic. Best for diagrams, architecture pictures, photos of
  scenes. Routed via `route("vision", project)` (default
  `anthropic:claude-sonnet-4.6`); user can switch to
  `claude-opus-4-7` or any other vision-capable model via
  `veles route set vision <provider>:<model>`. Per-provider wire
  formats (Anthropic / OpenAI / OpenRouter / Gemini) handled
  inline rather than going through `Provider.create_message`,
  since that abstraction is text-only today.

Both tools sandboxed via M37 `resolve_safe`; failures degrade to
user-visible `<error: ...>` strings rather than raising.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_DEFAULT_DESCRIBE_PROMPT = (
    "Describe this image. List visible text verbatim, then summarise "
    "the scene / diagram / chart content in 3-5 short sentences."
)
_VISION_MAX_TOKENS = 1024
_VISION_OUTPUT_CAP = 32_000

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_MIME_BY_EXT: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


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
        import pytesseract
        from PIL import Image
    except ImportError:
        return (
            "<error: image_ocr requires `pytesseract` + `Pillow`. Install: "
            "`uv pip install pytesseract pillow` and the system tesseract "
            "binary (`brew install tesseract` / `apt install tesseract-ocr`)>"
        )

    try:
        with Image.open(str(p)) as img:
            text = pytesseract.image_to_string(img, lang=lang) or ""
    except FileNotFoundError:
        return (
            "<error: tesseract binary not found in PATH. Install: "
            "`brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux)>"
        )
    except Exception as exc:
        return f"<error: OCR failed: {type(exc).__name__}: {exc}>"
    text = text.strip()
    return text or "<warning: OCR returned empty (image may have no text)>"


@tool(risk_class=RiskClass.COMPUTE_ONLY)
def image_describe(path: str, prompt: str = _DEFAULT_DESCRIBE_PROMPT) -> str:
    """Describe an image via the routed vision-capable LLM.

    Tier-2 semantic / paid. Routed by task `vision` (set with
    `veles route set vision <provider>:<model>`; default is
    `anthropic:claude-sonnet-4.6`). Path sandboxed (M37). The
    `prompt` field directs the model: defaults to a transcription +
    summary; pass a custom prompt for targeted questions.
    """
    from veles.core.context import current_project
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
    from veles.core.model_resolver import ConfigurationError

    try:
        provider_name, model = route("vision", project)
    except ConfigurationError as exc:
        return f"<error: {exc}>"
    if not has_api_key(provider_name):
        return (
            f"<error: no API key for routed vision provider {provider_name!r}; "
            f"set the env var or run `veles route set vision <provider>:<model>`>"
        )

    image_bytes = p.read_bytes()
    mime = _detect_mime(p)
    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    try:
        if provider_name == "anthropic":
            text = _describe_anthropic(model, image_b64, mime, prompt)
        elif provider_name in ("openai", "openrouter"):
            base_url = _OPENROUTER_BASE_URL if provider_name == "openrouter" else None
            text = _describe_openai(model, image_b64, mime, prompt, base_url)
        elif provider_name == "gemini":
            text = _describe_gemini(model, image_bytes, mime, prompt)
        else:
            return (
                f"<error: provider {provider_name!r} can't run vision queries; "
                "route to anthropic / openai / openrouter / gemini>"
            )
    except Exception as exc:
        return f"<error: {type(exc).__name__}: {exc}>"

    text = (text or "").strip()
    if not text:
        return "<warning: vision provider returned empty response>"
    return _truncate(text)


# ---- per-provider implementations ----


def _describe_anthropic(model: str, image_b64: str, mime: str, prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=_VISION_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    parts: list[str] = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            if text:
                parts.append(text)
    return "\n".join(parts)


def _describe_openai(
    model: str, image_b64: str, mime: str, prompt: str, base_url: str | None
) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=base_url) if base_url else OpenAI()
    response = client.chat.completions.create(
        model=model,
        max_tokens=_VISION_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""


def _describe_gemini(model: str, image_bytes: bytes, mime: str, prompt: str) -> str:
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                        }
                    },
                    {"text": prompt},
                ],
            }
        ],
    )
    text = getattr(response, "text", None)
    if text:
        return text
    parts: list[str] = []
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            t = getattr(part, "text", None)
            if t:
                parts.append(t)
    return "\n".join(parts)


# ---- helpers ----


def _detect_mime(p: Path) -> str:
    return _MIME_BY_EXT.get(p.suffix.lower(), "image/png")


def _truncate(text: str) -> str:
    if len(text) <= _VISION_OUTPUT_CAP:
        return text
    suffix = f"\n\n<truncated at {_VISION_OUTPUT_CAP} chars>"
    return text[: _VISION_OUTPUT_CAP - len(suffix)] + suffix
