"""The entry point: `handle-mcp` and `python -m handle_mcp.server`.

stdout is the JSON-RPC stream. All logging goes to stderr. The server object and the
shared helpers are in app.py; the tools in read_tools.py and cart_tools.py, which register
on app.mcp when imported. The names below stay importable from here, e.g. server.get_cart.
"""

from __future__ import annotations

from handle_mcp import cli
from handle_mcp.app import (  # noqa: F401 (re-exported)
    MAX_DAYS,
    MAX_ITEMS,
    MAX_PERSONS,
    MAX_QUANTITY,
    MAX_RESULTS,
    MIN_PERSONS,
    _out,
    _store,
    mcp,
)
from handle_mcp.cart_tools import (  # noqa: F401 (re-exported)
    add_recipe_to_cart,
    get_cart,
    get_delivery_info,
    get_order,
    get_orders,
    list_delivery_slots,
    set_cart_quantities,
)
from handle_mcp.read_tools import (  # noqa: F401 (re-exported)
    compare_basket,
    get_nutrition,
    get_recipe,
    list_offers,
    list_recipes,
    search_products,
    search_recipes,
)


def main() -> None:
    cli.main(mcp)


if __name__ == "__main__":
    main()
