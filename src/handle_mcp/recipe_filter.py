"""list_recipes `without`: drop the recipes that have an unwanted word in the name or in an
ingredient, e.g. "oregano" or "fisk".

A list of recipes has names only, so the ingredients are read per recipe (REMA 1000 sends them
with its list: no extra call). A few at a time, and only for the page that was asked for: never
a loop over all of a store's recipes. The answer says what was dropped and every line that hit.
So the caller sees when a word hit too much ("løg" also hits "hvidløg"), and when a dish is one
line away from fitting: a lasagne with "1 tsk oregano" is cooked without it, as in any kitchen.
The tool sorts; the human decides.
"""

from __future__ import annotations

import asyncio
from typing import Any

from handle_mcp.models import Recipe
from handle_mcp.stores import StoreError
from handle_mcp.stores._http import AT_ONCE


def hits(words: list[str], recipe: Recipe, lines: list[str]) -> list[str]:
    """The name and every ingredient line that hold one of the words, the name first."""
    wanted = [w.strip().casefold() for w in words if w.strip()]
    texts = dict.fromkeys((recipe.name, *lines))
    return [text for text in texts if any(w in text.casefold() for w in wanted)]


async def without(store: Any, recipes: list[Recipe], words: list[str]) -> dict[str, list]:
    """`recipes` in three parts: `recipes` to keep, `dropped` (name, link, `in_name` and the
    lines that hit, in `because`) and `unchecked`: kept, but the store did not give their
    ingredients.
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
        because = hits(words, recipe, [] if failed else f)
        if because:
            out["dropped"].append(
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "url": recipe.url,
                    "in_name": because[0] == recipe.name,
                    "because": because,
                }
            )
            continue
        out["recipes"].append(recipe)
        if failed:
            out["unchecked"].append({"name": recipe.name, "url": recipe.url, "reason": str(f)})
    return out
