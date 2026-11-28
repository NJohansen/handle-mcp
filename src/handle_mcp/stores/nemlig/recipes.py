"""nemlig.com recipes: the products behind "Se varer og læg i kurv" and "Ugens udvalgte".

From nemlig's new web API (productbff), found 2026-11-03 (tests/fixtures/nemlig/README.md).
Read only: nemlig's own "add recipe to basket" is never called. The caller puts the
products in the cart with set_cart_quantities, after the human says yes.
"""

from __future__ import annotations

import asyncio
import re
from decimal import Decimal
from typing import Any

from handle_mcp.models import Recipe, RecipeDetails, RecipeItem, RecipeProduct, RecipeSection
from handle_mcp.stores import StoreError

SITE = "https://www.nemlig.com"
BFF = "https://webapi.prod.knl.nemlig.it/productbff/api/web"
SLUG = re.compile(r"^[a-z0-9-]+$")
PLAN = "madplan"  # /maaltider/madplan: "Ugens madplan", earlier weeks, "Mad til flere dage"


def recipe_slug(recipe: str) -> str:
    """'https://www.nemlig.com/maaltider/opskrift/kebabfad-98001303?x=1', the old
    '/opskrifter/kebabfad-98001303' or just 'kebabfad-98001303' → 'kebabfad-98001303'."""
    slug = recipe.strip().split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1].lower()
    if not SLUG.match(slug):
        raise StoreError(f"Kender ikke opskriften {recipe!r}. Brug linket fra nemlig.com.")
    return slug


def _key(text: Any) -> str:
    """'Mad i fad' → 'mad-i-fad', 'Måltidskasse' → 'maaltidskasse': how nemlig spells a path."""
    key = str(text or "").strip().lower().replace(" ", "-")
    for a, b in (("æ", "ae"), ("ø", "oe"), ("å", "aa")):
        key = key.replace(a, b)
    return key


def category_path(category: str, tree: list[dict] | None = None) -> str:
    """'Madpakke', 'Jul/Julefrokost' or just 'julefrokost' → nemlig's path: 'madpakke',
    'juleopskrifter/julefrokost'. `tree` is nemlig's own list of categories, each with its
    sub-categories, matched by title or path. A sub-category is asked for with its parent in
    front: alone, nemlig answers 500 (live, 2026-11-28). An unknown one answers with the list."""
    wanted = "/".join(_key(part) for part in category.split("/") if part.strip())
    known: dict[str, list[str]] = {}
    tops: dict[str, list[str]] = {}
    for top in tree or []:
        path, subs = top.get("categoryPath"), top.get("subCategories") or []
        if not path:
            continue
        names = {_key(top.get("title")), path}
        tops[path] = [f"{path}/{s['categoryPath']}" for s in subs if s.get("categoryPath")]
        for name in names:
            known.setdefault(name, []).append(path)
        for sub in subs:
            if not sub.get("categoryPath"):
                continue
            full = f"{path}/{sub['categoryPath']}"
            for own in {_key(sub.get("title")), sub["categoryPath"]}:
                for key in (own, *(f"{name}/{own}" for name in names)):
                    if full not in known.setdefault(key, []):
                        known[key].append(full)
    if not tops:  # nemlig sent no list: send the words as a path, as before
        if not SLUG.match(wanted):
            raise StoreError(f"Kender ikke kategorien {category!r}. Brug fx aftensmad.")
        return wanted
    found = known.get(wanted) or []
    if len(found) == 1:
        return found[0]
    if found:
        raise StoreError(f"nemlig har {category!r} flere steder. Brug en af: {', '.join(found)}.")
    top = next((t for t in known.get(wanted.split("/")[0]) or [] if t in tops), None)
    names = ", ".join(tops[top] if top and tops[top] else [*tops, PLAN])
    raise StoreError(f"nemlig kender ikke kategorien {category!r}. Brug en af: {names}.")


def _row(store: str, row: dict, group: str | None) -> Recipe:
    """One recipe in a list. nemlig's lists have no time and no persons: its tags on the
    recipe ("Under 30 min", "Familievenlig") are what it says there."""
    marks = [*(row.get("highlightedFilters") or []), *(row.get("generalFilters") or [])]
    tags = [t for f in marks if isinstance(f, dict) and (t := _text(f.get("title")))]
    return Recipe(
        store=store,
        id=row["id"],
        name=row.get("title", ""),
        url=f"{SITE}/maaltider/opskrift/{row['id']}",
        group=group,
        tags=list(dict.fromkeys(tags)),
    )


