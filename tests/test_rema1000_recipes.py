"""REMA 1000 recipes against a fake backend (httpx.MockTransport). No network."""

import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from handle_mcp import recipe_cart
from handle_mcp.stores import StoreError
from handle_mcp.stores import rema1000 as rema_module
from handle_mcp.stores.rema1000 import Rema1000Store
from handle_mcp.stores.rema1000.recipes import recipe_slug

FIXTURES = Path(__file__).parent / "fixtures" / "rema1000"
NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)  # inside the offer week in recipe_lasagne.json
AVIS = "5Q5t9rpmNk4jp1ygKZDEHx"  # the tag "Avisopskrifter"
AFTENSMAD = "6mjo9YHow8fdXyG4LhmHoK"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeRema:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.recipe = fixture("recipe_lasagne")
        self.listing = fixture("recipes_by_tag")
        self.status = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        if self.status != 200:
            return httpx.Response(self.status, text="<html>kø</html>")
        if request.url.path.endswith("search/recipes"):
            return httpx.Response(200, json=fixture("recipes_search"))
        if params.get("filter[type]") == "recipeTag":
            return httpx.Response(200, json=fixture("recipe_tags"))
        if slug := params.get("filter[slug]"):
            found = self.recipe if slug == "lasagne" else {"data": [], "meta": {}}
            return httpx.Response(200, json=found)
        return httpx.Response(200, json=self.listing)


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture(autouse=True)
def _in_the_offer_week(monkeypatch):
    monkeypatch.setattr(rema_module, "datetime", _Clock)


@pytest.fixture
def fake():
    return FakeRema()


@pytest.fixture
def store(fake):
    return Rema1000Store(httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)))


@pytest.mark.parametrize(
    "given",
    [
        "lasagne",
        "/opskrifter/lasagne",
        "https://shop.rema1000.dk/opskrifter/lasagne?utm=x#top",
        "https://madogdrikke.rema1000.dk/opskrifter/Lasagne/",
    ],
)
def test_a_link_or_an_id_is_the_slug(given):
    assert recipe_slug(given) == "lasagne"


def test_a_strange_recipe_id_is_refused():
    with pytest.raises(StoreError, match="Kender ikke opskriften"):
        recipe_slug("lasagne med ost")


async def test_search_gives_name_link_and_persons(store, fake):
    found = await store.recipes("lasagne", limit=2)
    assert [(r.id, r.name, r.persons) for r in found] == [
        ("lasagne", "Lasagne", 4),
        ("glutenfri-lasagne", "Glutenfri lasagne", None),  # REMA writes 0 persons
    ]
    assert found[0].url == "https://shop.rema1000.dk/opskrifter/lasagne"
    assert found[0].time is None  # totalTime 0: REMA gives no time
    (request,) = fake.requests
    assert request.url.params["query"] == "lasagne" and request.url.params["per_page"] == "2"
    assert "authorization" not in request.headers  # public: no login is sent


async def test_recipe_has_products_text_and_method(store):
    recipe = await store.recipe("https://shop.rema1000.dk/opskrifter/lasagne")
    assert (recipe.id, recipe.name, recipe.persons) == ("lasagne", "Lasagne", 4)
    assert recipe.ingredients_persons == recipe.min_persons == recipe.max_persons == 4
    assert recipe.image.startswith("https://") and recipe.time is None
    assert recipe.ingredients[:3] == ["400 g hakket oksekød", "1 stk løg", "2 fed hvidløg"]
    assert recipe.ingredients.count("salt") == 1  # no amount: the name alone, said once
    assert [s.title for s in recipe.method] == ["Kødsauce", "Béchamelsauce", "Lasagne"]
    assert all(s.steps for s in recipe.method)
    beef = recipe.items[0]
    assert (beef.ingredient, beef.product.id, beef.product.name) == (
        "hakket oksekød",
        "400176",
        "HK. OKSEKØD 15-18%",
    )
    assert beef.product.price == Decimal(29) and beef.product.quantity == 1
    assert beef.product.size == "400 GR." and beef.product.offer_text.startswith("Avisvare")
    assert not beef.have_at_home and beef.alternatives == []


async def test_basic_ingredients_are_have_at_home_and_not_in_the_total(store):
    recipe = await store.recipe("lasagne")
    home = {i.ingredient for i in recipe.items if i.have_at_home}
    assert {"salt", "peber", "olivenolie", "smør", "hvedemel", "løg"} <= home
    buy = [i for i in recipe.items if not i.have_at_home]
    assert recipe.total == sum(i.product.price * i.product.quantity for i in buy)
    assert recipe.total == Decimal("87.00")  # the price REMA shows for the recipe
    # salt and peber are in two parts of the recipe; the second has 0 packs and is left out
    assert [i.ingredient for i in recipe.items].count("salt") == 1
    assert all(i.product.quantity >= 1 for i in recipe.items)


