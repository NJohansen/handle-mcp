"""list_recipes `ingredients` and `without`: each recipe in a list with its ingredient text.

A list of recipes has names only. With the ingredient lines next to each name, the caller can
pick by any rule: without oregano, with chickpeas, few ingredients, what uses up the cream. The
tool gives the facts and decides nothing: a model knows that salmon is fish and that a lasagne
is cooked without its "1 tsk oregano"; a word filter knows neither.

The lines are read per recipe (REMA 1000 sends them with its list: no extra call), a few at a
time, and only for the page that was asked for: never a loop over all of a store's recipes.
`without` removes nothing. It marks: each recipe gets `hits`, its name and the lines that hold
one of the words, so no word is overlooked in a long list.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

from handle_mcp.models import Recipe
from handle_mcp.stores import StoreError
from handle_mcp.stores._http import AT_ONCE


def hits(words: list[str], name: str, lines: list[str]) -> list[str]:
    """The name and every ingredient line that hold one of the words, the name first."""
    wanted = [w.strip().casefold() for w in words if w.strip()]
    texts = dict.fromkeys((name, *lines))
    return [text for text in texts if any(w in text.casefold() for w in wanted)]


async def with_ingredients(store: Any, recipes: list[Recipe], words: list[str]) -> list[dict]:
    """Each recipe as in the list, plus `ingredients` (null with `ingredients_reason` when the
    store did not give them) and, with `words`, `hits`. Every recipe failing (a queue, a format
    change) raises the first error."""
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
    rows = []
    for recipe, f in zip(recipes, found, strict=True):
        row = dataclasses.asdict(recipe)
        if isinstance(f, BaseException):
            row |= {"ingredients": None, "ingredients_reason": str(f)}
        else:
            row["ingredients"] = f
        if words:
            row["hits"] = hits(words, recipe.name, row["ingredients"] or [])
        rows.append(row)
    return rows
