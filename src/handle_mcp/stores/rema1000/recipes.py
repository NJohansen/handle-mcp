"""REMA 1000 recipes: the pages under shop.rema1000.dk/opskrifter. Public: no login.

Three calls, as the website makes them (seen 2026-11-23, tests/fixtures/rema1000/README.md):
`search/recipes?query=` (the search), `rema1000dk/entities?filter[type]=recipe` with
`filter[slug]` (one recipe) or `filter[tags.sys.id]` (a tag page), and
`rema1000dk/entities?filter[type]=recipeTag` (the tags). A recipe has its ingredients with the
product REMA picks for each and `amount`: packs for the recipe's own persons. No call scales to
other persons and no ingredient has alternatives. Read only.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from handle_mcp.models import Recipe, RecipeDetails, RecipeItem, RecipeProduct, RecipeSection
from handle_mcp.stores import StoreError
from handle_mcp.stores.rema1000.auth import SHOP

SLUG = re.compile(r"^[a-z0-9-]+$")
FEATURED = "ugens-avisopskrifter"  # "Avisopskrifter": dinners made from this week's leaflet
PAGE, MAX_PAGE = 20, 100  # recipes per page: as the website asks, and the most asked for
MAX_PAGES = 8  # pages of MAX_PAGE read for a mix of tags: more than all of REMA's recipes
KEEP = 600  # seconds a mix of tags is kept, so its next page reads nothing again
PLAN = "madplan"  # REMA has no week plan: its dinners from this week's leaflet are the nearest
CHANGED = "REMA 1000 har ændret sine opskrifter. handle-mcp skal opdateres."


def recipe_slug(recipe: str) -> str:
    """'https://shop.rema1000.dk/opskrifter/lasagne?x=1', '/opskrifter/lasagne' or 'lasagne'
    → 'lasagne'."""
    slug = recipe.strip().split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1].lower()
    if not SLUG.match(slug):
        raise StoreError(f"Kender ikke opskriften {recipe!r}. Brug linket fra shop.rema1000.dk.")
    return slug


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _form(entity: dict) -> dict:
    return (entity.get("fields") or {}).get("customForm") or {}


def _persons(form: dict) -> int | None:
    """None when REMA writes the recipe for pieces ("12 stk."), not persons."""
    servings = form.get("servings") or {}
    amount = servings.get("amount")
    if servings.get("type") != "person" or not isinstance(amount, int) or isinstance(amount, bool):
        return None
    return amount or None


def _time(form: dict) -> str | None:
    minutes = form.get("totalTime")
    return f"{minutes} min" if isinstance(minutes, int) and minutes > 0 else None


def _summary(entity: dict, group: str | None = None) -> Recipe | None:
    fields = entity.get("fields") or {}
    slug = fields.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug):
        return None
    form = _form(entity)
    return Recipe(
        store="rema1000",
        id=slug,
        name=str(fields.get("title") or ""),
        url=f"{SHOP}/opskrifter/{slug}",
        time=_time(form),
        persons=_persons(form),
        group=group,
        tags=[
            title
            for t in fields.get("tags") or []
            if isinstance(t, dict) and (title := _text((t.get("fields") or {}).get("title")))
        ],
    )


def _amount(value: Any) -> str:
    """400 → '400', 0.5 → '0,5', 0 or junk → '' (salt has no amount)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return ""
    return f"{Decimal(str(value)).normalize():f}".replace(".", ",")


def _line(row: dict) -> str | None:
    """'400 g hakket oksekød', '1 stk løg', 'salt'."""
    name = _text(row.get("ingredient"))
    if not name:
        return None
    parts = [_amount(row.get("amountOfContent")), _text(row.get("unitOfContent")), name]
    return " ".join(p for p in parts if p) if parts[0] else name


def _last_page(data: dict) -> int:
    return ((data.get("meta") or {}).get("pagination") or {}).get("last_page") or 1


def _tag_ids(entity: dict) -> set[str]:
    tags = (entity.get("fields") or {}).get("tags") or []
    return {str(t.get("id")) for t in tags if isinstance(t, dict)}


