"""UTM tags on links to a store's cart."""

from urllib.parse import parse_qs, urlsplit

from handle_mcp import server
from handle_mcp.links import UTM, cart_url, with_utm
from handle_mcp.stores.bilkatogo import BilkaStore
from handle_mcp.stores.nemlig import NemligStore

TAGS = "utm_source=handlemcp&utm_medium=mcp&utm_campaign=cart"


def test_adds_the_tags_to_a_bare_link():
    assert with_utm("https://www.bilkatogo.dk/kurv") == f"https://www.bilkatogo.dk/kurv?{TAGS}"


def test_keeps_other_parameters_and_the_fragment():
    url = with_utm("https://example.com/kurv?ref=1&empty=&a=%C3%A6#top")
    parts = urlsplit(url)
    assert parts.fragment == "top"
    assert parse_qs(parts.query, keep_blank_values=True) == {
        "ref": ["1"],
        "empty": [""],
        "a": ["æ"],
        **{k: [v] for k, v in UTM.items()},
    }


def test_replaces_old_tags_instead_of_doubling_them():
    url = with_utm("https://example.com/?utm_source=other&utm_campaign=x&ref=1")
    assert parse_qs(urlsplit(url).query) == {"ref": ["1"], **{k: [v] for k, v in UTM.items()}}


def test_twice_is_the_same_as_once():
    once = with_utm("https://example.com/kurv?ref=1")
    assert with_utm(once) == once


def test_every_store_has_a_tagged_cart_link():
    for store in (NemligStore, BilkaStore):
        url = cart_url(store)
        assert url and url.startswith("https://") and url.endswith(TAGS)


def test_a_store_without_a_cart_page_has_no_link():
    assert cart_url(object()) is None


async def test_cart_answers_carry_the_tagged_link():
    expected = f"https://example.com/kurv?ref=1&{TAGS}"
    assert (await server.get_cart("fake"))["url"] == expected
    assert (await server.get_cart())["fake"]["url"] == expected
    result = await server.set_cart_quantities("fake", {"2": 1})
    assert result["cart"]["url"] == expected
    result = await server.add_recipe_to_cart("fake", "r1")
    assert result["cart"]["url"] == expected
