"""TTL memo for `discover_skills` (M158-followup).

Daemon-only opt-in: default (`cache_ttl=None`) re-reads on-disk truth every
call so CLI one-shots and tests see a freshly-authored skill immediately; the
long-lived daemon passes a few-minute TTL to stop re-parsing every SKILL.md
per turn, bounding how long a runtime-authored skill stays invisible.
"""

from __future__ import annotations

from pathlib import Path

from veles.core import skills as skills_mod
from veles.core.project import init_project
from veles.core.skills import discover_skills


def _write_skill(parent: Path, name: str) -> None:
    d = parent / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} skill.\n---\nbody\n",
        encoding="utf-8",
    )


def _names(project, **kw) -> set[str]:
    return {s.name for s in discover_skills(project, include_layout=False, **kw)}


def test_no_cache_by_default_sees_new_skill_immediately(tmp_path, isolated_user_home):
    skills_mod._SKILLS_CACHE.clear()
    project = init_project(tmp_path / "p", name="p")
    _write_skill(project.skills_dir, "alpha")
    assert _names(project) == {"alpha"}
    _write_skill(project.skills_dir, "beta")
    assert _names(project) == {"alpha", "beta"}  # default = no cache


def test_ttl_cache_serves_stale_within_window(tmp_path, isolated_user_home):
    skills_mod._SKILLS_CACHE.clear()
    project = init_project(tmp_path / "p", name="p")
    _write_skill(project.skills_dir, "alpha")
    assert _names(project, cache_ttl=600) == {"alpha"}  # warms the cache
    _write_skill(project.skills_dir, "beta")
    # within TTL: the cache hides the freshly-written skill
    assert _names(project, cache_ttl=600) == {"alpha"}
    # but an uncached call still sees on-disk truth (CLI/tests path)
    assert _names(project) == {"alpha", "beta"}


def test_ttl_cache_expires_and_repolls(tmp_path, isolated_user_home, monkeypatch):
    skills_mod._SKILLS_CACHE.clear()
    clock = {"t": 1000.0}
    monkeypatch.setattr(skills_mod.time, "monotonic", lambda: clock["t"])
    project = init_project(tmp_path / "p", name="p")
    _write_skill(project.skills_dir, "alpha")
    assert _names(project, cache_ttl=60) == {"alpha"}
    _write_skill(project.skills_dir, "beta")
    clock["t"] += 30  # still within the 60s window
    assert _names(project, cache_ttl=60) == {"alpha"}
    clock["t"] += 31  # now past 60s → re-poll
    assert _names(project, cache_ttl=60) == {"alpha", "beta"}


def test_ttl_zero_disables_cache(tmp_path, isolated_user_home):
    skills_mod._SKILLS_CACHE.clear()
    project = init_project(tmp_path / "p", name="p")
    _write_skill(project.skills_dir, "alpha")
    assert _names(project, cache_ttl=0) == {"alpha"}
    _write_skill(project.skills_dir, "beta")
    assert _names(project, cache_ttl=0) == {"alpha", "beta"}  # 0 → no cache


def test_cached_list_is_a_copy(tmp_path, isolated_user_home):
    skills_mod._SKILLS_CACHE.clear()
    project = init_project(tmp_path / "p", name="p")
    _write_skill(project.skills_dir, "alpha")
    first = discover_skills(project, include_layout=False, cache_ttl=600)
    first.append("garbage")  # mutating the returned list must not corrupt cache
    second = discover_skills(project, include_layout=False, cache_ttl=600)
    assert {s.name for s in second} == {"alpha"}
