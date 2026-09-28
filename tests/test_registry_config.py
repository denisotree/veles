import tomllib

import pytest

from veles.core.registry.config import (
    PUBLIC_URL,
    RegistryConfigError,
    add_source,
    cache_dir,
    get_source,
    list_sources,
    remove_source,
)
from veles.core.user_config import user_config_path


def test_default_is_public() -> None:
    [only] = list_sources()
    assert (only.name, only.url) == ("public", PUBLIC_URL)


def test_add_without_name_is_private_and_keeps_public() -> None:
    added = add_source("git@github.com:acme/veles-registry.git")
    assert added.name == "private"
    assert [s.name for s in list_sources()] == ["public", "private"]


def test_second_unnamed_add_needs_a_name() -> None:
    add_source("git@x:a.git")
    with pytest.raises(RegistryConfigError, match="--name"):
        add_source("git@x:b.git")
    assert add_source("git@x:b.git", name="client-x", ref="stable").ref == "stable"


def test_add_preserves_other_sections() -> None:
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '[user]\nlanguage = "ru"\ndefault_provider = "openrouter"\n\n'
        '[permissions]\nfetch_url = "approval_required"\n',
        encoding="utf-8",
    )
    add_source("git@x:a.git")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["user"]["language"] == "ru"
    assert data["permissions"]["fetch_url"] == "approval_required"
    assert data["registries"]["private"]["url"] == "git@x:a.git"


def test_remove_public_sticks_and_drops_cache() -> None:
    cache = cache_dir("public")
    cache.mkdir(parents=True)
    remove_source("public")
    assert list_sources() == []
    assert not cache.exists()
    with pytest.raises(RegistryConfigError):
        get_source("public")


def test_bad_name_rejected() -> None:
    with pytest.raises(RegistryConfigError, match="name"):
        add_source("git@x:a.git", name="Bad Name")


def test_option_like_url_rejected() -> None:
    with pytest.raises(RegistryConfigError, match="start with '-'"):
        add_source("--upload-pack=touch /x")
