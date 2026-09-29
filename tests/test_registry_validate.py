import subprocess
import sys
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


def test_entrypoint_outside_payload_fails(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    (tmp_path / "outside.py").write_text("def register(api): pass\n", encoding="utf-8")
    manifest = _MODULE_FILES["module.toml"].replace("demo.py", "../../../../outside.py")
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files={**_MODULE_FILES, "module.toml": manifest},
    )
    assert any("outside" in e for e in validate_registry(root).errors)


def test_entrypoint_in_hash_skipped_dir_fails(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    files = {
        "module.toml": _MODULE_FILES["module.toml"].replace("demo.py", ".git/main.py"),
        ".git/main.py": _MODULE_FILES["demo.py"],
    }
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=files,
    )
    assert any("not covered by the approval hash" in e for e in validate_registry(root).errors)


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


def test_bad_encoding_extension_is_reported_not_raised(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    ext = write_extension(root, "official", "bad")
    (ext / "extension.toml").write_bytes(b"\xff\xfe")
    report = validate_registry(root)
    assert not report.ok
    assert any("extension.toml" in e for e in report.errors)


def test_changed_paths_handles_non_ascii_group_name(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    write_extension(root, "café", "alpha")
    commit_all(root, "base")
    git(root, "branch", "base")
    (root / "extensions/café/alpha/SKILL.md").write_text(
        "---\nname: alpha\ndescription: Changed.\n---\nnew\n", encoding="utf-8"
    )
    commit_all(root, "change alpha under café, no bump")
    report = validate_registry(root, base="base")
    assert any("alpha" in e and "version" in e for e in report.errors)


def test_module_tests_use_basetemp_under_work(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    files = {
        **_MODULE_FILES,
        "tests/test_tmp.py": (
            "def test_tmp_under_work(tmp_path):\n    assert '.tmp/validate' in str(tmp_path)\n"
        ),
    }
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


def test_register_only_runs_with_run_code(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    files = {
        "module.toml": (
            '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "demo.py:register"\n'
        ),
        "demo.py": (
            "from pathlib import Path\n\n\n"
            "def register(api):\n"
            "    (Path(__file__).parent / 'sentinel.txt').write_text('x')\n"
        ),
    }
    ext_dir = write_extension(root, "official", "demo", kind="module", files=files)
    sentinel = ext_dir / "sentinel.txt"
    validate_registry(root, run_code=False)
    assert not sentinel.exists()
    validate_registry(root, run_code=True)
    assert sentinel.exists()


def test_registry_toml_change_forces_full_revalidation(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r", public=False)
    write_extension(root, "official", "alpha")
    closed = write_extension(root, "official", "closed")
    text = (closed / "extension.toml").read_text(encoding="utf-8")
    (closed / "extension.toml").write_text(
        text.replace("Apache-2.0", "Proprietary"), encoding="utf-8"
    )
    commit_all(root, "base")
    git(root, "branch", "base")
    # Flip the registry public without touching any extension directory — the
    # licence gate now applies to `closed`, even though it wasn't itself changed.
    (root / "registry.toml").write_text(
        '[registry]\nname = "test"\ndescription = "Test registry"\nschema = 1\npublic = true\n',
        encoding="utf-8",
    )
    commit_all(root, "flip public")
    report = validate_registry(root, base="base")
    assert any("closed" in e and "Proprietary" in e for e in report.errors)
    # `alpha` wasn't itself touched, so it owes no version bump — only the
    # registry.toml-driven license re-check applies to it, and it passes that.
    assert not any("official/alpha" in e for e in report.errors)


def test_bogus_base_ref_is_reported_not_raised(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    write_extension(root, "official", "alpha")
    commit_all(root, "base")
    report = validate_registry(root, base="does-not-exist")
    assert any("does-not-exist" in e and "cannot compute changes" in e for e in report.errors)


def test_register_cannot_fake_a_green_run(tmp_path: Path) -> None:
    """A PR's register() that kills the validator (os._exit(0)) must not turn CI
    green: it runs in a subprocess, and the report still lands."""
    root = write_registry(tmp_path / "r")
    files = {**_MODULE_FILES, "demo.py": "import os\n\ndef register(api):\n    os._exit(0)\n"}
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=files,
    )
    write_extension(root, "official", "nodesc", files={"SKILL.md": "no frontmatter"})
    report_file = tmp_path / "report.md"
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from veles.cli import main; sys.exit(main(sys.argv[1:]))",
            "registry",
            "validate",
            str(root),
            "--run-code",
            "--report",
            str(report_file),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    text = report_file.read_text(encoding="utf-8")
    assert "official/nodesc" in text and "SKILL.md" in text
    assert "official/demo" in text and "register()" in text


def test_bytecode_in_payload_fails(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    ext = write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=_MODULE_FILES,
    )
    (ext / "helper.pyc").write_bytes(b"\0")
    errors = validate_registry(root).errors
    assert any("bytecode" in e and "helper.pyc" in e for e in errors), errors


def test_case_variant_bytecode_in_payload_fails(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    ext = write_extension(
        root,
        "official",
        "demo",
        kind="module",
        extra_ext='provides = ["hook:pre_turn"]',
        files=_MODULE_FILES,
    )
    (ext / "__PYCACHE__").mkdir()
    (ext / "__PYCACHE__" / "DEMO.CPYTHON-313.PYC").write_bytes(b"\0")
    (ext / "X.PYC").write_bytes(b"\0")
    [error] = [e for e in validate_registry(root).errors if "bytecode" in e]
    assert "__PYCACHE__" in error and "X.PYC" in error


def test_run_code_leaves_no_bytecode_behind(tmp_path: Path) -> None:
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
    assert validate_registry(root, run_code=True).ok
    report = validate_registry(root, run_code=True)  # a second local run stays green
    assert report.ok, report.errors


def test_scan_python_flags(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "import subprocess, os\nimport httpx\neval('1')\nos.environ['X']\nopen('f', 'w')\n",
        encoding="utf-8",
    )
    text = "\n".join(scan_python(tmp_path))
    for needle in ("process", "network", "eval", "environment", "file write"):
        assert needle in text