def _product(item: dict) -> RecipeProduct:
    p = item.get("product") or {}
    campaign = next((c.get("text") for c in p.get("campaignLines") or [] if c.get("text")), None)
    return RecipeProduct(
        id=str(p["id"]),
        name=p.get("title", ""),
        price=Decimal(str(p.get("price") or 0)) / 100,  # øre
        quantity=int(item.get("quantity") or 1),
        size=p.get("description") or None,
        available=(p.get("availability") or {}).get("type", "Available") == "Available",
        offer_text=campaign,
    )


def _items(rows: list[dict], have_at_home: bool) -> list[RecipeItem]:
    return [
        RecipeItem(
            ingredient=row.get("ingredientTitle") or row.get("ingredientId", ""),
            product=_product(row["item"]),
            have_at_home=have_at_home,
            alternatives=[_product(a) for a in row.get("alternatives") or [] if a.get("product")],
        )
        for row in rows
        if (row.get("item") or {}).get("product", {}).get("id")
    ]


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _int(value: Any) -> int | None:
    """A count the store may send as "4", 4 or junk: junk is None, never a crash."""
    try:
        return int(value) or None
    except (TypeError, ValueError):
        return None


def _method(details: dict) -> list[RecipeSection]:
    """recipeDetails `instructions`: sections ("Kebabfad", "Salat") with steps in order."""
    sections = []
    for group in details.get("instructions") or []:
        steps = [t for s in group.get("steps") or [] if (t := _text(s.get("description")))]
        if steps:
            sections.append(RecipeSection(title=_text(group.get("title")), steps=steps))
    return sections


def _image(details: dict) -> str | None:
    """The dish's photo: the first https image. The byline's portrait is not the dish."""
    return next(
        (
            s
            for i in details.get("images") or []
            if (s := _text(i.get("source"))) and s.startswith("https://")
        ),
        None,
    )


