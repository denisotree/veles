"""Tests for core/untrusted.py — Tier ε M66 active boundary."""

from __future__ import annotations

from veles.core.untrusted import (
    redact_secrets,
    trust_frontmatter,
    wrap_untrusted,
)


# ---------- redaction ----------


def test_redacts_openai_api_key() -> None:
    text = "my key is sk-abcDEF1234567890wxyzABCDEFG and that's it"
    clean, findings = redact_secrets(text)
    assert "sk-abcDEF1234567890wxyzABCDEFG" not in clean
    assert "[REDACTED:openai-key]" in clean
    assert any(f.pattern == "openai-key" for f in findings)


def test_redacts_openai_project_key() -> None:
    text = "sk-proj-AbcdEFG1234567890hijKLM and rest"
    clean, _ = redact_secrets(text)
    assert "sk-proj-AbcdEFG1234567890hijKLM" not in clean
    assert "[REDACTED:openai-key]" in clean


def test_redacts_anthropic_key() -> None:
    text = "key=sk-ant-AbCdEf1234567890XyZ-test_data here"
    clean, _ = redact_secrets(text)
    assert "[REDACTED:anthropic-key]" in clean


def test_redacts_github_token() -> None:
    text = "Token: ghp_AbcdefghIjklmnopqrstuvwxyzABCDEF12 done"
    clean, _ = redact_secrets(text)
    assert "[REDACTED:github-token]" in clean


def test_redacts_aws_access_key() -> None:
    text = "AKIAIOSFODNN7EXAMPLE is exposed"
    clean, _ = redact_secrets(text)
    assert "[REDACTED:aws-access-key]" in clean


def test_redacts_google_api_key() -> None:
    # Real Google API key: literal `AIza` + exactly 35 [0-9A-Za-z_-] chars.
    text = "got AIza" + "A" * 35 + " from log"
    clean, _ = redact_secrets(text)
    assert "[REDACTED:google-api-key]" in clean


def test_redacts_pem_private_key() -> None:
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1Z1Z\n"
        "-----END RSA PRIVATE KEY-----"
    )
    clean, _ = redact_secrets(text)
    assert "BEGIN RSA PRIVATE KEY" not in clean
    assert "[REDACTED:pem-private-key]" in clean


def test_redacts_env_style_secret() -> None:
    text = "API_KEY=verysecret123abcDEF456 and more text"
    clean, _ = redact_secrets(text)
    assert "verysecret123abcDEF456" not in clean
    assert "API_KEY=[REDACTED:env-style-secret]" in clean


def test_does_not_redact_short_or_normal_text() -> None:
    """False-positive guard — `FOO=bar`, short words, prose shouldn't redact."""
    text = "this is normal prose. FOO=bar. number 1234. value: abc"
    clean, findings = redact_secrets(text)
    assert clean == text
    assert findings == []


def test_redaction_findings_count_correctly() -> None:
    text = "key1: ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa key2: ghp_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    clean, findings = redact_secrets(text)
    gh_finds = [f for f in findings if f.pattern == "github-token"]
    assert gh_finds and gh_finds[0].count == 2
    assert "[REDACTED:github-token]" in clean
    assert clean.count("[REDACTED:github-token]") == 2


# ---------- wrap_untrusted ----------


def test_wrap_adds_reminder_and_tags() -> None:
    wrapped = wrap_untrusted("hello", source="https://example.com")
    assert '<untrusted source="https://example.com"' in wrapped
    assert 'trust="external"' in wrapped
    assert "</untrusted>" in wrapped
    assert "untrusted data" in wrapped


def test_wrap_escapes_quotes_in_source() -> None:
    wrapped = wrap_untrusted("x", source='evil"injected"src')
    # The opening tag must remain well-formed.
    first_line = wrapped.splitlines()[0]
    assert first_line.startswith("<untrusted source=")
    assert first_line.endswith(">")


def test_wrap_redacts_secrets_inside() -> None:
    wrapped = wrap_untrusted(
        "tip: sk-abcDEF1234567890wxyzABCDEFG is the key",
        source="https://foo",
    )
    assert "sk-abcDEF1234567890wxyzABCDEFG" not in wrapped
    assert "[REDACTED:openai-key]" in wrapped


def test_wrap_redact_false_skips_redaction() -> None:
    """Caller can disable redaction when content was already scrubbed upstream."""
    wrapped = wrap_untrusted(
        "ghp_AbcdefghIjklmnopqrstuvwxyzABCDEF12",
        source="x",
        redact=False,
    )
    assert "[REDACTED" not in wrapped


def test_wrap_respects_provided_fetched_timestamp() -> None:
    wrapped = wrap_untrusted("x", source="s", fetched="2026-01-02T03:04:05Z")
    assert 'fetched="2026-01-02T03:04:05Z"' in wrapped


# ---------- trust_frontmatter ----------


def test_trust_frontmatter_format() -> None:
    fm = trust_frontmatter("https://example.com/page", fetched="2026-05-15T00:00:00Z")
    assert fm.startswith("---\n")
    assert "trust: external\n" in fm
    assert 'source_url: "https://example.com/page"' in fm
    assert 'fetched: "2026-05-15T00:00:00Z"' in fm
    assert fm.endswith("---\n\n")


def test_trust_frontmatter_escapes_quotes() -> None:
    fm = trust_frontmatter('https://evil"src.example/')
    # source_url stays inside double quotes; the inner " is URL-encoded.
    assert 'source_url: "https://evil%22src.example/"' in fm
