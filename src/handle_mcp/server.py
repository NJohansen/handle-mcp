"""The MCP server: store selection, error handling and the tools that read products,
recipes and offers. The cart, delivery and order tools are in cart_tools.py.

stdout is the JSON-RPC stream. All logging goes to stderr.
Every answer goes through privacy.scrub() in `_out()`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from handle_mcp import cli, compare, links, telemetry
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


@_tool(READ)
async def search_products(
    query: str,
    stores: list[str] | None = None,
    limit: int = 10,
    sort: Literal["relevance", "price", "unit_price"] = "relevance",
) -> dict:
    """Search products in one or more stores. Returns price, price per kg/l, offers and EAN when
    known. Stores rank by relevance and put cheap products far down: when the human asks for the
    cheapest, use sort="unit_price" (per kg/l/stk) or "price"."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: compare.search(s, query, limit, sort)))


@_tool(READ)
async def search_recipes(query: str, stores: list[str] | None = None, limit: int = 5) -> dict:
    """Find the stores' own recipes, e.g. "kylling karry". Returns name and link.
    Use get_recipe for time, persons and the products to buy.
    nemlig only: BilkaToGo has no recipe search, use list_recipes with `category` there."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: s.recipes(query, limit)))


@_tool(READ)
async def get_recipe(store: str, recipe: str, persons: int | None = None) -> dict:
    """The products to buy for one of the store's recipes, as on its "Se varer og læg i kurv":
    per ingredient the store's product, packs for `persons` and alternatives. `have_at_home`
    items (salt, oil) are what the store assumes you have: left out of `total`, ask first.
    Also `image`, `description`, `method`, `tip`. Scale `ingredients` from `ingredients_persons`.
    `recipe` is the recipe's link or id from search_recipes or list_recipes. Put the products
    in the cart with add_recipe_to_cart after the human says yes.
    BilkaToGo: one pack per product, no alternatives; `persons` is fixed (null for pieces).
    `missing`: product ids not sold at the address: say so to the human."""
    return _out(await _call(store, "recipe", recipe, _persons(persons)))


@_tool(READ)
async def list_recipes(
    stores: list[str] | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    limit: int = 20,
) -> dict:
    """Browse the store's recipes, with link. No tags or category: this week's featured
    recipes (nemlig: "Ugens udvalgte"). With `tags`: recipes that have every tag, e.g.
    ["Familievenlig", "Budgetvenlig"] or ["Under 30 min", "Kylling"]. nemlig's tags include
    Under 20/30 min, Budgetvenlig, Familievenlig, Populær, Mad til flere dage, Vegetarisk,
    Kylling, Fisk, Oksekød, Gris and cuisines; an unknown tag answers with the full list.
    `category` (nemlig: aftensmad by default, frokost, madpakke, morgenmad, ...).
    BilkaToGo: no tags; no category is this week's "Madplan" (7 dinners); `category` is a path
    like aftensmad or aftensmad/pastaretter, an unknown one answers with the list. Use get_recipe."""
    limit = max(1, min(limit, MAX_RESULTS))
    if not tags and not category:
        return _out(await _each(_names(stores), lambda s: s.featured_recipes(limit)))
    return _out(
        await _each(_names(stores), lambda s: s.recipes_by_tag(tags or [], category, limit))
    )


@_tool(READ)
async def list_offers(stores: list[str] | None = None, limit: int = 25) -> dict:
    """List this week's offers in each store, also items you would not search for: nemlig's
    Skarp pris, Priskup, Dagstilbud, Undgå madspild and gifts; BilkaToGo's offers; REMA 1000's
    leaflet (Avisvarer, often with a max per customer in offer_text). `limit` is
    per list; a product on two lists is shown once. A list the store fails to send is left out
    (see the server log). Free gifts come from a separate search and are not cut by `limit`.
    They have price 0 and "max_per_order". Use them when they fit the plan."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: s.offers(limit)))


@_tool(READ)
async def get_nutrition(store: str, product_ids: list[str]) -> dict:
    """Nutrition per 100 g or 100 ml from the store's label: energy_kj, energy_kcal, fat,
    saturated_fat, carbohydrate, sugar, protein, salt, fibre as strings ("0.13", "<0.5"), null
    when the label leaves a line out. No label (often fresh meat, fruit): `nutrition` null with a
    `reason`. Up to 50 ids from search_products, list_offers or compare_basket; duplicates are
    removed. nemlig, BilkaToGo and REMA 1000; no login needed."""
    ids = list(dict.fromkeys(i.strip() for i in product_ids if i.strip()))  # order kept
    if not ids or len(ids) > MAX_ITEMS:
        raise ToolError(
            "Ingen vare-id'er angivet." if not ids else f"Højst {MAX_ITEMS} varer pr. kald."
        )
    return _out({"products": await _call(store, "nutrition", ids)})


@_tool(READ)
async def compare_basket(items: list[str], stores: list[str] | None = None) -> dict:
    """Price a shopping list in each store, e.g. ["2 x letmælk 1 l", "rugbrød", "æg 10 stk"].
    Write the amount you need ("fior di latte 300 g"), not a pack size. Returns per item a
    suggested product and up to 5 "candidates" (the suggestion first, one øko when found) with
    the cost for the amount and flags: name_match, size_fits, prepared (cold cuts, smoked,
    breaded), processed (frost/konserves), blend, oeko. The suggestion is a guess by word rules:
    pick the candidate that fits the user, and ask when "sure" is false or none fits
    (search_products finds more). Unknown facts and false flags are left out. Also total incl.
    fees and minimum order met. Only reads: use set_cart_quantities with the chosen ids after."""
    items = [i.strip() for i in items if i.strip()]
    if not items:
        raise ToolError("Indkøbslisten er tom.")
    if len(items) > MAX_ITEMS:
        raise ToolError(f"Højst {MAX_ITEMS} varer pr. liste.")
    quotes = await _each(_names(stores), lambda s: compare.quote(s, items))
    return _out({"stores": quotes, **compare.verdict(quotes)})


if __name__ != "__main__":  # the cart tools register on `mcp` when imported: after the helpers
    from handle_mcp.cart_tools import (  # noqa: F401 (re-exported: server.get_cart)
        add_recipe_to_cart,
        get_cart,
        get_delivery_info,
        get_order,
        get_orders,
        list_delivery_slots,
        set_cart_quantities,
    )


def main() -> None:
    cli.main(mcp)


if __name__ == "__main__":  # python -m handle_mcp.server: this copy is not the module the
    from handle_mcp.server import main as run  # cart tools register on, so run that one

    run()
