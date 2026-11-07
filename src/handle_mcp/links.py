"""Links the human clicks. Every link to a store's cart gets the same UTM tags, so the store
can see in its own analytics how many carts and kroner come from handle-mcp."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from handle_mcp import telemetry
from handle_mcp.privacy import jsonable

UTM = {"utm_source": "handlemcp", "utm_medium": "mcp", "utm_campaign": "cart"}


def with_utm(url: str) -> str:
    """`url` with our UTM tags. Other query parameters and the #fragment stay as they were;
    a UTM tag that is already there is replaced, never doubled."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in UTM]
    return urlunsplit(parts._replace(query=urlencode(query + list(UTM.items()))))


def cart_url(store: object) -> str | None:
    """The store's cart page with UTM tags, or None when the store has no `cart_page`."""
    page = getattr(store, "cart_page", None)
    return with_utm(page) if page else None


async def cart(store: Any, seen: bool = True) -> Any:
    """The store's cart with `url`: the cart page, tagged, where the human checks and pays.
    Only a logged-in user gets a cart back, so this also counts the day's login_ok, and an
    empty cart unlocks the store's cart_filled (telemetry.cart_seen)."""
    result = jsonable(await store.get_cart())
    telemetry.login_ok(store.name)
    if seen:  # a read before or without a write: an empty cart here is an order (or cleared)
        telemetry.cart_seen(store.name, result)
    if isinstance(result, dict) and (url := cart_url(store)):
        result["url"] = url
    return result
