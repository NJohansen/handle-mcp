"""nemlig.com offers: the lists on /tilbud, read from nemlig's new web API (productbff).

The page URL /tilbud?GetAsJson=1 can send us to the queue-it waiting room; the API does not
(seen live 2026-11-03). One call gives every list with its products, and needs no user id.
/tilbud also has a block per category; its sub-page (/tilbud/frugt-og-groent) is the whole
list, and can have campaign blocks of its own ("Lurpak kun 12 kr."). Live 2026-11-14.
Shapes: tests/fixtures/nemlig/README.md.
"""

from __future__ import annotations

import asyncio
import logging
import re
from decimal import Decimal
from typing import Any

from handle_mcp.models import Product
from handle_mcp.stores import OFFER_CATEGORIES, StoreError
from handle_mcp.stores.nemlig.recipes import BFF

log = logging.getLogger(__name__)

# Offer lists on /tilbud, matched on the heading. The other lists on the page are categories.
OFFER_LISTS = {
    "skarp pris": "Skarp pris",
    "ugens priskup": "Priskup",
    "priskup": "Priskup",
    "dagstilbud": "Dagstilbud",
    "undgå madspild": "Undgå madspild",
    "en gave til dig": "Gratis",
}
# A shared category (stores.OFFER_CATEGORIES) is one or more sub-pages of /tilbud.
CATEGORY_PAGES = {
    "frugt og grønt": ("frugt-og-groent",),
    "kød og fisk": ("koed",),  # fish has no sub-page (live 2026-11-14)
    "mejeri og æg": ("mejeri-og-aeg",),
    "pålæg": ("paalaeg",),
    "brød og kager": ("broed-kiks-og-kager",),
    "kolonial": ("ris-pasta-og-konserves", "bagning", "morgenmad-og-musli"),
    "frost": ("frost",),
    "drikkevarer": ("drikkevarer", "vin"),
    "slik og snacks": ("chips-slik-og-snacks",),
    "husholdning": ("husholdning-og-bolig",),
    "pleje": ("pleje",),
    "baby": ("baby-boern-og-legetoej",),
}
assert set(CATEGORY_PAGES) == set(OFFER_CATEGORIES)
# Pages outside /tilbud that show a gift (live 2026-11-14). A gift has its own product id.
# nemlig removes such a page without notice: a page that fails is left out.
GIFT_PAGES = ("/fordele/det-nye-nemlig",)
GIFT = "en gave til dig"
UNITS = {"Weight": "kg", "Volume": "l", "Pieces": "stk"}
MULTI = re.compile(r"^(Mix )?\d+ stk\.")


def _kr(ore: Any) -> Decimal | None:
    return None if ore is None else Decimal(int(ore)) / 100


def _text(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",").removesuffix(",00")


def _lines(p: dict) -> list[str]:
    return [str(ln.get("text") or "") for ln in p.get("campaignLines") or []]


def _is_gift(p: dict) -> bool:
    return GIFT in map(str.lower, _lines(p)) or (
        p.get("price") == 0 and bool(p.get("priceOriginal"))
    )


def _blocks(page: dict) -> list[tuple[str, str, list[dict]]]:
    """(heading, layout, products) of every product list on a page."""
    return [
        (
            str((block.get("header") or {}).get("title") or "").strip(),
            str(block.get("layout") or ""),
            block.get("products") or [],
        )
        for block in page.get("pageContent") or []
        if block.get("contentType") == "ProductList" or block.get("products")
    ]


def category_offer(p: dict, block: str | None) -> Product | None:
    """One product from a category page, or None when it is no offer: a category list also
    has products at their normal price ("God pris"). `block` is the heading of a campaign
    block, which is then the campaign's name."""
    lines = _lines(p)
    own = next((OFFER_LISTS[t.lower()] for t in lines if t.lower() in OFFER_LISTS), None)
    before = p.get("priceOriginal")
    cheaper = before is not None and int(p["price"]) < int(before)
    if not (own or cheaper or any(MULTI.match(t) for t in lines)):
        return None
    return offer_product(p, block or own or "Tilbud")


def offer_product(p: dict, campaign: str) -> Product | None:
    """One product from a list, or None if it is not cheaper than its normal price."""
    price = Decimal(int(p["price"])) / 100  # no price: format change, never "Gratis"
    before = _kr(p.get("priceOriginal"))
    if before is not None and price >= before:
        return None
    limit = p.get("labelMaxQuantity") or None
    multi = next(  # "Mix 2 stk. 35,-" or "2 stk. 15,-"
        (ln["text"] for ln in p.get("campaignLines") or [] if MULTI.match(ln.get("text") or "")),
        None,
    )
    if campaign == "Gratis" or _is_gift(p):
        campaign, text = "Gratis", "Gratis"
    else:
        text = multi or (f"Tilbud, før {_text(before)} kr" if before else campaign)
    if limit:
        text += f" (max {limit} stk.)"
    per_unit = p.get("pricePerUnit") or {}
    return Product(
        store="nemlig",
        id=str(p["id"]),
        name=p.get("title", ""),
        price=price,
        size=p.get("description") or None,
        unit_price=_kr(per_unit.get("value")),
        unit=UNITS.get(per_unit.get("unitType")),
        on_offer=True,
        offer_text=text,
        before_price=before,
        available=(p.get("availability") or {}).get("type", "Available") == "Available",
        campaign=campaign,
        max_per_order=limit,
    )


