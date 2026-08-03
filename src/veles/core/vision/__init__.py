"""Vision: describe images with the project's own models (M226).

`adapter.py` owns policy (what to run: model / OCR / both / nothing),
`backends.py` owns the per-provider wire formats and Tesseract.
"""

from veles.core.vision.adapter import (
    DEFAULT_PROMPT,
    RoutedVisionAdapter,
    VisionSettings,
    build_vision_adapter,
    install_vision_adapter,
    load_vision_settings,
)
from veles.core.vision.backends import VISION_PROVIDERS, OCRUnavailable, describe, ocr_bytes

__all__ = [
    "DEFAULT_PROMPT",
    "VISION_PROVIDERS",
    "OCRUnavailable",
    "RoutedVisionAdapter",
    "VisionSettings",
    "build_vision_adapter",
    "describe",
    "install_vision_adapter",
    "load_vision_settings",
    "ocr_bytes",
]
