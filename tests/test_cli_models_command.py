"""`veles models <provider>` shell command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from veles.cli import main as cli_main


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles_home"))
    # The wizard is gated on `~/.veles/config.toml`; tmp home is empty so
    # we'd otherwise trip the wizard. Skip it explicitly.
    monkeypatch.setenv("VELES_NO_WIZARD", "1")


def _make_provider_returning(models: list[str]):
    adapter = MagicMock()
    adapter.list_models = MagicMock(return_value=models)
    return MagicMock(return_value=adapter)


def test_models_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    fake_make = _make_provider_returning(["anthropic/claude-opus-4.7", "openai/gpt-4o"])
    with patch("veles.cli._make_provider", fake_make):
        rc = cli_main(["models", "openrouter"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "provider=openrouter" in out
    assert "source=live" in out
    assert "anthropic/claude-opus-4.7" in out
    assert "openai/gpt-4o" in out


def test_models_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    fake_make = _make_provider_returning(["only-one"])
    with patch("veles.cli._make_provider", fake_make):
        rc = cli_main(["models", "openrouter", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "openrouter"
    assert payload["source"] == "live"
    assert "only-one" in payload["models"]


def test_models_refresh_writes_cache(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """`--refresh` triggers a live fetch and persists the result to disk."""
    cache_file = tmp_path / "veles_home" / ".veles" / "cache" / "models" / "openrouter.json"
    assert not cache_file.exists()
    fake_make = _make_provider_returning(["m1", "m2"])
    with patch("veles.cli._make_provider", fake_make):
        rc = cli_main(["models", "openrouter", "--refresh", "--json"])
    assert rc == 0
    capsys.readouterr()
    assert cache_file.exists()
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["models"][0] == "m1"


def test_models_local_provider_skips_cache(tmp_path: Path) -> None:
    """ollama / llamacpp / openai-compat must never write a cache file."""
    fake_make = _make_provider_returning(["qwen2.5:7b"])
    cache_file = tmp_path / "veles_home" / ".veles" / "cache" / "models" / "ollama.json"
    with patch("veles.cli._make_provider", fake_make):
        rc = cli_main(["models", "ollama", "--json"])
    assert rc == 0
    assert not cache_file.exists()


def test_models_falls_back_to_curated_on_missing_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_make = MagicMock(side_effect=RuntimeError("OPENROUTER_API_KEY env var is required"))
    with patch("veles.cli._make_provider", fake_make):
        rc = cli_main(["models", "openrouter"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "source=curated" in out
    # Curated list is non-empty for openrouter.
    assert "anthropic/claude-sonnet-4.6" in out


def test_models_empty_curated_for_cli_delegate_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """claude-cli has no listing endpoint and an empty curated list; the
    command exits 1 with a clear stderr message so shell pipelines can
    branch on it."""
    rc = cli_main(["models", "claude-cli"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "claude-cli" in err