class RecipesMixin:
    """Recipe methods for NemligStore. Uses its logged-in `_api`."""

    name: str
    _api: Any
    _timeslot_id: Any
    _tags: dict[str, str]
    _tag_names: list[str]
    _categories: list[dict]

    async def recipes(self, query: str, limit: int = 5) -> list[Recipe]:
        """nemlig's recipe search, as on the website. The old search (searchgateway) also finds
        recipes that the new API no longer has (500 on get_recipe, live 2026-11-03), so not that.
        Name and link only: get_recipe gives time, persons and products."""
        params: dict[str, Any] = {"query": query, "take": limit, "skip": 0}
        if slot := await self._timeslot_id():
            params["timeslotId"] = slot
        data = await self._api("GET", f"{BFF}/search/recipes", params=params) or {}
        hits = (data.get("searchResult") or {}).get("items")
        if not isinstance(hits, list):
            raise StoreError("nemlig-opskrifter har ændret format.")
        return [
            Recipe(
                store=self.name,
                id=h["id"],
                name=h.get("title", ""),
                url=f"{SITE}/maaltider/opskrift/{h['id']}",
            )
            for h in hits[:limit]
            if h.get("id")
        ]

    async def recipe(self, recipe_id: str, persons: int | None = None) -> RecipeDetails:
        slug = recipe_slug(recipe_id)
        params: dict[str, Any] = {"recipeId": slug, "maxProductsPerIngredient": 10}
        if slot := await self._timeslot_id():
            params["timeSlotId"] = slot
        if persons:
            params["servings"] = persons
        details, dialog = await asyncio.gather(
            self._api("GET", f"{BFF}/meals/recipeDetails/{slug}"),
            self._api("GET", f"{BFF}/meals/recipeProductDialog", params=params),
        )
        details, dialog = details or {}, dialog or {}
        if "includedProducts" not in dialog:
            raise StoreError("nemlig-opskriften har ændret format.")
        items = _items(dialog["includedProducts"] or [], False)
        items += _items(dialog.get("selfSuppliedProducts") or [], True)
        limits = dialog.get("servingLimits") or details.get("servingLimits") or {}
        minutes = (details.get("durationTotal") or {}).get("from")
        return RecipeDetails(
            store=self.name,
            id=slug,
            name=dialog.get("title") or details.get("title", ""),
            url=f"{SITE}/maaltider/opskrift/{slug}",
            persons=_int(dialog.get("servings")) or _int(details.get("servings")) or persons or 0,
            min_persons=limits.get("minServings"),
            max_persons=limits.get("maxServings"),
            time=f"{minutes} min" if minutes else None,
            description=_text(details.get("description")),
            image=_image(details),
            ingredients=[
                i["text"]
                for group in details.get("ingredients") or []
                for i in group.get("ingredients") or []
                if i.get("text")
            ],
            # recipeDetails has no servings parameter: its text is always for the recipe's own
            # servings, while the products follow `persons` (live, 2026-11-05).
            ingredients_persons=_int(details.get("servings")),
            method=_method(details),
            tip=_text(details.get("tip")),
            items=items,
            total=sum(
                (i.product.price * i.product.quantity for i in items if not i.have_at_home),
                Decimal(0),
            ),
        )

    async def featured_recipes(self, limit: int = 20) -> list[Recipe]:
        """nemlig's "Ugens udvalgte" (/maaltider), grouped by theme."""
        return (await self._page_recipes("/maaltider", "Ugens udvalgte"))[:limit]

    async def _page_recipes(self, path: str, title: str) -> list[Recipe]:
        """Every recipe on one of nemlig's recipe pages, in page order. A block's heading
        ("Mad i fad", "Madplanen fra uge 46") is the recipe's group. Two kinds of block: a
        list of recipes, and a grid of cards that link to one ("Ugens madplan": "Mandag:
        Marry me chicken", with nemlig's line under it, "⚡ Klar på 30 min", as its tag)."""
        page = await self._api("GET", f"{BFF}/page", params={"path": path}) or {}
        found: list[Recipe] = []
        for block in page.get("pageContent") or []:
            group = _text((block.get("header") or {}).get("title"))
            for row in block.get("recipes") or []:
                if isinstance(row, dict) and row.get("id"):
                    found.append(_row(self.name, row, group))
            for card in block.get("items") or []:
                link = _text(card.get("url")) if isinstance(card, dict) else None
                slug = (link or "").rsplit("/", 1)[-1]
                if not link or "/maaltider/opskrift/" not in link or not SLUG.match(slug):
                    continue
                mark = _text(card.get("description"))
                found.append(
                    Recipe(
                        store=self.name,
                        id=slug,
                        name=_text(card.get("title")) or "",
                        url=f"{SITE}/maaltider/opskrift/{slug}",
                        group=group,
                        tags=[mark] if mark else [],
                    )
                )
        if not found:
            raise StoreError(f"Fandt ingen opskrifter i nemligs '{title}'.")
        return found

    async def recipes_by_tag(
        self, tags: list[str], category: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[Recipe]:
        """All of nemlig's recipes with every tag, e.g. ["Familievenlig", "Under 30 min"],
        `limit` of them after the first `offset`. Tags are matched on nemlig's own list, by
        title or path. Category defaults to nemlig's "aftensmad"; "madplan" is nemlig's page
        of week plans, which has no tags to ask by."""
        if category and _key(category) == PLAN:
            if tags:
                raise StoreError("nemligs madplan kan ikke filtreres på tags. Udelad tags.")
            return (await self._page_recipes(f"/maaltider/{PLAN}", "Madplan"))[
                offset : offset + limit
            ]
        known = await self._recipe_tags()
        paths = []
        for tag in tags:
            path = known.get(tag.strip().lower())
            if not path:
                names = ", ".join(self._tag_names)
                raise StoreError(f"nemlig kender ikke tagget {tag!r}. Brug et af: {names}.")
            paths.append(path)
        params: dict[str, Any] = {"skip": offset, "take": limit, "filters": paths}
        if category:
            params["categoryPath"] = category_path(category, self._categories)
        data = await self._api("GET", f"{BFF}/meals/allRecipes", params=params) or {}
        found = data.get("requestedCategory") or {}
        if not isinstance(found.get("recipes"), list):
            raise StoreError("nemlig-opskrifter har ændret format.")
        return [
            _row(self.name, r, found.get("title"))
            for r in found["recipes"]
            if isinstance(r, dict) and r.get("id")
        ][:limit]

    async def _recipe_tags(self) -> dict[str, str]:
        """nemlig's tags, by lower-case title and by path → path. The same answer has nemlig's
        categories. Cached: they rarely change."""
        if not getattr(self, "_tags", None):
            data = await self._api("GET", f"{BFF}/meals/allRecipes", params={"skip": 0, "take": 1})
            found = [
                f
                for group in (data or {}).get("filters") or []
                for f in group.get("filters") or []
                if f.get("path")
            ]
            if not found:
                raise StoreError("nemlig-opskrifter har ændret format: ingen tags.")
            categories = (data or {}).get("categories")
            self._categories = categories if isinstance(categories, list) else []
            self._tag_names = [str(f.get("title") or f["path"]).strip() for f in found]
            self._tags = {
                key.strip().lower(): f["path"]
                for f in found
                for key in (str(f.get("title") or ""), f["path"])
                if key.strip()
            }
        return self._tags
