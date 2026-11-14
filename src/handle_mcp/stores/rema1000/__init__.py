"""REMA 1000: the API behind shop.rema1000.dk. See docs/research.md and docs/adr/0007.

Search, the weekly leaflet (Avisvare) and the store list are public: no login. Pickup times
need one (auth.py, pickup.py). The webshop is pickup only (Køb & Hent).
REMA's own cart, store choice, pickup time and payment are never touched here (docs/adr/0001,
docs/adr/0007). The cart is the shopping list "handle-mcp" (shopping_list.py).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from handle_mcp.models import Order, Product, Recipe, RecipeDetails
from handle_mcp.stores import StoreError
from handle_mcp.stores._http import request
from handle_mcp.stores.rema1000.auth import API, HEADERS, NAME, SHOP, RemaAuthMixin
from handle_mcp.stores.rema1000.nutrition import RemaNutritionMixin
from handle_mcp.stores.rema1000.pickup import NOTE, RemaPickupMixin
from handle_mcp.stores.rema1000.shopping_list import RemaListMixin

log = logging.getLogger(__name__)

LEAFLET = 9001  # the label "Avisvare": this week's leaflet
FIXED = "Avisvare, fast pris"
# A shared category (stores.OFFER_CATEGORIES) is one or more departments: `filter[departments]`
# takes a department id. No call lists them (live 2026-11-14: tests/fixtures/rema1000/README.md).
DEPARTMENTS = {
    "frugt og grønt": (20,),
    "kød og fisk": (30,),
    "mejeri og æg": (60, 70),  # Mejeri, Ost m.v.
    "pålæg": (40,),  # Køl
    "brød og kager": (10,),
    "kolonial": (80, 160),  # Kolonial, Nemt & hurtigt
    "frost": (50,),
    "drikkevarer": (90,),
    "slik og snacks": (130,),
    "husholdning": (100,),
    "pleje": (120,),
    "baby": (110,),
}

PER_PAGE = 100  # the most one page gives
UNITS = {"kg": "kg", "ltr": "l", "l": "l", "stk": "stk"}
__all__ = ["NOTE", "Rema1000Store", "product"]


def _money(value: Any) -> Decimal | None:
    """REMA gives kroner as JSON numbers (7.95). Through str, never float maths."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _current(prices: list[dict], now: datetime) -> int | None:
    """Index of the price that holds now. REMA lists the current period first. When none holds,
    the last normal (no offer) price, never an ended offer; None when there is none."""
    for i, period in enumerate(prices):
        start, end = _time(period.get("starting_at")), _time(period.get("ending_at"))
        if (start is None or start <= now) and (end is None or now.date() <= end.date()):
            return i
    normal = [i for i, p in enumerate(prices) if not p.get("is_campaign")]
    return normal[-1] if normal else None


def _kr(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",").removesuffix(",00")


def _offer_text(period: dict, leaflet: bool) -> str:
    text = "Avisvare" if leaflet else "Tilbud"
    if not period.get("is_campaign"):  # in the leaflet at a fixed price, for months
        return FIXED
    most, over = period.get("max_quantity"), _money(period.get("price_over_max_quantity"))
    if isinstance(most, int) and most > 0 and over is not None:
        text += f", maks {most} stk. (derefter {_kr(over)} kr)"
    return text


def product(hit: dict, now: datetime | None = None, advertised: bool = False) -> Product | None:
    """One product from search/products. None when it has no price. `advertised` (the offer
    list): a leaflet product at a fixed price is an offer too."""
    prices = [p for p in hit.get("prices") or [] if isinstance(p, dict)]
    at = _current(prices, now or datetime.now(UTC))
    price = _money(prices[at].get("price")) if at is not None else None
    if price is None or hit.get("id") is None:
        return None
    period = prices[at]
    size, _, brand = str(hit.get("underline") or "").partition(" / ")
    labels = {lbl.get("id") for lbl in hit.get("labels") or [] if isinstance(lbl, dict)}
    # A leaflet product can be advertised at a fixed price and be no campaign (live 2026-11-14:
    # 191 of the leaflet's 416). The leaflet shows it, so the offer list does; no price before.
    # In a search it stays a normal price: nothing is cheaper than before.
    on_offer = bool(period.get("is_campaign")) or (
        advertised and LEAFLET in labels and bool(period.get("is_advertised"))
    )
    before = None
    if on_offer:  # the next period that is no offer: what it costs after the offer
        later = [p for p in prices[at + 1 :] if not p.get("is_campaign")]
        before = _money(later[0].get("price")) if later else None
        before = before if before is not None and before > price else None
    end = _time(period.get("ending_at"))
    dept = (hit.get("department") or {}).get("name")
    cat = (hit.get("category") or {}).get("name")
    unit = str(period.get("compare_unit") or "").lower().rstrip(".")
    barcodes = [b for b in hit.get("barcodes") or [] if isinstance(b, str)]
    most = period.get("max_quantity")
    return Product(
        store="rema1000",
        id=str(hit["id"]),
        name=str(hit.get("name") or ""),
        price=price,
        brand=brand.strip() or None,
        size=size.strip() or None,
        unit_price=_money(period.get("compare_unit_price")),
        unit=UNITS.get(unit, unit or None),
        ean=barcodes[0] if barcodes else None,
        on_offer=on_offer,
        offer_text=_offer_text(period, LEAFLET in labels) if on_offer else None,
        before_price=before,
        offer_until=end.date() if on_offer and end else None,
        category=" > ".join(x for x in (dept, cat) if x) or None,
        campaign="Avisvare" if on_offer and LEAFLET in labels else None,
        max_per_order=most if on_offer and isinstance(most, int) and most > 0 else None,
    )


