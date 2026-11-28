"""list_recipes `without`: drop the recipes that have an unwanted word in the name or in an
ingredient, e.g. "oregano" or "fisk".

A list of recipes has names only, so the ingredients are read per recipe (REMA 1000 sends them
with its list: no extra call). A few at a time, and only for the page that was asked for: never
a loop over all of a store's recipes. The answer says what was dropped and why, so the caller
can see when a word hit too much ("løg" also hits "hvidløg").
"""

from __future__ import annotations

import asyncio
from typing import Any

from handle_mcp.models import Recipe
from handle_mcp.stores import StoreError
from handle_mcp.stores._http import AT_ONCE


def hit(words: list[str], recipe: Recipe, lines: list[str]) -> str | None:
    """The name or the first ingredient line that holds one of the words, else None."""
    wanted = [w.strip().casefold() for w in words if w.strip()]
    for text in (recipe.name, *lines):
        if any(w in text.casefold() for w in wanted):
            return text
    return None


async def without(store: Any, recipes: list[Recipe], words: list[str]) -> dict[str, list]:
    """`recipes` in three parts: `recipes` to keep, `dropped` (name, link and the line that
    hit, in `because`) and `unchecked`: kept, but the store did not give their ingredients.
    Every recipe failing (a queue, a format change) raises the first error."""
    gate = asyncio.Semaphore(AT_ONCE)

    async def lines(recipe: Recipe) -> list[str]:
        async with gate:
            return await store.recipe_ingredients(recipe.id)

    found = await asyncio.gather(*(lines(r) for r in recipes), return_exceptions=True)
    for f in found:  # anything but a store error is a bug: let the server log it
        if isinstance(f, BaseException) and not isinstance(f, StoreError):
            raise f
    if found and all(isinstance(f, StoreError) for f in found):
        raise found[0]
    out: dict[str, list] = {"recipes": [], "dropped": [], "unchecked": []}
    for recipe, f in zip(recipes, found, strict=True):
        failed = isinstance(f, BaseException)
        because = hit(words, recipe, [] if failed else f)
        if because:
            out["dropped"].append({"name": recipe.name, "url": recipe.url, "because": because})
            continue
        out["recipes"].append(recipe)
        if failed:
            out["unchecked"].append({"name": recipe.name, "url": recipe.url, "reason": str(f)})
    return out