class OffersMixin:
    """offers() for NemligStore. Uses its `_public` (login optional) and `search`."""

    _public: Any
    _has_login: Any
    _timeslot_id: Any
    search: Any

    async def _page(self, path: str) -> dict:
        params = {"path": path}
        if slot := await self._timeslot_id():
            params["timeslotId"] = slot  # sic: the page call spells it so, the dialog not
        return await self._public("GET", f"{BFF}/page", params=params) or {}

    async def offers(self, limit: int = 25, category: str | None = None) -> list[Product]:
        """Without `category`: every product on nemlig's offer lists (/tilbud): Skarp pris,
        Priskup, Dagstilbud, Undgå madspild and gifts; `limit` is per list. With one: every
        offer on the category's sub-pages, at most `limit`. Read only. Works without a login:
        the offers are public; with one, they fit the household's delivery time."""
        if category:
            return await self._category_offers(category, limit)
        page, gifts, extra = await asyncio.gather(
            self._page("/tilbud"), self._gift_search(), self._gift_pages()
        )
        blocks = _blocks(page)
        lists = [
            (OFFER_LISTS[h.lower()], items) for h, _, items in blocks if h.lower() in OFFER_LISTS
        ]
        if not lists:
            raise StoreError("Fandt ingen tilbudslister hos nemlig. Siden kan have ændret sig.")
        products: dict[str, Product] = {}
        broken = 0
        for name, items in lists:
            try:  # one broken list must not hide the others
                found = [o for p in items if (o := offer_product(p, name))][:limit]
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("nemlig-tilbudslisten %s har ændret format: %r", name, exc)
                broken += 1
                continue
            for product in found:
                products.setdefault(product.id, product)
        if broken == len(lists):
            raise StoreError("nemligs tilbudslister har ændret format.")
        # A gift can also sit in a category block (live 2026-11-14), on a page of its own, or
        # only in a search for "gratis" (ProductCampaignFreeProduct). None is cut by `limit`.
        for gift in [*self._gifts(blocks), *extra, *gifts]:
            products.setdefault(gift.id, gift)
        return list(products.values())

    async def _category_offers(self, category: str, limit: int) -> list[Product]:
        pages = await asyncio.gather(
            *(self._page(f"/tilbud/{slug}") for slug in CATEGORY_PAGES[category]),
            return_exceptions=True,
        )
        if failed := [p for p in pages if isinstance(p, BaseException)]:
            if len(failed) == len(pages):
                raise failed[0]
            log.warning("nemlig: %d tilbudssider fejlede: %r", len(failed), failed[0])
        products: dict[str, Product] = {}
        blocks = [b for p in pages if isinstance(p, dict) for b in _blocks(p)]
        # Campaign blocks first: their heading names the campaign the product is in.
        for head, layout, items in sorted(blocks, key=lambda b: b[1] != "Onerow"):
            try:
                name = head if layout == "Onerow" and head else None
                found = [o for p in items if (o := category_offer(p, name))]
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("nemlig-tilbudslisten %s har ændret format: %r", head, exc)
                continue
            for product in found:
                products.setdefault(product.id, product)
        if blocks and not products:
            raise StoreError("nemligs tilbudslister har ændret format.")
        return list(products.values())[:limit]

    def _gifts(self, blocks: list[tuple[str, str, list[dict]]]) -> list[Product]:
        found = []
        for _, _, items in blocks:
            try:
                found += [o for p in items if _is_gift(p) and (o := offer_product(p, "Gratis"))]
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("nemlig-gave har ændret format: %r", exc)
        return found

    async def _gift_pages(self) -> list[Product]:
        pages = await asyncio.gather(*map(self._page, GIFT_PAGES), return_exceptions=True)
        for path, page in zip(GIFT_PAGES, pages, strict=True):
            if isinstance(page, BaseException):
                log.warning("nemlig-gavesiden %s fejlede: %r", path, page)
        return self._gifts([b for p in pages if isinstance(p, dict) for b in _blocks(p)])

    async def _gift_search(self) -> list[Product]:
        """A free-text search, so it may change. Search needs a login."""
        if not self._has_login():
            return []
        try:
            return [p for p in await self.search("gratis", 50) if p.campaign == "Gratis"]
        except StoreError as exc:
            log.warning("nemlig-gaver fejlede: %s", exc)
            return []
