"""Veles — a minimalist CLI agent framework."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("veles")
except PackageNotFoundError:  # source checkout without an installed dist
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
