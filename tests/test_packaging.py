"""Packaging sanity checks: metadata, entry point and version consistency."""

import tomllib
from pathlib import Path

from orion import main

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _project() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_version_matches_pyproject():
    assert main.VERSION == _project()["project"]["version"]


def test_console_entry_point_is_orion():
    assert _project()["project"]["scripts"]["orion"] == "orion.main:main"


def test_required_metadata_present():
    project = _project()["project"]
    for field in ("name", "description", "readme", "license", "requires-python"):
        assert field in project, f"missing project.{field}"
    assert "MIT" in str(project["license"])
    assert project["license-files"] == ["LICENSE"]


def test_project_urls_point_at_the_repo():
    urls = _project()["project"]["urls"]
    assert urls["Repository"].endswith("orion-second-brain")
    assert urls["Issues"].endswith("/issues")


def test_extras_and_dependency_groups_defined():
    project = _project()["project"]
    assert {"dev", "mcp", "semantic"} <= set(project["optional-dependencies"])
    assert {"dev", "mcp", "semantic"} <= set(_project()["dependency-groups"])


def test_wheel_ships_the_orion_package():
    target = _project()["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert target["packages"] == ["orion"]
