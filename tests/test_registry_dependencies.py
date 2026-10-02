"""`requires_extensions` — an extension that needs another one gets it installed
first under one confirmation; a failure rolls the whole set back; a dependency
can't be uninstalled from under its dependant."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, make_git_registry, write_extension, write_registry
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project
from veles.core.registry import install as install_mod
from veles.core.registry.catalog import resolve
from veles.core.registry.config import add_source, remove_source
from veles.core.registry.install import InstallError, install, uninstall
from veles.core.registry.maintenance import verify
from veles.core.registry.model import ExtensionError, parse_extension
from veles.core.registry.records import load_records
from veles.core.registry.validate import validate_registry
from veles.core.user_paths import user_home, user_modules_dir

_MODULE_FILES = {
    "module.toml": '[module]\nname = "engine"\ndescription = "d"\nentrypoint = "e.py:register"\n',
    "e.py": "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
}
_LAYOUT_FILES = {"layout.toml": '[layout]\nname = "pack"\ndescription = "d"\n'}


@pytest.fixture()
def asked() -> Iterator[list[str]]:
    seen: list[str] = []

    def confirm(op: str, summary: str) -> bool:
        seen.append(f"{op}\n{summary}")
        return True

    token = set_critical_confirmer(confirm)
    yield seen
    reset_critical_confirmer(token)


@pytest.fixture()
def remote(tmp_path: Path) -> Path:
    root = tmp_path / "remote"
    make_git_registry(root, skills=("alpha",))
    write_extension(root, "official", "engine", kind="module", files=_MODULE_FILES)
    write_extension(
        root,
        "official",
        "pack",
        kind="layout",
        files=_LAYOUT_FILES,
        extra_ext='requires_extensions = ["private:official/engine"]',
    )
    commit_all(root, "more")
    remove_source("public")
    add_source(str(root))
    return root


def _names() -> set[str]:
    return {r.name for r in load_records()}


def test_dependency_installs_first_under_one_confirmation(remote, asked, tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p", layout="bare")
    rec = install(resolve("pack"), project=project)
    assert rec.name == "pack"
    assert _names() == {"pack", "engine"}
    # A layout is user-level, so is the engine it brings along.
    assert (user_modules_dir() / "engine" / "e.py").is_file()
    assert len(asked) == 1
    assert "private:official/engine" in asked[0] and "private:official/pack" in asked[0]


def test_installed_dependency_is_not_reinstalled(remote, asked, tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p", layout="bare")
    install(resolve("engine"), project=project, user_scope=True)
    install(resolve("pack"), project=project)
    assert _names() == {"pack", "engine"}
    assert "private:official/engine" not in asked[-1].split("\n", 1)[1].split("\n")[0]


def test_failure_rolls_the_whole_set_back(remote, asked, tmp_path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p", layout="bare")
    real = install_mod.materialise

    def fail_on_layout(found, target):
        if found.ext.kind == "layout":
            raise OSError("disk full")
        real(found, target)

    monkeypatch.setattr(install_mod, "materialise", fail_on_layout)
    with pytest.raises(InstallError, match="disk full"):
        install(resolve("pack"), project=project)
    assert load_records() == []
    assert not (user_modules_dir() / "engine").exists()
    assert not (user_home() / "layouts" / "pack").exists()


def test_uninstall_refuses_a_dependency_in_use(remote, asked, tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p", layout="bare")
    install(resolve("pack"), project=project)
    with pytest.raises(InstallError, match="pack"):
        uninstall("engine", project=project)
    uninstall("engine", project=project, force=True)
    assert _names() == {"pack"}
    issues = verify(project)
    assert any(i.problem == "missing-dependency" and i.record.name == "pack" for i in issues)


def test_dependency_cycle_is_refused(tmp_path, asked) -> None:
    root = tmp_path / "cyc"
    make_git_registry(root, skills=())
    write_extension(root, "g", "a", extra_ext='requires_extensions = ["private:g/b"]')
    write_extension(root, "g", "b", extra_ext='requires_extensions = ["private:g/a"]')
    commit_all(root, "cycle")
    remove_source("public")
    add_source(str(root))
    project = init_project(tmp_path / "p", name="p", layout="bare")
    with pytest.raises(InstallError, match="cycle"):
        install(resolve("a"), project=project)
    assert load_records() == []


def test_requires_extensions_must_be_full_refs() -> None:
    text = (
        '[extension]\nname = "x"\nkind = "skill"\nversion = "1.0.0"\ndescription = "d"\n'
        'license = "MIT"\nrequires_veles = ">=1"\nrequires_extensions = ["wiki"]\n'
        '[source]\ntype = "path"\n'
    )
    with pytest.raises(ExtensionError, match="requires_extensions"):
        parse_extension(text)


def test_validate_reports_unknown_and_cyclic_dependencies(tmp_path) -> None:
    root = write_registry(tmp_path / "r", name="mine")
    write_extension(root, "g", "a", extra_ext='requires_extensions = ["mine:g/b"]')
    write_extension(root, "g", "b", extra_ext='requires_extensions = ["mine:g/a"]')
    write_extension(root, "g", "c", extra_ext='requires_extensions = ["mine:g/nope"]')
    errors = "\n".join(validate_registry(root).errors)
    assert "mine:g/nope" in errors
    assert "cycle" in errors


def test_losing_an_install_race_never_deletes_the_winners_copy(remote, tmp_path) -> None:
    """Install B passed its collision check, then sat at the confirmation prompt while
    install A finished. B must fail and leave A's copy alone."""
    project = init_project(tmp_path / "p", name="p", layout="bare")
    found = resolve("alpha")
    target = install_mod._target_dir(found, project, user_scope=False)

    def winner_finishes_meanwhile(op: str, summary: str) -> bool:
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("winner\n", encoding="utf-8")
        return True

    token = set_critical_confirmer(winner_finishes_meanwhile)
    try:
        with pytest.raises(InstallError, match="already exists"):
            install(found, project=project)
    finally:
        reset_critical_confirmer(token)
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "winner\n"
    assert load_records() == []


