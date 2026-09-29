import os
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, git, make_git_registry, write_extension
from veles.core.registry import repo as repo_module
from veles.core.registry.catalog import ResolveError, available, resolve, search
from veles.core.registry.config import add_source, cache_dir, remove_source
from veles.core.registry.model import Source
from veles.core.registry.repo import RegistryRepoError, ensure_cache, fetch_git_source, update


@pytest.fixture
def private_registry(tmp_path: Path) -> Path:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha", "beta"))
    remove_source("public")
    add_source(str(remote))
    return remote


def test_ensure_cache_clones_once(private_registry: Path) -> None:
    from veles.core.registry.config import get_source

    path = ensure_cache(get_source("private"))
    assert (path / "registry.toml").is_file()
    assert ensure_cache(get_source("private")) == path


def test_update_fast_forwards(private_registry: Path) -> None:
    from veles.core.registry.config import get_source

    source = get_source("private")
    ensure_cache(source)
    write_extension(private_registry, "community", "gamma")
    new_head = commit_all(private_registry, "add gamma")
    assert update(source) == new_head
    assert {f.ext.name for f in available()[0]} == {"alpha", "beta", "gamma"}


def test_failed_clone_leaves_no_cache(tmp_path: Path) -> None:
    remove_source("public")
    add_source(str(tmp_path / "does-not-exist"), name="broken")
    from veles.core.registry.config import get_source

    with pytest.raises(RegistryRepoError):
        ensure_cache(get_source("broken"))
    assert not cache_dir("broken").exists()
    assert not cache_dir("broken").with_name(".broken.cloning").exists()


def test_ensure_cache_removes_stale_staging_dir(private_registry: Path) -> None:
    from veles.core.registry.config import get_source

    staging = cache_dir("private").with_name(".private.cloning")
    staging.mkdir(parents=True)
    (staging / "junk.txt").write_text("stale", encoding="utf-8")
    path = ensure_cache(get_source("private"))
    assert (path / "registry.toml").is_file()
    assert not staging.exists()


