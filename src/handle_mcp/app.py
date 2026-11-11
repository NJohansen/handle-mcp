"""The MCP server object and what every tool module shares: limits, annotations, store
selection, error handling and `_out()`, through which every answer passes privacy.scrub().

read_tools.py and cart_tools.py register their tools on `mcp` here. server.py is only the
entry point: no module imports it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from handle_mcp import links, telemetry
from handle_mcp import stores as registry
from handle_mcp.privacy import jsonable, scrub, scrub_text

log = logging.getLogger("handle_mcp")

MAX_ITEMS = 50  # per set_cart_quantities or compare_basket call
MAX_QUANTITY = 50  # per product
MAX_RESULTS = 25
MAX_DAYS = 14
MIN_PERSONS, MAX_PERSONS = 2, 12  # nemlig: 2-12


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)
ADD = ToolAnnotations(  # add_recipe_to_cart: twice adds twice
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)

mcp = MCPServer(
    "handle",
    instructions=(
        "Tools for Danish grocery stores with home delivery. You can search, compare "
        "baskets, find recipes, list delivery times and change cart quantities. You can never order or pay: the human "
        "always does that on the store's website. An answer with `telemetry_notice` says "
        "what handle-mcp counts anonymously: tell the human in one sentence, once."
    ),
)

_instances: dict[str, registry.Store] = {}


def _store(name: str) -> registry.Store:
    if name not in registry.STORES:
        known = ", ".join(sorted(registry.STORES)) or "ingen endnu"
        raise ToolError(f"Ukendt butik '{name}'. Kendte butikker: {known}.")
    if name not in _instances:
        _instances[name] = registry.STORES[name]()
    return _instances[name]


def _names(requested: list[str] | None) -> list[str]:
    names = requested or sorted(registry.STORES)
    if not names:
        raise ToolError("Ingen butikker er sat op endnu.")
    for name in names:
        _store(name)  # fail early on an unknown name
    return names


def _persons(persons: int | None) -> int | None:
    return None if persons is None else max(MIN_PERSONS, min(persons, MAX_PERSONS))


def _tool(annotations: ToolAnnotations) -> Callable[[Callable], Callable]:
    """`mcp.tool`, and count the day's first tool call (telemetry.counted)."""
    return lambda fn: mcp.tool(annotations=annotations)(telemetry.counted(fn))


def _out(value: Any) -> dict[str, Any]:
    result = scrub(jsonable(value))
    result = result if isinstance(result, dict) else {"result": result}
    if notice := telemetry.notice():  # once: the model tells the human what is counted
        result["telemetry_notice"] = notice
    return result


def _error_text(store: str, exc: BaseException) -> str:
    """The error the model sees. A store's own message may echo personal data: scrub it."""
    return scrub_text(_error_reason(store, exc))


def _error_reason(store: str, exc: BaseException) -> str:
    if isinstance(exc, NotImplementedError):
        return f"{store} kan ikke det endnu."
    if isinstance(exc, registry.StoreError):
        return f"{store}: {exc}"
    log.exception("%s failed", store, exc_info=exc)
    return f"{store}: uventet fejl ({type(exc).__name__}). Se serverens log."


async def _call(store: str, method: str, *args: Any) -> Any:
    try:
        if method == "cart":  # the cart with its tagged link (links.py)
            return await links.cart(_store(store), *args)
        return await getattr(_store(store), method)(*args)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(_error_text(store, exc)) from exc


async def _each(names: list[str], work: Callable[[Any], Awaitable[Any]]) -> dict[str, Any]:
    """Run `work(store)` for every store at once. One store failing never stops the others."""
    results = await asyncio.gather(*(work(_store(n)) for n in names), return_exceptions=True)
    return {
        name: {"error": _error_text(name, r)} if isinstance(r, BaseException) else r
        for name, r in zip(names, results, strict=True)
    }