def test_validate_refuses_an_mcp_recipe_as_a_dependency(tmp_path) -> None:
    root = write_registry(tmp_path / "r", name="mine")
    write_extension(root, "g", "srv", kind="mcp", files={}, mcp='command = "x"')
    write_extension(root, "g", "s")  # a skill
    write_extension(root, "g", "m", kind="module", files=_MODULE_FILES)
    write_extension(root, "g", "a", extra_ext='requires_extensions = ["mine:g/srv"]')
    write_extension(root, "g", "b", extra_ext='requires_extensions = ["mine:g/m", "mine:g/s"]')
    errors = validate_registry(root).errors
    assert any(
        e.startswith("g/a:") and "only a module, a layout or a skill" in e for e in errors
    ), errors
    assert not any(e.startswith("g/b:") for e in errors), errors


def test_validate_checks_refs_into_a_connected_registry(tmp_path) -> None:
    other = tmp_path / "other"
    make_git_registry(other, skills=("alpha",))
    write_extension(other, "official", "engine", kind="module", files=_MODULE_FILES)
    commit_all(other, "engine")
    remove_source("public")
    add_source(str(other))  # connected as `private`
    root = write_registry(tmp_path / "r", name="mine")
    write_extension(root, "g", "ok", extra_ext='requires_extensions = ["private:official/engine"]')
    write_extension(root, "g", "sk", extra_ext='requires_extensions = ["private:official/alpha"]')
    write_extension(root, "g", "gone", extra_ext='requires_extensions = ["private:official/nope"]')
    write_extension(root, "g", "far", extra_ext='requires_extensions = ["acme:g/x"]')
    report = validate_registry(root)
    errors = "\n".join(report.errors)
    assert "g/ok:" not in errors
    assert "g/sk:" not in errors  # a skill in another registry is a valid dependency
    assert "g/gone:" in errors and "private:official/nope" in errors
    # A registry this environment doesn't connect can't be checked: a reviewer
    # note, not a failure (a company registry is connected under any local name).
    assert "acme:g/x" not in errors
    assert any("acme:g/x" in r and "not connected" in r for r in report.review), report.review
