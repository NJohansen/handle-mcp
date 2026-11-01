"""compare_basket: price one shopping list in each store.

Simple and explainable matching. No store-specific code here.
- "2 x rugbrød" means quantity 2. A size like "1 l" or "500 g" in the item must match.
- A product matches well when every word of the item is a whole word in its name.
- Then the right size wins, then the lowest price. Sold-out products never win.
- Unsure matches and missing items are marked, so a human can check them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from handle_mcp.models import Product
from handle_mcp.stores import StoreError

SEARCH_LIMIT = 10
SIZE_TOLERANCE = Decimal("0.15")  # 15 % off the wanted size still counts as the same size
STOP_WORDS = {"og", "med", "i", "af", "en", "et", "til", "uden"}
UNITS = {
    "g": ("g", 1), "gr": ("g", 1), "kg": ("g", 1000),
    "ml": ("ml", 1), "cl": ("ml", 10), "dl": ("ml", 100),
    "l": ("ml", 1000), "ltr": ("ml", 1000), "liter": ("ml", 1000),
    "stk": ("stk", 1), "st": ("stk", 1),
}  # fmt: skip
SIZE_RE = re.compile(
    r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(" + "|".join(UNITS) + r")\b", re.IGNORECASE
)
QTY_RE = re.compile(r"^\s*(\d+)\s*[x×]\s+(?=\D)", re.IGNORECASE)


@dataclass
class BasketLine:
    item: str  # the line from the shopping list
    quantity: int
    product: Product | None
    line_total: Decimal
    sure: bool
    note: str | None = None


@dataclass
class BasketQuote:
    store: str
    lines: list[BasketLine]
    missing: list[str]
    products_total: Decimal
    fees: dict[str, Decimal]
    total: Decimal
    minimum_order: Decimal | None
    minimum_met: bool | None
    notes: list[str] = field(default_factory=list)


def _get(product: Any, key: str) -> Any:
    """Adapters return Product; tolerate a dict too."""
    return product.get(key) if isinstance(product, dict) else getattr(product, key)


def parse_size(text: str | None) -> tuple[str, Decimal] | None:
    """'1 l' → ('ml', 1000). '12 x 0,25 l' → ('ml', 3000). None if no size."""
    match = SIZE_RE.search(text or "")
    if not match:
        return None
    count, amount, unit = match.groups()
    base, factor = UNITS[unit.lower()]
    return base, Decimal(amount.replace(",", ".")) * factor * int(count or 1)


def parse_item(item: str) -> tuple[int, list[str], tuple[str, Decimal] | None]:
    """'2 x letmælk 1 l' → (2, ['letmælk'], ('ml', 1000))."""
    quantity = 1
    if match := QTY_RE.match(item):
        quantity, item = int(match.group(1)), item[match.end() :]
    size = parse_size(item)
    words = [w for w in _words(SIZE_RE.sub(" ", item)) if w not in STOP_WORDS]
    return max(quantity, 1), words, size


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zæøå0-9]+", text.lower())


def _score(words: list[str], product: Any) -> float:
    """1.0 when every word is a whole word in the name; a word inside another word counts half."""
    text = f"{_get(product, 'name')} {_get(product, 'brand') or ''}".lower()
    tokens = set(_words(text))
    hits = [1.0 if w in tokens else 0.5 if w in text else 0.0 for w in words]
    return sum(hits) / len(hits) if hits else 0.0


def _size_ok(wanted: tuple[str, Decimal] | None, product: Any) -> bool | None:
    """True/False when both sizes are known, None when we cannot tell."""
    have = parse_size(_get(product, "size")) or parse_size(_get(product, "name"))
    if not wanted or not have or wanted[0] != have[0]:
        return None if not wanted or not have else False
    return abs(have[1] - wanted[1]) <= wanted[1] * SIZE_TOLERANCE


def best_match(item: str, products: list[Any]) -> BasketLine:
    """Best word match first, then the right size, then the lowest price."""
    quantity, words, size = parse_item(item)
    ranked = []
    for product in products:
        score = _score(words, product)
        if _get(product, "available") and score >= 0.5:
            size_ok = _size_ok(size, product)
            size_rank = 0 if size_ok or not size else 1 if size_ok is None else 2
            ranked.append((-score, size_rank, Decimal(_get(product, "price")), product))
    if not ranked:
        return BasketLine(item, quantity, None, Decimal(0), False, "Ikke fundet")
    neg_score, size_rank, price, product = min(ranked, key=lambda r: r[:3])
    sure = neg_score == -1.0 and size_rank == 0
    note = None
    if size_rank == 2:
        note = f"Anden størrelse: {_get(product, 'size') or _get(product, 'name')}."
    elif not sure:
        note = "Usikkert match. Tjek varen."
    return BasketLine(item, quantity, product, price * quantity, sure, note)


async def quote(store: Any, items: list[str]) -> BasketQuote:
    """Search each item in one store (one call at a time) and add fees and minimum order."""
    lines = [best_match(item, await store.search(item, SEARCH_LIMIT)) for item in items]
    terms = await store.terms()
    found = [ln for ln in lines if ln.product is not None]
    products_total = sum((ln.line_total for ln in found), Decimal(0))
    fees = {k: v for k, v in {"levering": terms.delivery_fee, **terms.other_fees}.items() if v}
    try:  # read-only; e.g. a fee that depends on the slot. Prices still count without it.
        note = _get(await store.delivery_info(), "note")
    except (NotImplementedError, StoreError):
        note = None
    notes = [note] if note else []
    if not terms.home_delivery and not note:
        notes.append("Kurven er ikke sat til hjemlevering.")
    minimum = terms.minimum_order
    return BasketQuote(
        store=terms.store,
        lines=found,
        missing=[ln.item for ln in lines if ln.product is None],
        products_total=products_total,
        fees=fees,
        total=products_total + sum(fees.values(), Decimal(0)),
        minimum_order=minimum,
        minimum_met=None if minimum is None else products_total >= minimum,
        notes=notes,
    )


def verdict(quotes: dict[str, Any]) -> dict[str, Any]:
    """Compare stores on the items every store has, plus each store's fees."""
    ok = {n: q for n, q in quotes.items() if isinstance(q, BasketQuote)}
    if not ok:
        return {"cheapest": None, "summary": "Ingen butik kunne prise listen."}
    common = set.intersection(*({ln.item for ln in q.lines} for q in ok.values()))
    if not common:
        return {"cheapest": None, "summary": "Ingen vare blev fundet i alle butikker. Tjek listen."}
    totals = {
        n: sum((ln.line_total for ln in q.lines if ln.item in common), Decimal(0))
        + sum(q.fees.values(), Decimal(0))
        for n, q in ok.items()
    }
    cheapest = min(totals, key=lambda n: totals[n])
    summary = f"Billigst: {cheapest} ({totals[cheapest]} kr. inkl. gebyrer"
    summary += f" for de {len(common)} varer, alle butikker har)."
    if any(q.missing for q in ok.values()) or any(
        not ln.sure for q in ok.values() for ln in q.lines
    ):
        summary += " Nogle varer mangler eller er usikre. Tjek dem."
    return {"cheapest": cheapest, "comparable_totals": totals, "summary": summary}
