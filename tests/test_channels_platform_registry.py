"""M74 — PlatformRegistry register/get/list and built-in Telegram registration."""

from __future__ import annotations

import pytest

from veles.channels import platform_registry as pr


@pytest.fixture(autouse=True)
def _isolated_registry():
    snapshot = dict(pr._REGISTRY)
    pr._reset_registry_for_tests()
    yield
    pr._reset_registry_for_tests()
    pr._REGISTRY.update(snapshot)


def _factory_a(**kwargs):
    return ("A", kwargs)


def _factory_b(**kwargs):
    return ("B", kwargs)


def test_register_and_get():
    pr.register_platform("alpha", _factory_a)
    entry = pr.get_platform("alpha")
    assert entry.name == "alpha"
    assert entry.factory is _factory_a


def test_double_register_same_factory_is_idempotent():
    pr.register_platform("alpha", _factory_a)
    pr.register_platform("alpha", _factory_a)  # no raise
    assert pr.get_platform("alpha").factory is _factory_a


def test_double_register_different_factory_raises():
    pr.register_platform("alpha", _factory_a)
    with pytest.raises(ValueError, match="already registered"):
        pr.register_platform("alpha", _factory_b)


def test_overwrite_replaces_factory():
    pr.register_platform("alpha", _factory_a)
    pr.register_platform("alpha", _factory_b, overwrite=True)
    assert pr.get_platform("alpha").factory is _factory_b


def test_get_unknown_platform_raises_keyerror_with_available_list():
    pr.register_platform("alpha", _factory_a)
    pr.register_platform("beta", _factory_b)
    with pytest.raises(KeyError) as excinfo:
        pr.get_platform("gamma")
    msg = str(excinfo.value)
    assert "alpha" in msg and "beta" in msg


def test_list_returns_sorted_names():
    pr.register_platform("beta", _factory_b)
    pr.register_platform("alpha", _factory_a)
    assert pr.list_platforms() == ["alpha", "beta"]


def test_unregister_returns_true_when_found():
    pr.register_platform("alpha", _factory_a)
    assert pr.unregister_platform("alpha") is True
    assert pr.unregister_platform("alpha") is False
    assert "alpha" not in pr.list_platforms()


def test_register_empty_name_rejected():
    with pytest.raises(ValueError):
        pr.register_platform("", _factory_a)
    with pytest.raises(ValueError):
        pr.register_platform("   ", _factory_a)


def test_ensure_builtins_registers_telegram():
    pr.ensure_builtins_registered()
    assert "telegram" in pr.list_platforms()
    # idempotent
    pr.ensure_builtins_registered()
    assert pr.list_platforms().count("telegram") == 1
