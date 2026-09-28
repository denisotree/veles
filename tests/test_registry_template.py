from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import make_git_registry
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.registry.catalog import resolve
from veles.core.registry.config import add_source, remove_source
from veles.core.registry.model import load_registry_meta, scan_registry
from veles.core.registry.template import (
    TemplateError,
    init_registry,
    scaffold_extension,
    vendor_extension,
)
from veles.core.registry.validate import validate_registry


@pytest.fixture(autouse=True)
def _yes() -> Iterator[None]:
    token = set_critical_confirmer(lambda op, summary: True)
    yield
    reset_critical_confirmer(token)


def test_init_produces_a_valid_registry(tmp_path: Path) -> None:
    root = init_registry(tmp_path / "acme", name="acme", ci="github")
    assert load_registry_meta(root).name == "acme"
    assert (root / ".github" / "workflows" / "validate.yml").is_file()
    assert (root / ".gitignore").is_file()
    workflow = (root / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert "@@" not in workflow and "${{ github.base_ref }}" in workflow
    assert "--from 'veles-ai==" in workflow and " veles registry validate" in workflow
    assert not list(root.rglob("*.tmpl"))
    report = validate_registry(root)
    assert report.ok, report.errors


def test_init_gitlab_and_refuses_non_empty(tmp_path: Path) -> None:
    root = init_registry(tmp_path / "g", name="g", ci="gitlab")
    assert (root / ".gitlab-ci.yml").is_file()
    assert not (root / ".github").exists()
    with pytest.raises(TemplateError):
        init_registry(root, name="again")


@pytest.mark.parametrize("kind", ["module", "skill", "layout", "mcp"])
def test_scaffold_each_kind_validates(tmp_path: Path, kind: str) -> None:
    root = init_registry(tmp_path / "r", name="r", ci="none")
    scaffold_extension(root, kind, f"my-{kind}", group="internal")
    report = validate_registry(root)
    assert report.ok, report.errors


def test_vendor_copies_with_upstream(tmp_path: Path) -> None:
    remote = tmp_path / "public-remote"
    head = make_git_registry(remote, skills=("alpha",))
    remove_source("public")
    add_source(str(remote), name="public")
    target = init_registry(tmp_path / "corp", name="corp", ci="none")
    dest = vendor_extension(resolve("public:alpha"), target, group="vendor")
    [vendored] = [e for e in scan_registry(target)[0] if e.name == "alpha"]
    assert vendored.upstream == f"public:alpha@{head}"
    assert vendored.source.type == "path"
    assert (dest / "SKILL.md").is_file()
    assert validate_registry(target).ok
