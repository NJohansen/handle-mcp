"""The tools for the human's cart, delivery times and orders. They register on server.mcp.

Imported at the end of server.py, after the helpers they use. Only set_cart_quantities and
add_recipe_to_cart write, and only the cart: never an order, a payment or a delivery time.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from typing import Annotated, Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BeforeValidator

from handle_mcp import links, recipe_cart, telemetry
from handle_mcp import stores as registry
from handle_mcp.server import (
    ADD,
    MAX_DAYS,
    MAX_ITEMS,
    MAX_QUANTITY,
    MAX_RESULTS,
    READ,
    WRITE,
    _call,
    _each,
    _names,
    _out,
    _persons,
    _tool,
)


def _whole(value: Any) -> Any:
    """A count is a number or plain digits. int() reads "2_0" as 20 and True as 1."""
    if isinstance(value, bool) or (
        isinstance(value, str) and not re.fullmatch(r"\s*[0-9]+\s*", value)
    ):
        raise ValueError("Antal skal være et helt tal, fx 2.")
    return value


Count = Annotated[int, BeforeValidator(_whole)]


@_tool(READ)
async def get_cart(store: str | None = None) -> dict:
    """Show the cart: lines, fees, total, whether the minimum order is met and `url`, the
    store's cart page where the human checks the cart and pays: give it to the human. With `store`
    that store's cart; without, every store's cart keyed by store name, a failing store
    (e.g. no login) as {"error": ...} next to the others. REMA 1000: the cart is the shopping
    list "handle-mcp" in REMA's app, where the human orders."""
    if store is not None:
        return _out(await _call(store, "cart"))
    return _out(await _each(_names(None), links.cart))


@_tool(WRITE)
async def set_cart_quantities(store: str, items: dict[str, Count]) -> dict:
    """Set ABSOLUTE quantities in one store's cart (0 removes the product). Never orders or pays. Returns a result per product and the new cart with its `url`: give the human that link to check and pay. REMA 1000: sets the shopping list "handle-mcp", never another list."""
    if not items:
        raise ToolError("Ingen varer angivet.")
    if len(items) > MAX_ITEMS:
        raise ToolError(f"Højst {MAX_ITEMS} varer pr. kald.")
    bad = [pid for pid, qty in items.items() if not 0 <= qty <= MAX_QUANTITY]
    if bad:
        raise ToolError(f"Antal skal være 0-{MAX_QUANTITY}. Forkert for: {', '.join(bad)}.")
    if telemetry.locked(store):  # was the counted cart ordered? (telemetry.cart_seen)
        with contextlib.suppress(ToolError):  # counting never blocks a cart change
            await _call(store, "cart")
    results = await _call(store, "set_quantities", dict(items))
    cart = await _call(store, "cart", False)
    telemetry.cart_filled(store, cart, results)
    return _out({"results": results, "cart": cart})


@_tool(ADD)
async def add_recipe_to_cart(
    store: str,
    recipe: str,
    persons: int | None = None,
    skip: list[str] | None = None,
    swap: dict[str, str] | None = None,
    include: list[str] | None = None,
) -> dict:
    """Put a recipe's products in one store's cart, as get_recipe shows them.
    ASK THE HUMAN FIRST: show the list from get_recipe and get a yes. Never orders or pays.
    Adds to what is already in the cart, so calling it twice adds twice.
    `have_at_home` items (salt, oil) are left out unless named in `include`. `skip` leaves out
    ingredients; `swap` maps an ingredient (or product id) to one of its alternatives' product
    ids. Names: ingredient or product id. Returns before/added/after per product, the skipped
    items and the new cart. Check `ok` per product: a store can refuse some lines; tell the
    human which ones failed. BilkaToGo: one pack per product; `persons` is not used."""
    details = await _call(store, "recipe", recipe, _persons(persons))
    try:
        lines, skipped = recipe_cart.plan(details, skip, swap, include)
    except recipe_cart.PlanError as exc:
        raise ToolError(str(exc)) from exc
    if not lines:
        raise ToolError("Ingen varer at lægge i kurven.")
    if len(lines) > MAX_ITEMS:
        raise ToolError(f"Højst {MAX_ITEMS} varer pr. kald.")
    before = recipe_cart.in_cart(await _call(store, "cart"))
    targets = {pid: before.get(pid, 0) + ln["quantity"] for pid, ln in lines.items()}
    if bad := [pid for pid, qty in targets.items() if qty > MAX_QUANTITY]:
        raise ToolError(f"Højst {MAX_QUANTITY} stk. pr. vare. For mange af: {', '.join(bad)}.")
    results = await _call(store, "set_quantities", targets)
    added = recipe_cart.report(lines, before, results)
    cart = await _call(store, "cart", False)
    telemetry.cart_filled(store, cart, results)
    return _out({"added": added, "skipped": skipped, "cart": cart})


@_tool(READ)
async def get_delivery_info(store: str) -> dict:
    """Show the chosen delivery time, edit deadline and next free day, plus fees and minimum order.
    `delivery_mode` is "home", "pickup" (BilkaToGo, REMA 1000, with `pickup_store`) or null when
    unknown."""
    info, terms = await asyncio.gather(_call(store, "delivery_info"), _call(store, "terms"))
    return _out({"delivery": info, "terms": terms})


@_tool(READ)
async def list_delivery_slots(stores: list[str] | None = None, days: int = 7) -> dict:
    """List free delivery times for the next `days` days with the delivery fee per slot, in time
    order, plus the 3 cheapest per store. nemlig: "Personlig" (you are home) or "Fleksibel"
    (left at the door). BilkaToGo: one flat fee, night delivery, or pickup times ("Afhentning")
    when the cart is set to pickup. REMA 1000: Køb & Hent times in the store chosen at login, no
    fee. Only reads: it never chooses a time, store or mode. The human chooses on the store's
    website."""
    days = max(1, min(days, MAX_DAYS))
    return _out(await _each(_names(stores), lambda s: _slots(s, days)))


async def _slots(store: registry.Store, days: int) -> dict:
    slots = sorted(
        (s for s in await store.delivery_slots(days) if s.available), key=lambda s: s.start
    )
    cheapest = sorted(slots, key=lambda s: (s.price is None, s.price or 0, s.start))[:3]
    return {"cheapest": cheapest, "slots": slots}


@_tool(READ)
async def get_orders(store: str, limit: int = 10) -> dict:
    """List recent orders in one store (newest first). Use get_order for the lines."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out({"orders": await _call(store, "orders", limit)})


@_tool(READ)
async def get_order(store: str, order_id: str) -> dict:
    """Show one order with what was bought."""
    return _out(await _call(store, "order", order_id))
