"""server.json for the official MCP Registry stays in step with the package."""

import json
import pathlib
import re
import tomllib

_root = pathlib.Path(__file__).parents[1]
_server = json.loads((_root / "server.json").read_text(encoding="utf-8"))
_version = tomllib.loads((_root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]


def test_versions_match_pyproject():
    assert _server["version"] == _version
    assert [p["version"] for p in _server["packages"]] == [_version]


def test_readme_proves_pypi_ownership():
    # The registry looks for this line in the README that PyPI shows.
    readme = (_root / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {_server['name']} -->" in readme


def test_description_fits_registry_limit():
    assert len(_server["description"]) <= 100


def test_install_commands_use_latest():
    # ADR 0007: users get the newest release; no pin to forget at release time.
    files = [_root / "README.md", *(_root / "docs").glob("*.md")]
    pins = {
        (f.name, pin)
        for f in files
        for pin in re.findall(r"uvx handle-mcp@(\S+)|\"handle-mcp@([^\"]+)\"", f.read_text("utf-8"))
    }
    assert pins
    assert {p for _, pair in pins for p in pair if p} == {"latest"}, sorted(pins)