class Rema1000Store(RemaAuthMixin, RemaPickupMixin, RemaListMixin, RemaNutritionMixin):
    name = "rema1000"
    cart_page = SHOP  # the list lives in REMA's app and webshop; no page per list is known

    def __init__(
        self, client: httpx.AsyncClient | None = None, auth: httpx.AsyncClient | None = None
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=20, follow_redirects=True)
        # The login has its own client, so its cookies never ride along with a search.
        self._auth = auth or httpx.AsyncClient(timeout=20)
        self._cookies: dict[str, str] = {}  # the site's session (auth.py)
        self._token: str | None = None
        self._until = datetime.min.replace(tzinfo=UTC)
        self._user: int | None = None  # the user id in the token, for the list
        self._stores = ""  # the chosen store ids, comma-separated (pickup.py)
        self._gate = None
        self._auth_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()  # one list write at a time (shopping_list.py)

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        resp = await request(
            self._client, "GET", f"{API}/{path}", NAME, params=params, headers=HEADERS
        )
        if resp.status_code != 200:
            raise StoreError(f"REMA 1000 svarer {resp.status_code}. Prøv igen senere.")
        try:
            data = resp.json()
        except ValueError as exc:  # a queue or bot page instead of JSON: never work around it
            raise StoreError("REMA 1000 svarer ikke med data lige nu. Prøv igen senere.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise StoreError("REMA 1000 har ændret sit svar. handle-mcp skal opdateres.")
        return data

    async def _products(
        self, params: dict[str, Any], limit: int, offers_only: bool = False
    ) -> list[Product]:
        """Page until `limit` products. `offers_only` skips a leaflet product whose offer has
        ended, before counting, so the limit is still filled."""
        found: list[Product] = []
        page = 1
        while len(found) < limit:
            data = await self._get("search/products", params | {"per_page": PER_PAGE, "page": page})
            hits = [
                product(hit, advertised=offers_only)
                for hit in data["data"]
                if isinstance(hit, dict)
            ]
            found += [p for p in hits if p and (p.on_offer or not offers_only)]
            last = ((data.get("meta") or {}).get("pagination") or {}).get("last_page") or 1
            if page >= last or not data["data"]:
                break
            page += 1
        if offers_only:  # campaigns first: a fixed price must not push a price cut out
            found.sort(key=lambda p: p.offer_text == FIXED)
        return found[:limit]

    async def search(self, query: str, limit: int = 10) -> list[Product]:
        return await self._products({"query": query}, limit)

    async def offers(self, limit: int = 25, category: str | None = None) -> list[Product]:
        """The leaflet (Avisvarer). With `category`: the leaflet in its departments, one call
        per department at once."""
        params = {"filter[labels]": LEAFLET, "sort": "department"}
        if not category:
            return await self._products(params, limit, offers_only=True)
        found = await asyncio.gather(
            *(
                self._products(params | {"filter[departments]": dept}, limit, offers_only=True)
                for dept in DEPARTMENTS[category]
            )
        )
        unique = {p.id: p for products in found for p in products}
        return list(unique.values())[:limit]

    async def recipes(self, query: str, limit: int = 5) -> list[Recipe]:
        raise NotImplementedError

    async def recipe(self, recipe_id: str, persons: int | None = None) -> RecipeDetails:
        raise NotImplementedError

    async def featured_recipes(self, limit: int = 20) -> list[Recipe]:
        raise NotImplementedError

    async def recipes_by_tag(
        self, tags: list[str], category: str | None = None, limit: int = 20
    ) -> list[Recipe]:
        raise NotImplementedError

    async def orders(self, limit: int = 10) -> list[Order]:
        raise NotImplementedError

    async def order(self, order_id: str) -> Order:
        raise NotImplementedError
