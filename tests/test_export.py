"""M45 — export / import: pack, unpack, sanitize, round-trip."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from veles.core.export import (
    ExportManifest,
    export_full,
    export_template,
    import_bundle,
    sanitize_pii,
)
from veles.core.export import (
    ImportError as VelesImportError,
)
from veles.core.project import init_project

# ---------- helpers ----------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _seed_project(tmp_path: Path, *, name: str = "demo") -> Path:
    """Initialise a project + populate representative artefacts in every sub-tree."""
    project = init_project(tmp_path / name, name=name)
    state = project.state_dir

    # Memory DB stub (binary-ish)
    (state / "memory.db").write_bytes(b"\x00stub-sqlite\x00")
    # M160 memory artefacts: insight view (kept in template) + session
    # compaction (excluded in template) + job output (excluded in template)
    _write(
        state / "memory" / "insights" / "lesson.md",
        "# Lesson\nuse OAuth (alice@example.com)",
    )
    _write(
        state / "memory" / "sessions" / "abc.md",
        "# Session abc\nUser asked alice@example.com to test 192.168.1.5.",
    )
    _write(state / "jobs" / "job-1" / "20260101T000000Z.md", "# job output")
    # Skills
    _write(
        state / "skills" / "planner" / "SKILL.md",
        "---\nname: planner\ndescription: Plans tasks\n---\nplan body",
    )
    # Trust + curator state
    (state / "trust.json").write_text(
        '{"tools": {"run_shell": {"granted_at": "2026-05-10T00:00:00Z"}}}',
        encoding="utf-8",
    )
    (state / "curator.state.json").write_text('{"last_curated_at": 12345}', encoding="utf-8")
    (state / "routing.toml").write_text(
        '[routing.tasks]\ndefault = "openrouter:anthropic/claude-sonnet-4.6"\n',
        encoding="utf-8",
    )
    # Runtime ephemera that must be excluded
    (state / "budget.state.json").write_text("{}", encoding="utf-8")
    (state / "memory.db.lock").write_text("", encoding="utf-8")
    # Tag the AGENTS.md with a piece of PII so template sanitisation is observable.
    (project.root / "AGENTS.md").write_text(
        (project.root / "AGENTS.md").read_text(encoding="utf-8")
        + "\n\nContact: alice@example.com\n",
        encoding="utf-8",
    )
    return project.root


def _read_manifest(bundle: Path) -> dict:
    with tarfile.open(bundle, "r:gz") as tf:
        member = tf.getmember("MANIFEST.json")
        fh = tf.extractfile(member)
        assert fh is not None
        return json.loads(fh.read().decode("utf-8"))


def _list_arcs(bundle: Path) -> list[str]:
    with tarfile.open(bundle, "r:gz") as tf:
        return [m.name for m in tf.getmembers()]


# ---------- sanitize_pii ----------


def test_sanitize_replaces_email() -> None:
    assert sanitize_pii("write to alice@example.com please") == "write to <EMAIL> please"


def test_sanitize_replaces_ipv4() -> None:
    out = sanitize_pii("connect 192.168.1.1 and 10.0.0.5")
    assert "192.168.1.1" not in out
    assert "10.0.0.5" not in out
    assert out.count("<IP>") == 2


def test_sanitize_replaces_openai_style_key() -> None:
    raw = "use sk-abcdef0123456789ABCDEFhijklmnopqrstuvwx for openai"
    out = sanitize_pii(raw)
    assert "sk-abcdef" not in out
    assert "<API_KEY>" in out


def test_sanitize_replaces_google_api_key() -> None:
    raw = "key=AIzaSyA0123456789abcdefghijklmnopqrstuvw"
    out = sanitize_pii(raw)
    assert "AIza" not in out
    assert "<GOOGLE_API_KEY>" in out


def test_sanitize_replaces_github_token() -> None:
    raw = "x-token: ghp_0123456789abcdefghijklmnopqrstuvwxyz"
    out = sanitize_pii(raw)
    assert "ghp_" not in out
    assert "<GITHUB_TOKEN>" in out


def test_sanitize_replaces_bearer_token() -> None:
    raw = "Authorization: Bearer abcdef0123456789abcdef01"
    out = sanitize_pii(raw)
    assert "Bearer <TOKEN>" in out
    assert "abcdef0123456789" not in out


def test_sanitize_idempotent_on_clean_text() -> None:
    txt = "Just some prose with no secrets."
    assert sanitize_pii(txt) == txt


# ---------- export_full ----------


def test_export_full_writes_manifest_and_files(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)

    arcs = _list_arcs(bundle)
    assert "MANIFEST.json" in arcs
    assert "AGENTS.md" in arcs
    assert ".veles/project.toml" in arcs
    assert ".veles/memory.db" in arcs
    assert ".veles/trust.json" in arcs
    assert ".veles/memory/sessions/abc.md" in arcs
    assert ".veles/jobs/job-1/20260101T000000Z.md" in arcs


def test_export_full_excludes_runtime_files(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)

    arcs = _list_arcs(bundle)
    assert ".veles/budget.state.json" not in arcs
    assert all(not m.endswith(".lock") for m in arcs)


def test_export_full_manifest_fields(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path, name="myorg")
    bundle = tmp_path / "out.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)
    manifest = _read_manifest(bundle)
    assert manifest["mode"] == "full"
    assert manifest["project_name"] == "myorg"
    assert manifest["schema_version"] == 1


# ---------- export_template ----------


def test_export_template_excludes_sensitive_files(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "tmpl.tar.gz"
    from veles.core.project import load_project

    export_template(load_project(project_root), bundle)
    arcs = _list_arcs(bundle)
    assert ".veles/memory.db" not in arcs
    assert ".veles/trust.json" not in arcs
    assert ".veles/curator.state.json" not in arcs
    # Per-session compactions + job outputs stripped, insight views kept
    assert not any(m.startswith(".veles/memory/sessions") for m in arcs)
    assert not any(m.startswith(".veles/jobs") for m in arcs)
    assert ".veles/memory/insights/lesson.md" in arcs
    # Schema kept
    assert "AGENTS.md" in arcs
    assert ".veles/project.toml" in arcs
    # Skills kept
    assert ".veles/skills/planner/SKILL.md" in arcs


def test_export_template_runs_pii_sanitisation(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "tmpl.tar.gz"
    from veles.core.project import load_project

    export_template(load_project(project_root), bundle)
    with tarfile.open(bundle, "r:gz") as tf:
        member = tf.getmember(".veles/memory/insights/lesson.md")
        fh = tf.extractfile(member)
        assert fh is not None
        body = fh.read().decode("utf-8")
    assert "alice@example.com" not in body
    assert "<EMAIL>" in body


def test_export_template_manifest_marks_mode(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "out.tar.gz"
    from veles.core.project import load_project

    export_template(load_project(project_root), bundle)
    manifest = _read_manifest(bundle)
    assert manifest["mode"] == "template"


# ---------- import_bundle ----------


def test_import_round_trip_full(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)
    target = tmp_path / "restored"
    imported = import_bundle(bundle, target)
    assert imported.root == target
    assert (target / "AGENTS.md").is_file()
    assert (target / ".veles" / "project.toml").is_file()
    assert (target / ".veles" / "memory.db").is_file()


def test_import_into_existing_project_refuses_without_force(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)
    other_root = tmp_path / "other"
    init_project(other_root, name="other")
    with pytest.raises(VelesImportError, match="already has a Veles project"):
        import_bundle(bundle, other_root)


def test_import_force_overwrites_existing(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path, name="origin")
    bundle = tmp_path / "bundle.tar.gz"
    from veles.core.project import load_project

    export_full(load_project(project_root), bundle)
    other_root = tmp_path / "other"
    init_project(other_root, name="other")
    imported = import_bundle(bundle, other_root, force=True)
    assert imported.name == "origin"


def test_import_refuses_path_escape(tmp_path: Path) -> None:
    """Hand-craft a malicious tarball with `..` in entry name."""
    bundle = tmp_path / "evil.tar.gz"
    with tarfile.open(bundle, "w:gz") as tf:
        # Add a manifest first so the bundle looks plausible.
        manifest = json.dumps(
            {
                "veles_version": "0.0.1",
                "schema_version": 1,
                "exported_at": "2026-05-10T00:00:00Z",
                "mode": "full",
                "project_name": "evil",
            }
        ).encode("utf-8")
        info = tarfile.TarInfo(name="MANIFEST.json")
        info.size = len(manifest)
        tf.addfile(info, fileobj=__import__("io").BytesIO(manifest))
        # Now an escaping entry.
        bad_payload = b"pwned"
        info2 = tarfile.TarInfo(name="../escaped.txt")
        info2.size = len(bad_payload)
        tf.addfile(info2, fileobj=__import__("io").BytesIO(bad_payload))
    with pytest.raises(VelesImportError, match="unsafe path"):
        import_bundle(bundle, tmp_path / "into")


def test_import_refuses_missing_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "no_manifest.tar.gz"
    with tarfile.open(bundle, "w:gz") as tf:
        info = tarfile.TarInfo(name="AGENTS.md")
        info.size = 0
        tf.addfile(info, fileobj=__import__("io").BytesIO(b""))
    with pytest.raises(VelesImportError, match="missing MANIFEST"):
        import_bundle(bundle, tmp_path / "into")


def test_import_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    bundle = tmp_path / "bad_schema.tar.gz"
    with tarfile.open(bundle, "w:gz") as tf:
        manifest = json.dumps(
            {
                "veles_version": "999.0",
                "schema_version": 99,
                "exported_at": "2099-01-01T00:00:00Z",
                "mode": "full",
                "project_name": "future",
            }
        ).encode("utf-8")
        info = tarfile.TarInfo(name="MANIFEST.json")
        info.size = len(manifest)
        tf.addfile(info, fileobj=__import__("io").BytesIO(manifest))
    with pytest.raises(VelesImportError, match="unsupported bundle schema"):
        import_bundle(bundle, tmp_path / "into")


def test_import_refuses_missing_bundle(tmp_path: Path) -> None:
    with pytest.raises(VelesImportError, match="not found"):
        import_bundle(tmp_path / "nope.tar.gz", tmp_path / "into")


def test_import_template_then_load_works(tmp_path: Path) -> None:
    project_root = _seed_project(tmp_path)
    bundle = tmp_path / "tmpl.tar.gz"
    from veles.core.project import load_project

    export_template(load_project(project_root), bundle)
    target = tmp_path / "restored_template"
    imported = import_bundle(bundle, target)
    # Template-imported project should NOT have memory.db
    assert not (target / ".veles" / "memory.db").exists()
    # But it should be a valid project loadable on its own.
    assert imported.name == project_root.name


# ---------- ExportManifest dataclass ----------


def test_export_manifest_is_frozen() -> None:
    m = ExportManifest(
        veles_version="0.0.1",
        schema_version=1,
        exported_at="2026-05-10T00:00:00Z",
        mode="full",
        project_name="x",
    )
    with pytest.raises((AttributeError, TypeError)):
        m.mode = "template"  # type: ignore[misc]
