"""Start the real server over stdio, like an MCP client does, and list its tools.

Catches anything that writes to stdout (it would break JSON-RPC) and import errors.
No network and no logins: listing tools never calls a store.
"""

import os
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_tools import ALLOWED


async def test_server_starts_over_stdio_and_lists_tools(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "handle_mcp.server"],
        env={"HANDLE_CONFIG_DIR": str(tmp_path), "HANDLE_TELEMETRY": "0"},  # no logins, no events
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
    assert sorted(t.name for t in tools.tools) == sorted(ALLOWED)
    assert len(tools.tools) == 14  # one module copy, one MCPServer: every tool on it


def test_server_imports_without_system_time_zones():
    """Windows has no system time zone database (#91). PYTHONTZPATH="" hides ours,
    so zoneinfo must find Europe/Copenhagen in the tzdata package."""
    env = {**os.environ, "PYTHONTZPATH": ""}
    code = "import handle_mcp.server, handle_mcp.compare"
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        timeout=60,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


MODULES = ["handle_mcp.app", "handle_mcp.read_tools", "handle_mcp.cart_tools", "handle_mcp.server"]


@pytest.mark.parametrize("first", MODULES)
@pytest.mark.parametrize("order", [1, -1], ids=["forward", "backward"])
def test_every_tool_module_imports_first_in_a_fresh_interpreter(first, order):
    """No import cycle: any module can be the first one loaded, and all tools end up on
    the one app.mcp."""
    rest = [m for m in MODULES if m != first][::order]
    code = (
        f"import importlib, asyncio; importlib.import_module({first!r}); "
        + "".join(f"importlib.import_module({m!r}); " for m in rest)
        + "from handle_mcp.app import mcp; assert len(asyncio.run(mcp.list_tools())) == 14"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, timeout=60, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
