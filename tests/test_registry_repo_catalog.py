from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, git, make_git_registry, write_extension
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


def test_resolve_unknown_registry(private_registry: Path) -> None:
    with pytest.raises(ResolveError, match="no registry named 'nope'"):
        resolve("nope:alpha")


def test_available_warns_on_unreachable_registry(private_registry: Path, tmp_path: Path) -> None:
    add_source(str(tmp_path / "missing"), name="gone")
    found, warnings = available()
    assert {f.ext.name for f in found} == {"alpha", "beta"}
    assert any(w.startswith("gone:") for w in warnings)


def test_no_sync_when_asked(private_registry: Path) -> None:
    found, warnings = available(sync_missing=False)
    assert found == []
    assert warnings and "veles registry update" in warnings[0]


def test_fetch_git_source_rejects_escaping_subdir(private_registry: Path, tmp_path: Path) -> None:
    head = git(private_registry, "rev-parse", "HEAD")
    dest = tmp_path / "install-target"
    src = Source(
        type="git", url=str(private_registry), commit=head, subdir="../..", sha256="0" * 64
    )
    with pytest.raises(RegistryRepoError, match="escapes the repository"):
        fetch_git_source(src, dest)
    assert not dest.exists()