def test_ensure_cache_cleans_up_on_keyboard_interrupt(
    private_registry: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.registry.config import get_source

    def _boom(*args: object, **kwargs: object) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(repo_module, "_git", _boom)
    with pytest.raises(KeyboardInterrupt):
        ensure_cache(get_source("private"))
    path = cache_dir("private")
    assert not path.exists()
    assert not path.with_name(".private.cloning").exists()


def test_search_filters(private_registry: Path) -> None:
    found, warnings = search("beta")
    assert [f.ref for f in found] == ["private:official/beta"]
    assert warnings == []
    assert search(kind="module")[0] == []


def test_resolve_unique_ambiguous_and_missing(private_registry: Path, tmp_path: Path) -> None:
    assert resolve("alpha").registry == "private"
    other = tmp_path / "other"
    make_git_registry(other, skills=("alpha",))
    add_source(str(other), name="other")
    with pytest.raises(ResolveError, match="private:official/alpha"):
        resolve("alpha")
    assert resolve("other:alpha").registry == "other"
    with pytest.raises(ResolveError, match="no extension"):
        resolve("zeta")


def test_resolve_by_group_slash_name(private_registry: Path) -> None:
    assert resolve("private:official/alpha").registry == "private"
    assert resolve("official/alpha").registry == "private"


def test_resolve_disambiguates_same_name_different_group(private_registry: Path) -> None:
    # `validate` forbids two extensions sharing a name within one registry, but a
    # locally-authored registry that was never validated can still reach this state —
    # `resolve` must disambiguate it rather than pick one arbitrarily.
    write_extension(private_registry, "community", "alpha")
    commit_all(private_registry, "add community/alpha")
    with pytest.raises(ResolveError, match="ambiguous"):
        resolve("alpha")
    assert resolve("official/alpha").ext.group == "official"
    assert resolve("community/alpha").ext.group == "community"


def test_resolve_unknown_registry(private_registry: Path) -> None:
    with pytest.raises(ResolveError, match="no registry named 'nope'"):
        resolve("nope:alpha")


def test_resolve_reports_warnings_when_missing(private_registry: Path, tmp_path: Path) -> None:
    add_source(str(tmp_path / "missing"), name="gone")
    with pytest.raises(ResolveError, match="unreachable: gone:"):
        resolve("zeta")


def test_available_warns_on_unreachable_registry(private_registry: Path, tmp_path: Path) -> None:
    add_source(str(tmp_path / "missing"), name="gone")
    found, warnings = available()
    assert {f.ext.name for f in found} == {"alpha", "beta"}
    assert any(w.startswith("gone:") for w in warnings)


def test_no_sync_when_asked(private_registry: Path) -> None:
    found, warnings = available(sync_missing=False)
    assert found == []
    assert warnings and "veles registry update" in warnings[0]


def test_access_failures_carry_a_hint(private_registry: Path, tmp_path: Path) -> None:
    import shutil

    from veles.core.registry.config import get_source

    add_source(str(tmp_path / "does-not-exist"), name="broken")
    with pytest.raises(RegistryRepoError) as clone_err:
        ensure_cache(get_source("broken"))
    assert str(clone_err.value).count("gh auth setup-git") == 1
    ensure_cache(get_source("private"))
    shutil.rmtree(private_registry)
    with pytest.raises(RegistryRepoError) as fetch_err:
        update(get_source("private"))
    assert str(fetch_err.value).count("gh auth setup-git") == 1


def test_changed_paths_rejects_option_like_base(private_registry: Path) -> None:
    from veles.core.registry.repo import changed_paths

    with pytest.raises(RegistryRepoError, match="must not start with '-'"):
        changed_paths(private_registry, "--output=pwned")
    assert not (private_registry / "pwned").exists()


def test_fetch_git_source_drops_bytecode(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    (upstream / "pkg" / "__pycache__").mkdir(parents=True)
    (upstream / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (upstream / "pkg" / "__pycache__" / "mod.cpython-313.pyc").write_bytes(b"\0")
    (upstream / "pkg" / "helper.pyc").write_bytes(b"\0")
    git(upstream, "init", "-q", "-b", "main")
    git(upstream, "add", "-f", "-A")
    head = commit_all(upstream, "with bytecode")
    assert "pkg/helper.pyc" in git(upstream, "ls-files")
    dest = tmp_path / "install-target"
    src = Source(type="git", url=str(upstream), commit=head, subdir="pkg", sha256="0" * 64)
    fetch_git_source(src, dest)
    assert (dest / "mod.py").is_file()
    assert not (dest / "__pycache__").exists()
    assert not (dest / "helper.pyc").exists()


def test_fetch_git_source_drops_case_variant_bytecode(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    (upstream / "pkg" / "__PYCACHE__").mkdir(parents=True)
    (upstream / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (upstream / "pkg" / "__PYCACHE__" / "MOD.CPYTHON-313.PYC").write_bytes(b"\0")
    (upstream / "pkg" / "HELPER.PYC").write_bytes(b"\0")
    git(upstream, "init", "-q", "-b", "main")
    git(upstream, "add", "-f", "-A")
    head = commit_all(upstream, "with bytecode")
    assert "pkg/HELPER.PYC" in git(upstream, "ls-files")
    dest = tmp_path / "install-target"
    src = Source(type="git", url=str(upstream), commit=head, subdir="pkg", sha256="0" * 64)
    fetch_git_source(src, dest)
    assert sorted(os.listdir(dest)) == ["mod.py"]


def test_fetch_git_source_rejects_escaping_subdir(private_registry: Path, tmp_path: Path) -> None:
    head = git(private_registry, "rev-parse", "HEAD")
    dest = tmp_path / "install-target"
    src = Source(
        type="git", url=str(private_registry), commit=head, subdir="../..", sha256="0" * 64
    )
    with pytest.raises(RegistryRepoError, match="escapes the repository"):
        fetch_git_source(src, dest)
    assert not dest.exists()
