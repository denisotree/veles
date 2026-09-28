from pathlib import Path

from tests.registry_helpers import commit_all, git, write_extension, write_registry
from veles.core.registry.scan import scan_python
from veles.core.registry.validate import validate_registry

_MODULE_FILES = {
    "module.toml": '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "demo.py:register"\n',
    "demo.py": "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
}


def test_clean_registry_passes(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    write_extension(root, "official", "alpha")
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=_MODULE_FILES,
    )
    write_extension(root, "official", "graph", kind="mcp", files={}, mcp='command = "x"')
    report = validate_registry(root, run_code=True)
    assert report.ok, report.errors


def test_errors_are_reported(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r", public=True)
    write_extension(root, "official", "nodesc", files={"SKILL.md": "no frontmatter"})
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:post_turn"]',
        files=_MODULE_FILES,
    )
    closed = write_extension(root, "community", "closed")
    text = (closed / "extension.toml").read_text(encoding="utf-8")
    (closed / "extension.toml").write_text(
        text.replace("Apache-2.0", "Proprietary"), encoding="utf-8"
    )
    write_extension(root, "community", "alpha")
    write_extension(root, "other", "alpha")
    errors = "\n".join(validate_registry(root, run_code=True).errors)
    assert "nodesc" in errors and "SKILL.md" in errors
    assert "provides" in errors and "hook:pre_turn" in errors
    assert "Proprietary" in errors
    assert "duplicate" in errors and "alpha" in errors


def test_private_registry_allows_proprietary(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r", public=False)
    ext = write_extension(root, "internal", "closed")
    text = (ext / "extension.toml").read_text(encoding="utf-8")
    (ext / "extension.toml").write_text(text.replace("Apache-2.0", "Proprietary"), encoding="utf-8")
    assert validate_registry(root).ok


def test_symlink_payload_fails(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    ext = write_extension(root, "official", "sneaky")
    (ext / "leak").symlink_to(tmp_path)
    assert any("symlink" in e for e in validate_registry(root).errors)


def test_changed_only_and_version_bump(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    write_extension(root, "official", "alpha")
    write_extension(root, "official", "beta")
    commit_all(root, "base")
    git(root, "branch", "base")
    (root / "extensions/official/alpha/SKILL.md").write_text(
        "---\nname: alpha\ndescription: Changed.\n---\nnew\n", encoding="utf-8"
    )
    commit_all(root, "change alpha, no bump")
    report = validate_registry(root, base="base")
    assert any("alpha" in e and "version" in e for e in report.errors)
    write_extension(
        root,
        "official",
        "alpha",
        version="0.2.0",
        files={"SKILL.md": "---\nname: alpha\ndescription: Changed.\n---\nnew\n"},
    )
    commit_all(root, "bump")
    assert validate_registry(root, base="base").ok


def test_module_tests_run(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    files = {**_MODULE_FILES, "tests/test_fail.py": "def test_x():\n    assert False\n"}
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=files,
    )
    assert any("tests failed" in e for e in validate_registry(root, run_code=True).errors)
    assert validate_registry(root).ok  # without --run-code the module never executes


def test_module_tests_pass(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    files = {**_MODULE_FILES, "tests/test_ok.py": "def test_x():\n    assert True\n"}
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=files,
    )
    report = validate_registry(root, run_code=True)
    assert report.ok, report.errors


def test_module_tests_ignore_registry_root_conftest(tmp_path: Path) -> None:
    """A conftest.py above the payload (e.g. at the registry root) must not load —
    the extension's own test run has to be isolated from anything else living in
    the registry checkout, not just from this repo's pyproject.toml."""
    root = write_registry(tmp_path / "r")
    files = {**_MODULE_FILES, "tests/test_ok.py": "def test_x():\n    assert True\n"}
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=files,
    )
    (root / "conftest.py").write_text('raise RuntimeError("leaked")\n', encoding="utf-8")
    report = validate_registry(root, run_code=True)
    assert report.ok, report.errors


def test_scan_python_flags(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "import subprocess, os\nimport httpx\neval('1')\nos.environ['X']\nopen('f', 'w')\n",
        encoding="utf-8",
    )
    text = "\n".join(scan_python(tmp_path))
    for needle in ("process", "network", "eval", "environment", "file write"):
        assert needle in text
