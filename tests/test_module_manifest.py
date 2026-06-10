"""Unit tests for module_manifest parser."""

from __future__ import annotations

import pytest

from veles.core.module_manifest import (
    ManifestError,
    ModuleManifest,
    parse_entrypoint,
    parse_manifest,
)


def test_parse_manifest_valid_minimal() -> None:
    text = """
[module]
name = "logger"
description = "Log every tool call"
entrypoint = "main.py:register"
"""
    m = parse_manifest(text)
    assert m == ModuleManifest(
        name="logger",
        description="Log every tool call",
        entrypoint="main.py:register",
        version=None,
    )


def test_parse_manifest_includes_optional_version() -> None:
    text = """
[module]
name = "x"
description = "y"
entrypoint = "main.py:register"
version = "0.2.1"
"""
    assert parse_manifest(text).version == "0.2.1"


def test_parse_manifest_missing_module_section_raises() -> None:
    with pytest.raises(ManifestError, match=r"\[module\] section"):
        parse_manifest("[other]\nfoo = 1\n")


def test_parse_manifest_missing_required_key_raises() -> None:
    text = """
[module]
name = "x"
description = "y"
"""
    with pytest.raises(ManifestError, match="entrypoint"):
        parse_manifest(text)


def test_parse_manifest_empty_string_required_raises() -> None:
    text = """
[module]
name = ""
description = "y"
entrypoint = "main.py:register"
"""
    with pytest.raises(ManifestError, match="name"):
        parse_manifest(text)


def test_parse_manifest_invalid_toml_raises() -> None:
    with pytest.raises(ManifestError, match="invalid TOML"):
        parse_manifest("[module\nname = 'x'")


def test_parse_manifest_version_must_be_string() -> None:
    text = """
[module]
name = "x"
description = "y"
entrypoint = "main.py:register"
version = 42
"""
    with pytest.raises(ManifestError, match="version"):
        parse_manifest(text)


def test_parse_entrypoint_splits_file_and_func() -> None:
    assert parse_entrypoint("main.py:register") == ("main.py", "register")
    assert parse_entrypoint("pkg/sub.py:my_func") == ("pkg/sub.py", "my_func")


def test_parse_entrypoint_rejects_missing_colon() -> None:
    with pytest.raises(ManifestError, match="file:func"):
        parse_entrypoint("just_a_func")


def test_parse_entrypoint_rejects_empty_parts() -> None:
    with pytest.raises(ManifestError):
        parse_entrypoint(":register")
    with pytest.raises(ManifestError):
        parse_entrypoint("main.py:")
