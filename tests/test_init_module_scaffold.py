"""`veles init` with a layout whose engine comes from an installed (user-level)
module: the module's scaffold runs even though `init` loads no modules itself —
otherwise `veles init --layout llm-wiki` would create no `wiki/`."""

from __future__ import annotations

from pathlib import Path

from veles.core.modules import current_module_registry
from veles.core.project import init_project
from veles.core.registry.gate import approve_module
from veles.core.user_paths import user_modules_dir

_MODULE = """
def register(api):
    from pathlib import Path
    def scaffold(root, manifest):
        if manifest.engine_enabled("dirs"):
            (Path(root) / "made-by-module").mkdir(exist_ok=True)
    api.contribute("scaffold", "dirs", scaffold)
"""


def test_init_runs_installed_module_scaffolds(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    pack = home / ".veles" / "layouts" / "dirpack"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text(
        '[layout]\nname = "dirpack"\n[layout.engines]\ndirs = true\n', encoding="utf-8"
    )
    module = user_modules_dir() / "dirs"
    module.mkdir(parents=True)
    (module / "module.toml").write_text(
        '[module]\nname = "dirs"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (module / "m.py").write_text(_MODULE, encoding="utf-8")
    approve_module(module, name="dirs", project_root=None)
    assert current_module_registry() is None

    project = init_project(tmp_path / "p", name="p", layout="dirpack")
    assert (project.root / "made-by-module").is_dir()
    assert current_module_registry() is None  # nothing leaks out of init
