# Contributing to Veles

Thanks for your interest in contributing! This document covers the development
setup, the conventions the codebase follows, and what a good PR looks like.

## Development setup

Requirements: Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                      # install runtime + dev dependencies into .venv
uv run pytest                # run the test suite (~3200 tests, ~2 min)
uv run ruff check src tests  # lint
uv run ruff format --check src tests
uv run mypy                  # strict-typed module tier
```

Optional live-API smoke tests (skipped by default):

```bash
VELES_LIVE_TESTS=1 OPENROUTER_API_KEY=sk-or-... uv run pytest tests/test_smoke.py
```

## Code conventions

- **Single responsibility, no god-files.** The codebase is deliberately
  decomposed — keep modules focused and small. If a file starts absorbing
  unrelated concerns, split it.
- **Core stays minimal.** The core is project memory + agent loop + provider
  protocol + tool registry. Gateways, TUI, schedulers, and channels are
  optional modules — new integrations belong there, not in `core/`.
- **All user-facing strings go through i18n.** Use `t("section.key")` from
  `veles.core.i18n` and add the English string to
  `src/veles/locales/en.toml` (canonical) plus translations where you can.
  Never hardcode user-visible text in a single language.
- **Tests are required.** Every behavioral change needs a test. Tests are
  plain pytest, async via `pytest-asyncio` (`asyncio_mode = auto`), no
  network access — stub providers live in `tests/conftest.py`.
- **Lint and format are enforced.** `ruff check` and `ruff format` must pass;
  the config lives in `pyproject.toml` (line length 100). New strictly-typed
  modules can opt into the mypy strict tier (`[tool.mypy] files` list).
- **Commit messages** describe the change in plain English, imperative mood.
  No trailers or attribution lines.

## Submitting a PR

1. Fork, branch from `main`.
2. Make the change with tests.
3. Run the full gate locally: `uv run pytest && uv run ruff check src tests
   && uv run ruff format --check src tests && uv run mypy`.
4. Open the PR with a short description of *why* — link an issue if one
   exists.

Good first contributions: provider adapters, skills for common workflows,
module hooks (observability, logging, policy enforcement), platform
packaging, and locale files for new languages.

## Reporting bugs

Use the issue templates. For security vulnerabilities, **do not open a public
issue** — see [SECURITY.md](SECURITY.md).
