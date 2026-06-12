# Summary

<!-- What does this PR change and why? Link an issue if one exists. -->

## Checklist

- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src tests` and `uv run ruff format --check src tests` pass
- [ ] `uv run mypy` passes (strict-typed module tier)
- [ ] Behavioral changes are covered by tests
- [ ] User-facing strings go through i18n (`t("section.key")` + `src/veles/locales/en.toml`)
