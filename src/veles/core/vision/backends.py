"""Per-provider image→text wire calls (M226, extracted from M50's
`tools/builtin/image.py`).

`Provider.create_message` is text-only, so vision requests are built by
hand per wire format. Two callers now share them: the `image_describe`
tool (agent asks about a file on disk) and the channel-side
`RoutedVisionAdapter` (a photo arrives in chat and is described before
the agent turn even starts).

The provider catalogue's `wire` picks the request shape. Local providers
speak the OpenAI wire format, so a local vision model (llava, qwen-vl, …)
works here too — that's the "engine is text-only, run something else for
images" case without any cloud dependency.

Tesseract OCR lives here as well (`ocr_bytes`) so the same code answers
both a path (tool) and raw bytes (channel upload).
"""

from __future__ import annotations

import base64
from pathlib import Path

_VISION_MAX_TOKENS = 1024

_WIRES = frozenset({"openai-wire", "anthropic-wire", "gemini-wire"})


def vision_capable(provider_name: str) -> bool:
    """A provider whose wire format we can build an image request for."""
    from veles.core.providers import find_provider

    spec = find_provider(provider_name)
    return spec is not None and spec.wire in _WIRES


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


def detect_mime(p: Path) -> str:
    return _MIME_BY_EXT.get(p.suffix.lower(), "image/png")


def describe(provider_name: str, model: str, image_bytes: bytes, mime: str, prompt: str) -> str:
    """Dispatch to the right wire format. Raises whatever the SDK raises
    (plus `ValueError` for a provider that can't do vision) — callers
    decide how a failure surfaces."""
    from veles.core.providers import find_provider

    spec = find_provider(provider_name)
    wire = spec.wire if spec else None
    if wire == "anthropic-wire":
        return _describe_anthropic(model, _b64(image_bytes), mime, prompt)
    if wire == "gemini-wire":
        return _describe_gemini(model, image_bytes, mime, prompt)
    if wire == "openai-wire":
        return _describe_openai(provider_name, model, _b64(image_bytes), mime, prompt)
    raise ValueError(
        f"provider {provider_name!r} can't run vision queries; route to a provider "
        "that speaks the Anthropic, Gemini or OpenAI wire format (not a CLI delegate)"
    )


def _b64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("ascii")


def _describe_anthropic(model: str, image_b64: str, mime: str, prompt: str) -> str:
    from anthropic import Anthropic

    from veles.core.provider_factory import resolve_api_key

    client = Anthropic(api_key=resolve_api_key("anthropic"))
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


def _describe_openai(provider_name: str, model: str, image_b64: str, mime: str, prompt: str) -> str:
    from openai import OpenAI

    from veles.core.providers import openai_wire_endpoint

    # Keychain-first key (M92): the SDK default would pick up OPENAI_API_KEY
    # for an OpenRouter call and 401.
    base_url, api_key = openai_wire_endpoint(provider_name)
    client = OpenAI(api_key=api_key, base_url=base_url)
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

    from veles.core.provider_factory import resolve_api_key

    api_key = resolve_api_key("gemini")  # key_env covers GOOGLE_API_KEY too
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": _b64(image_bytes)}},
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


class OCRUnavailable(RuntimeError):
    """Tesseract (or its python binding / language pack) isn't installed.
    The message is user-facing — it says how to install."""


def ocr_bytes(data: bytes, lang: str = "eng") -> str:
    """Tesseract OCR over raw image bytes. Deterministic, free, local —
    the cheap first stage of an OCR+model pipeline, and the whole thing
    when no vision model is configured."""
    import io

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OCRUnavailable(
            "image OCR requires `pytesseract` + `Pillow`. Install: "
            "`uv pip install pytesseract pillow` and the system tesseract "
            "binary (`brew install tesseract` / `apt install tesseract-ocr`)"
        ) from exc
    try:
        with Image.open(io.BytesIO(data)) as img:
            return (pytesseract.image_to_string(img, lang=lang) or "").strip()
    except FileNotFoundError as exc:
        raise OCRUnavailable(
            "tesseract binary not found in PATH. Install: "
            "`brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux)"
        ) from exc


__all__ = [
    "OCRUnavailable",
    "describe",
    "detect_mime",
    "ocr_bytes",
    "vision_capable",
]
