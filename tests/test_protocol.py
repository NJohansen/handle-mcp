"""The tools as an MCP client sees them: real JSON-RPC (initialize handshake) in-process.

The tool descriptions are prompts for the model. tests/snapshots/tools.json holds names,
descriptions, input schemas and annotations, so every change to them shows in the diff.
Update on purpose: HANDLE_UPDATE_SNAPSHOT=1 uv run pytest tests/test_protocol.py
"""

import json
import os
from pathlib import Path

import pytest
from mcp import Client

from handle_mcp import server
from tests.conftest import LEAK
from tests.test_privacy import CALLS

SNAPSHOT = Path(__file__).parent / "snapshots" / "tools.json"


async def _client_tools() -> list[dict]:
    async with Client(server.mcp, mode="legacy") as client:
        tools = (await client.list_tools()).tools
    return [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]


async def test_tool_surface_matches_the_snapshot():
    tools = sorted(await _client_tools(), key=lambda t: t["name"])
    if os.environ.get("HANDLE_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.write_text(json.dumps(tools, ensure_ascii=False, indent=1) + "\n")
    assert tools == json.loads(SNAPSHOT.read_text()), (
        "A tool's name, description, arguments or annotations changed. If on purpose: "
        "HANDLE_UPDATE_SNAPSHOT=1 uv run pytest tests/test_protocol.py"
    )


async def test_every_write_tool_says_so_and_asks_first():
    for tool in await _client_tools():
        hints = tool["annotations"]
        if not hints["readOnlyHint"]:
            assert hints["destructiveHint"] is True, tool["name"]
            assert "order" in tool["description"].lower(), tool["name"]  # "Never orders or pays"


@pytest.mark.parametrize(("tool", "args"), CALLS, ids=[c[0] for c in CALLS])
async def test_every_tool_answers_json_without_personal_data(tool, args):
    async with Client(server.mcp, mode="legacy") as client:
        result = await client.call_tool(tool, args)
    assert not result.is_error, result.content
    text = "".join(c.text for c in result.content if c.type == "text")
    json.loads(text)  # the model gets JSON it can read
    for secret in LEAK.values():
        assert str(secret) not in text, (tool, secret)


@pytest.mark.parametrize(
    ("tool", "args", "match"),
    [
        ("get_cart", {"store": "nope"}, "Ukendt butik"),
        ("set_cart_quantities", {"store": "fake", "items": {"1": 99}}, "Antal skal være"),
        ("set_cart_quantities", {"store": "fake", "items": {"1": "mange"}}, "items"),
        ("add_recipe_to_cart", {"store": "fake", "recipe": "r1", "skip": ["Pizza"]}, "Pizza"),
        ("search_products", {"query": "mælk", "stores": ["broken"]}, "500"),
    ],
)
async def test_errors_reach_the_model_as_clear_text(tool, args, match):
    async with Client(server.mcp, mode="legacy") as client:
        result = await client.call_tool(tool, args)
    text = "".join(c.text for c in result.content if c.type == "text")
    assert match in text, text


async def test_every_tool_is_called_above():
    assert {t["name"] for t in await _client_tools()} == {tool for tool, _ in CALLS}