class RemaRecipesMixin:
    """Recipe methods for Rema1000Store. Uses its `_get` and its `_product`."""

    name: str
    _get: Any
    _product: Callable[[dict], Any]
    _recipe_tag_ids: dict[str, str]
    _recipe_tag_names: dict[str, str]
    _mixes: dict[tuple[str, ...], tuple[float, list[Recipe]]]

    async def recipes(self, query: str, limit: int = 5) -> list[Recipe]:
        data = await self._get("search/recipes", {"query": query, "per_page": limit, "page": 1})
        found = [_summary(e) for e in data["data"] if isinstance(e, dict)]
        return [r for r in found if r][:limit]

    async def recipe(self, recipe_id: str, persons: int | None = None) -> RecipeDetails:
        """One recipe with REMA's product per ingredient. `persons` is not used: REMA gives
        packs for the recipe's own persons only, and those come back."""
        slug = recipe_slug(recipe_id)
        data = await self._get(
            "rema1000dk/entities", {"filter[type]": "recipe", "filter[slug]": slug}
        )
        entity = next((e for e in data["data"] if isinstance(e, dict)), None)
        if entity is None:
            raise StoreError(f"REMA 1000 har ingen opskrift {slug!r}. Brug linket fra søgningen.")
        fields, form = entity.get("fields") or {}, _form(entity)
        groups = form.get("ingredientGroups")
        if not isinstance(groups, list):
            raise StoreError(CHANGED)
        rows = [
            r
            for g in groups
            if isinstance(g, dict)
            for r in g.get("ingredients") or []
            if isinstance(r, dict)
        ]
        items = self._recipe_items(rows)
        own = _persons(form)
        return RecipeDetails(
            store=self.name,
            id=slug,
            name=str(fields.get("title") or ""),
            url=f"{SHOP}/opskrifter/{slug}",
            persons=own,
            min_persons=own,
            max_persons=own,
            time=_time(form),
            description=_text(form.get("preparationTextBefore")),
            image=_text((fields.get("image") or {}).get("url")),
            # salt and peber are in more parts of a recipe: the same line is said once
            ingredients=list(dict.fromkeys(line for r in rows if (line := _line(r)))),
            ingredients_persons=own,
            method=[
                RecipeSection(title=_text(g.get("name")), steps=steps)
                for g in form.get("preparationGroups") or []
                if isinstance(g, dict)
                and (steps := [t for s in g.get("steps") or [] if (t := _text(s.get("step")))])
            ],
            tip=_text(form.get("preparationTextAfter")),
            items=items,
            total=sum(
                (i.product.price * i.product.quantity for i in items if not i.have_at_home),
                Decimal(0),
            ),
        )

    def _recipe_items(self, rows: list[dict]) -> list[RecipeItem]:
        """One item per ingredient that has a product on the shelf. REMA lists salt in two
        parts of a recipe and gives the second 0 packs: that one adds nothing, so it is left
        out. An ingredient without a product stays in the recipe's `ingredients` text."""
        items = []
        for row in rows:
            picked = row.get("digitalProduct") or {}
            packs = picked.get("amount")
            found = self._product(picked.get("active_product") or {})
            if found is None or not isinstance(packs, int) or packs < 1:
                continue
            items.append(
                RecipeItem(
                    ingredient=_text(row.get("ingredient")) or found.name,
                    product=RecipeProduct(
                        id=found.id,
                        name=found.name,
                        price=found.price,
                        quantity=packs,
                        size=found.size,
                        offer_text=found.offer_text,
                    ),
                    # REMA's own marks: a basic ingredient (salt, flour) and "not on the list"
                    have_at_home=bool(
                        picked.get("is_basic_ingredient") or row.get("isExcludedFromShoppingList")
                    ),
                )
            )
        return items

    async def featured_recipes(self, limit: int = 20) -> list[Recipe]:
        """REMA's "Avisopskrifter": dinners made from this week's leaflet, the newest first."""
        return await self.recipes_by_tag([FEATURED], None, limit, sort="-created_at")

    async def recipes_by_tag(
        self,
        tags: list[str],
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "-popularity",
    ) -> list[Recipe]:
        """REMA's recipes with every tag, the most popular first, `limit` of them after the
        first `offset`. REMA has tags only, so a `category` is one more tag ("Aftensmad",
        "Frokost"); "madplan" is the leaflet's dinners, the newest first. Matched on REMA's own
        list, by title or slug."""
        if category and category.strip().lower() == PLAN:
            category, sort = FEATURED, "-created_at"
        known = await self._recipe_tags()
        ids = []
        for tag in [*tags, *([category] if category else [])]:
            tag_id = known.get(tag.strip().lower())
            if not tag_id:
                names = "; ".join(sorted(self._recipe_tag_names.values()))
                raise StoreError(f"REMA 1000 kender ikke tagget {tag!r}. Brug et af: {names}.")
            if tag_id not in ids:
                ids.append(tag_id)
        group = " + ".join(self._recipe_tag_names[i] for i in ids)
        if len(ids) > 1:
            return (await self._mix(ids, sort, group))[offset : offset + limit]
        size = min(MAX_PAGE, max(PAGE, limit))
        page, skip = offset // size + 1, offset % size
        found: list[Recipe] = []
        while True:
            data = await self._tag_page(ids[0], sort, size, page)
            found += [r for e in data["data"] if isinstance(e, dict) and (r := _summary(e, group))]
            if len(found) >= skip + limit or page >= _last_page(data) or not data["data"]:
                return found[skip : skip + limit]
            page += 1

    async def _tag_page(self, tag_id: str, sort: str, size: int, page: int) -> dict:
        params = {"filter[type]": "recipe", "filter[tags.sys.id]": tag_id, "sort": sort}
        return await self._get("rema1000dk/entities", params | {"per_page": size, "page": page})

    async def _mix(self, ids: list[str], sort: str, group: str) -> list[Recipe]:
        """Every recipe that has all the tags. The call filters on one tag only, so the tag
        with the fewest recipes is read to its end and the other tags are checked in the
        answer. Kept for KEEP seconds: the next page of the same mix asks REMA nothing."""
        if not hasattr(self, "_mixes"):
            self._mixes = {}
        kept = self._mixes.get((*ids, sort))
        if kept and kept[0] > time.monotonic():
            return kept[1]
        firsts = await asyncio.gather(*(self._tag_page(i, sort, 1, 1) for i in ids))
        totals = [((d.get("meta") or {}).get("pagination") or {}).get("total") for d in firsts]
        if not all(isinstance(t, int) for t in totals):
            raise StoreError(CHANGED)
        fewest = ids[totals.index(min(totals))]
        found: list[Recipe] = []
        for page in range(1, MAX_PAGES + 1):
            data = await self._tag_page(fewest, sort, MAX_PAGE, page)
            found += [
                r
                for e in data["data"]
                if isinstance(e, dict) and set(ids) <= _tag_ids(e) and (r := _summary(e, group))
            ]
            if page >= _last_page(data) or not data["data"]:
                break
        self._mixes[(*ids, sort)] = (time.monotonic() + KEEP, found)
        return found

    async def _recipe_tags(self) -> dict[str, str]:
        """REMA's tags, by lower-case title and by slug → id. Cached: they rarely change."""
        if not getattr(self, "_recipe_tag_ids", None):
            data = await self._get(
                "rema1000dk/entities", {"filter[type]": "recipeTag", "per_page": 100}
            )
            ids: dict[str, str] = {}
            names: dict[str, str] = {}
            for tag in data["data"]:
                fields = tag.get("fields") if isinstance(tag, dict) else None
                if not isinstance(fields, dict) or not tag.get("id"):
                    continue
                title, slug = _text(fields.get("title")), _text(fields.get("slug"))
                names[str(tag["id"])] = title or slug or ""
                for key in (title, slug):
                    if key:
                        ids.setdefault(key.lower(), str(tag["id"]))
            if not ids:
                raise StoreError(CHANGED)
            self._recipe_tag_ids, self._recipe_tag_names = ids, names
        return self._recipe_tag_ids