async def test_an_ingredient_without_a_product_stays_in_the_text_only(store, fake):
    fake.recipe = copy.deepcopy(fake.recipe)
    rows = fake.recipe["data"][0]["fields"]["customForm"]["ingredientGroups"][0]["ingredients"]
    rows[0]["digitalProduct"]["active_product"] = None  # not on the shelf
    rows[1]["digitalProduct"] = None  # REMA picked no product
    recipe = await store.recipe("lasagne")
    assert recipe.ingredients[:2] == ["400 g hakket oksekød", "1 stk løg"]
    assert "hakket oksekød" not in {i.ingredient for i in recipe.items}
    assert "løg" not in {i.ingredient for i in recipe.items}


async def test_persons_are_the_recipes_own(store):
    recipe = await store.recipe("lasagne", persons=8)
    assert recipe.persons == 4 and recipe.items[0].product.quantity == 1


async def test_the_cart_plan_leaves_out_what_you_have(store):
    lines, skipped = recipe_cart.plan(await store.recipe("lasagne"))
    assert lines["400176"]["quantity"] == 1 and "93605" not in lines  # salt
    assert {"ingredient": "salt", "name": "SALT M/ JOD", "reason": skipped[0]["reason"]} in skipped


async def test_an_unknown_recipe_says_so(store):
    with pytest.raises(StoreError, match="har ingen opskrift 'findes-ikke'"):
        await store.recipe("findes-ikke")


async def test_a_changed_recipe_says_update(store, fake):
    fake.recipe = copy.deepcopy(fake.recipe)
    del fake.recipe["data"][0]["fields"]["customForm"]["ingredientGroups"]
    with pytest.raises(StoreError, match="har ændret"):
        await store.recipe("lasagne")


async def test_featured_is_the_leaflet_recipes_newest_first(store, fake):
    found = await store.featured_recipes(limit=2)
    assert len(found) == 2 and all(r.group == "Avisopskrifter" for r in found)
    assert found[0].id == "medister-med-kartofler-og-appelsinsalat-hertil-favoritsauce"
    params = fake.requests[-1].url.params
    assert params["filter[tags.sys.id]"] == AVIS and params["sort"] == "-created_at"
    assert params["filter[type]"] == "recipe"


async def test_a_tag_is_matched_by_title_or_slug_and_category_is_a_tag(store, fake):
    await store.recipes_by_tag(["Aftensmad"])
    assert fake.requests[-1].url.params["filter[tags.sys.id]"] == AFTENSMAD
    assert fake.requests[-1].url.params["sort"] == "-popularity"
    await store.recipes_by_tag([], category="aftensmad")
    assert fake.requests[-1].url.params["filter[tags.sys.id]"] == AFTENSMAD
    tag_calls = [r for r in fake.requests if r.url.params.get("filter[type]") == "recipeTag"]
    assert len(tag_calls) == 1  # the tags are read once


async def test_every_tag_must_be_on_the_recipe(store, fake):
    # the fixture's recipes have the tag Avisopskrifter only
    assert await store.recipes_by_tag(["Avisopskrifter", "Aftensmad"]) == []
    fake.listing = copy.deepcopy(fake.listing)
    fake.listing["meta"]["pagination"]["last_page"] = 1
    fake.listing["data"][1]["fields"]["tags"].append({"id": AFTENSMAD})
    found = await store.recipes_by_tag(["Avisopskrifter"], category="Aftensmad")
    assert [r.name for r in found] == [fake.listing["data"][1]["fields"]["title"]]
    assert found[0].group == "Avisopskrifter + Aftensmad"


async def test_tags_page_until_the_limit(store, fake):
    fake.listing = copy.deepcopy(fake.listing)
    fake.listing["meta"]["pagination"]["last_page"] = 9
    found = await store.recipes_by_tag(["Avisopskrifter"], limit=7)
    pages = [r.url.params["page"] for r in fake.requests if "page" in r.url.params]
    assert len(found) == 7 and pages == ["1", "2", "3"]  # 3 per page in the fixture
    fake.requests.clear()
    assert await store.recipes_by_tag(["Avisopskrifter", "Aftensmad"]) == []
    assert len(fake.requests) == 5  # never more than 5 pages


async def test_an_unknown_tag_answers_with_remas_list(store):
    with pytest.raises(StoreError, match="kender ikke tagget 'Mexicansk'.*Aftensmad.*Kødfri"):
        await store.recipes_by_tag(["Mexicansk"])


async def test_a_queue_page_is_a_clear_error(store, fake):
    fake.status = 503
    with pytest.raises(StoreError, match="REMA 1000 svarer 503"):
        await store.recipes("lasagne")
