"""The README and docs/tools.md list every tool, with the same stores.

A new tool without a line in both tables fails here, so the lists cannot fall behind.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
STORES = ["nemlig", "BilkaToGo", "REMA 1000"]


def _rows(path: str) -> list[list[str]]:
    """The cells of each row in the first table under the "Tools" heading."""
    text = (ROOT / path).read_text(encoding="utf-8")
    table = re.search(r"^##? Tools\n\n((?:\|.*\n)+)", text, re.MULTILINE).group(1)
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table.splitlines()]
    return rows[2:]  # after the header and the |---| line


def _names(cell: str) -> list[str]:
    return re.findall(r"`([a-z_]+)", cell)


def _readme() -> dict[str, list[str]]:
    """Tool -> stores, from the README's ✓ columns."""
    stores = {}
    for tool, _writes, *marks, _what in _rows("README.md"):
        for name in _names(tool):
            stores[name] = [s for s, mark in zip(STORES, marks, strict=True) if mark == "✓"]
    return stores


def _tools_md() -> dict[str, list[str]]:
    """Tool -> stores, from the "Butikker" column in docs/tools.md."""
    stores = {}
    for tool, _writes, where, *_what in _rows("docs/tools.md"):
        for name in _names(tool):
            stores[name] = [s.strip() for s in where.split(",")]
    return stores


def test_every_tool_is_in_the_readme_and_in_tools_md():
    snapshot = json.loads((ROOT / "tests/snapshots/tools.json").read_text(encoding="utf-8"))
    tools = {tool["name"] for tool in snapshot}
    assert set(_readme()) == tools, "README.md: the Tools table and the tools differ"
    assert set(_tools_md()) == tools, "docs/tools.md: the table and the tools differ"


def test_the_readme_and_tools_md_name_the_same_stores():
    assert _readme() == _tools_md()
