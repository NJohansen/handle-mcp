"""The tools that read products, recipes, offers and nutrition, and compare a basket.
They register on app.mcp. Nothing here writes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from handle_mcp import compare
from handle_mcp.app import (
    CATEGORY_RESULTS,
    MAX_CATEGORY_RESULTS,
    MAX_ITEMS,
    MAX_RESULTS,
    READ,
    StoreName,
    StoreNames,
    _call,
    _each,
    _names,
    _out,
    _persons,
    _tool,
)
from handle_mcp.stores import OFFER_CATEGORIES


@_tool(READ)
async def search_products(
    query: Annotated[str, Field(description='What to find, in Danish, e.g. "letmælk".')],
    stores: StoreNames = None,
    limit: Annotated[int, Field(description="Products per store, 1-25.")] = 10,
    sort: Annotated[
        Literal["relevance", "price", "unit_price"],
        Field(description='"unit_price" is per kg/l/stk.'),
    ] = "relevance",
) -> dict:
    """Search products in one or more stores. Returns price, price per kg/l, offers and EAN when
    known. Stores rank by relevance and put cheap products far down: when the human asks for the
    cheapest, use sort="unit_price" (per kg/l/stk) or "price". For a whole shopping list, use
    compare_basket."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: compare.search(s, query, limit, sort)))


@_tool(READ)
async def search_recipes(
    query: Annotated[str, Field(description='Words to search for, e.g. "kylling karry".')],
    stores: StoreNames = None,
    limit: Annotated[int, Field(description="Recipes per store, 1-25.")] = 5,
) -> dict:
    """Find the stores' own recipes, e.g. "kylling karry". Returns name and link.
    Use it when the human names a dish; to browse by tag or category, use list_recipes.
    Use get_recipe for time, persons and the products to buy.
    nemlig only: BilkaToGo has no recipe search, use list_recipes with `category` there."""
    limit = max(1, min(limit, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: s.recipes(query, limit)))


@_tool(READ)
async def get_recipe(
    store: StoreName,
    recipe: Annotated[
        str, Field(description="The recipe's link or id from search_recipes or list_recipes.")
    ],
    persons: Annotated[
        int | None, Field(description="People to cook for, 2-12. Leave out for the recipe's own.")
    ] = None,
) -> dict:
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
    stores: StoreNames = None,
    tags: Annotated[
        list[str] | None, Field(description='Every tag must match, e.g. ["Familievenlig"].')
    ] = None,
    category: Annotated[
        str | None, Field(description='e.g. "aftensmad", "frokost". Leave out for the default.')
    ] = None,
    limit: Annotated[int, Field(description="Recipes per store, 1-25.")] = 20,
) -> dict:
    """Browse the store's recipes, with link, when the human has no dish in mind (for a dish by
    name, use search_recipes). No tags or category: this week's featured
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
async def list_offers(
    stores: StoreNames = None,
    limit: Annotated[
        int | None,
        Field(
            description="Without `category`: products per offer list, 1-25 (default 25). "
            "With it: products per store, 1-100 (default 60)."
        ),
    ] = None,
    category: Annotated[
        str | None,
        Field(description="One category: " + ", ".join(f'"{c}"' for c in OFFER_CATEGORIES) + "."),
    ] = None,
) -> dict:
    """List this week's offers in each store, also items you would not search for. For one
    named product, use search_products.
    Without `category`, a first look only: nemlig's Skarp pris, Priskup, Dagstilbud, Undgå
    madspild and gifts; the first of BilkaToGo's offers; REMA 1000's leaflet (Avisvarer). For a
    meal plan or a shopping list, call once per `category` you buy from: every offer in it, in
    each store.
    Each product has price, before_price and offer_until (null when the store does not say),
    offer_text (multi-buy, max per customer) and campaign (the store's name for the offer). A
    product on two lists is shown once. A list the store fails to send is left out (see the
    server log). Free gifts have price 0, max_per_order and their own product id, and are not
    cut by `limit`."""
    if category is not None:
        category = category.strip().lower()
        if category not in OFFER_CATEGORIES:
            known = ", ".join(OFFER_CATEGORIES)
            raise ToolError(f"Ukendt kategori '{category}'. Vælg en af: {known}.")
        limit = max(1, min(limit or CATEGORY_RESULTS, MAX_CATEGORY_RESULTS))
    else:
        limit = max(1, min(limit or MAX_RESULTS, MAX_RESULTS))
    return _out(await _each(_names(stores), lambda s: s.offers(limit, category)))


@_tool(READ)
async def get_nutrition(
    store: StoreName,
    product_ids: Annotated[
        list[str], Field(description="Product ids from the same store, up to 50.")
    ],
) -> dict:
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
async def compare_basket(
    items: Annotated[
        list[str], Field(description='One line per item with the amount, e.g. "rugbrød 1 kg".')
    ],
    stores: StoreNames = None,
) -> dict:
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
