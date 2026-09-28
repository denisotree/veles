import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, make_git_registry, write_extension
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project
from veles.core.registry.catalog import resolve
from veles.core.registry.config import add_source, remove_source
from veles.core.registry.gate import module_approved
from veles.core.registry.hashing import tree_sha256
from veles.core.registry.install import InstallError, install, uninstall
from veles.core.registry.records import load_records

_MODULE_FILES = {
    "module.toml": '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "demo.py:register"\n',
    "demo.py": "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
}


@pytest.fixture(autouse=True)
def _yes() -> Iterator[None]:
    token = set_critical_confirmer(lambda op, summary: True)
    yield
    reset_critical_confirmer(token)


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    root = tmp_path / "remote"
    make_git_registry(root, skills=("alpha",))
    write_extension(root, "official", "demo", kind="module", files=_MODULE_FILES)
    write_extension(root, "official", "graph", kind="mcp", files={}, mcp='command = "graphify-mcp"')
    commit_all(root, "more")
    remove_source("public")
    add_source(str(root))
    return root


def test_install_skill_into_project(remote: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    rec = install(resolve("alpha"), project=project)
    assert (project.skills_dir / "alpha" / "SKILL.md").is_file()
    assert not (project.skills_dir / "alpha" / "extension.toml").exists()
    assert rec.registry == "private" and rec.version == "0.1.0"


def test_install_module_is_approved(remote: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    install(resolve("demo"), project=project)
    assert module_approved(project.modules_dir / "demo")


def test_install_mcp_writes_config(remote: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    install(resolve("graph"), project=project)
    cfg = tomllib.loads((project.root / ".veles" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["mcp"]["servers"]["graph"]["command"] == "graphify-mcp"
    uninstall("graph", project=project)
    cfg = tomllib.loads((project.root / ".veles" / "config.toml").read_text(encoding="utf-8"))
    assert "graph" not in cfg.get("mcp", {}).get("servers", {})


def test_declined_confirmation_installs_nothing(remote: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    token = set_critical_confirmer(lambda op, summary: False)
    try:
        with pytest.raises(InstallError, match="aborted"):
            install(resolve("alpha"), project=project)
    finally:
        reset_critical_confirmer(token)
    assert not (project.skills_dir / "alpha").exists()
    assert load_records() == []


def test_incompatible_and_yanked_refused(remote: Path, tmp_path: Path) -> None:
    write_extension(remote, "official", "future", extra_ext="")
    text = (remote / "extensions/official/future/extension.toml").read_text(encoding="utf-8")
    text = text.replace('">=1.0,<2"', '">=9.0"')
    (remote / "extensions/official/future/extension.toml").write_text(text, encoding="utf-8")
    write_extension(remote, "official", "old", extra_ext='yanked = "compromised"')
    commit_all(remote, "future+old")
    from veles.core.registry.config import get_source
    from veles.core.registry.repo import update

    update(get_source("private"))
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(InstallError, match="requires Veles"):
        install(resolve("future"), project=project)
    with pytest.raises(InstallError, match="yanked"):
        install(resolve("old"), project=project)
    install(resolve("old"), project=project, force=True)


def test_git_source_hash_checked(remote: Path, tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(
        "---\nname: ext\ndescription: External.\n---\nbody\n", encoding="utf-8"
    )
    sha = commit_all(upstream, "ext")
    good = tree_sha256(upstream)
    for name, digest in (("ext-good", good), ("ext-bad", "0" * 64)):
        write_extension(
            remote,
            "community",
            name,
            files={},
            source=f'type = "git"\nurl = "{upstream}"\ncommit = "{sha}"\nsha256 = "{digest}"',
        )
    commit_all(remote, "git sources")
    from veles.core.registry.config import get_source
    from veles.core.registry.repo import update

    update(get_source("private"))
    project = init_project(tmp_path / "p", name="p")
    install(resolve("ext-good"), project=project)
    with pytest.raises(InstallError, match="hash mismatch"):
        install(resolve("ext-bad"), project=project)
    assert not (project.skills_dir / "ext-bad").exists()


def test_install_rejects_symlink_payload(remote: Path, tmp_path: Path) -> None:
    ext_dir = write_extension(remote, "official", "sneaky")
    (ext_dir / "leak").symlink_to(tmp_path)
    commit_all(remote, "sneaky")
    from veles.core.registry.config import get_source
    from veles.core.registry.repo import update

    update(get_source("private"))
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(InstallError, match="symlink"):
        install(resolve("sneaky"), project=project)
    assert not (project.skills_dir / "sneaky").exists()


def test_uninstall_skill(remote: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    install(resolve("alpha"), project=project)
    uninstall("alpha", project=project)
    assert not (project.skills_dir / "alpha").exists()
    assert load_records() == []
