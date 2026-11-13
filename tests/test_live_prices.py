"""Read-only: the price in a search answer is the price the cart charges.

Run: HANDLE_LIVE=1 uv run pytest -m live -s tests/test_live_prices.py
It reads the cart as it is and searches for each line. It NEVER changes the cart, so an empty
cart skips the test. Why: #155, where nemlig's search said 82 kr and the cart charged 99 kr.
"""

import os
import re
from decimal import Decimal

import pytest

from handle_mcp.models import CartLine, Product
from handle_mcp.stores import STORES

live = pytest.mark.skipif(os.environ.get("HANDLE_LIVE") != "1", reason="set HANDLE_LIVE=1")

# "2 for 80 kr": the cart price depends on the count, so price x quantity says nothing.
MULTI_BUY = re.compile(r"\d+\s+(for|stk)\b", re.IGNORECASE)
MOST = 15  # lines to check: one search per line


def compare(lines, found) -> tuple[list[str], list[str], int]:
    """(wrong, not checked, checked) for cart lines against the products a search found."""
    wrong, unchecked, checked = [], [], 0
    for line in lines:
        product = found.get(line.product_id)
        if product is None:
            unchecked.append(f"{line.name}: ikke fundet i søgningen")
        elif MULTI_BUY.search(product.offer_text or ""):
            unchecked.append(f"{line.name}: flerkøb ({product.offer_text})")
        elif line.quantity < 1:
            unchecked.append(f"{line.name}: antal {line.quantity}")
        else:
            checked += 1
            each = line.line_total / line.quantity
            if abs(each - product.price) > Decimal("0.01"):
                wrong.append(
                    f"{line.name} ({line.product_id}): søgning {product.price} kr, kurv {each} kr"
                )
    return wrong, unchecked, checked


def test_compare_finds_the_line_the_cart_charges_more_for():
    """No network: the case from #155, next to lines the check must leave alone."""

    def product(pid, price, offer_text=None):
        return Product("nemlig", pid, "vare", Decimal(price), offer_text=offer_text)

    lines = [
        CartLine("1", "Pepsi Max", 2, Decimal("198.00")),
        CartLine("2", "Mælk", 3, Decimal("38.85")),
        CartLine("3", "Cola", 2, Decimal("80.00")),
        CartLine("4", "Udgået", 1, Decimal("10.00")),
    ]
    found = {
        "1": product("1", "82.00"),
        "2": product("2", "12.95"),
        "3": product("3", "41.25", "2 for 80 kr"),
    }
    wrong, unchecked, checked = compare(lines, found)
    assert checked == 2
    assert wrong == ["Pepsi Max (1): søgning 82.00 kr, kurv 99.00 kr"]
    assert [text.split(":")[0] for text in unchecked] == ["Cola", "Udgået"]


@live
@pytest.mark.live
@pytest.mark.parametrize("name", ["bilkatogo", "nemlig"])
async def test_search_price_is_the_cart_price(name, monkeypatch):
    store = STORES[name]()

    async def no_writes(*_args, **_kwargs):
        raise AssertionError("this test must never write to the cart")

    monkeypatch.setattr(store, "set_quantities", no_writes)
    lines = (await store.get_cart()).lines[:MOST]
    if not lines:
        pytest.skip("kurven er tom: intet at sammenligne")
    found = {}
    for line in lines:
        for product in await store.search(line.name, limit=20):
            found.setdefault(product.id, product)
    wrong, unchecked, checked = compare(lines, found)
    print(f"\n[{name}] {checked} linjer sammenlignet, {len(unchecked)} sprunget over")
    for text in unchecked + wrong:
        print(f"  {text}")
    if not checked:
        pytest.skip("ingen linje kunne sammenlignes")
    assert not wrong, wrong
