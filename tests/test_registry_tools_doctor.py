from pathlib import Path

from tests.registry_helpers import make_git_registry
from veles.core.context import reset_active_project, set_active_project
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.doctor import _check_extensions
from veles.core.project import init_project
from veles.core.registry.config import add_source, remove_source
from veles.core.tools.builtin.registry_tools import registry_install, registry_search


def _setup(tmp_path: Path):
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha",))
    remove_source("public")
    add_source(str(remote))
    return init_project(tmp_path / "p", name="p")


def test_search_needs_a_fetched_registry(tmp_path: Path) -> None:
    _setup(tmp_path)
    assert "veles registry update" in registry_search("alpha")


def test_install_goes_through_critical_gate(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    token = set_active_project(project)
    refuse = set_critical_confirmer(lambda op, summary: False)
    try:
        assert "not installed" in registry_install("alpha")
        reset_critical_confirmer(refuse)
        # The ref `registry_search` prints (`registry:group/name`) must itself be a
        # valid `registry_install` argument — that's the round trip an agent actually
        # does (search, then install what it found).
        ref = registry_search("alpha").splitlines()[0].split()[0]
        assert ref == "private:official/alpha"
        allow = set_critical_confirmer(lambda op, summary: True)
        assert "installed" in registry_install(ref)
        reset_critical_confirmer(allow)
        assert "private:official/alpha" in registry_search("alpha")
    finally:
        reset_active_project(token)
    assert (project.skills_dir / "alpha").is_dir()


def test_doctor_flags_modified(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    assert _check_extensions(project).status == "ok"
    confirm = set_critical_confirmer(lambda op, summary: True)
    active = set_active_project(project)
    try:
        assert "installed" in registry_install("alpha")
    finally:
        reset_active_project(active)
        reset_critical_confirmer(confirm)
    (project.skills_dir / "alpha" / "SKILL.md").write_text("tampered", encoding="utf-8")
    assert _check_extensions(project).status == "error"


def test_doctor_statuses_for_removed_and_upstream_ahead(tmp_path: Path, monkeypatch) -> None:
    import veles.core.registry.maintenance as maintenance
    from veles.core.registry.maintenance import Issue
    from veles.core.registry.records import InstallRecord

    project = _setup(tmp_path)
    rec = InstallRecord("alpha", "skill", "/x", "1" * 64, registry="private")
    for problem, status in (("removed", "warn"), ("upstream-ahead", "info")):
        monkeypatch.setattr(maintenance, "verify", lambda p, pr=problem: [Issue(rec, pr, "d")])
        result = _check_extensions(project)
        assert result.status == status and "alpha" in result.message


def test_doctor_extensions_check_warns_instead_of_crashing(tmp_path: Path, monkeypatch) -> None:
    project = _setup(tmp_path)
    import veles.core.registry.maintenance as maintenance

    def _boom(project: object) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr(maintenance, "verify", _boom)
    result = _check_extensions(project)
    assert result.status == "warn"
    assert "could not verify extensions" in result.message
