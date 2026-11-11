"""REMA 1000 nutrition: the "Næringsindhold" table on shop.rema1000.dk's product page.

GET api/v3/products/{id}?include=nutrition_info, as the page itself asks (seen 2026-11-11, no
login): `nutrition_info` is [{name, value}] ("Energi" = "318 KJ / 75 kcal", "Fedt" = "< 0,5").
Search leaves it out. The table says "Pr. 100 g/ml": the product's compare unit (kg or ltr)
tells which. Shapes: tests/fixtures/rema1000/README.md.
"""

from __future__ import annotations

import re
from typing import Any

from handle_mcp import nutrition
from handle_mcp.models import ProductNutrition
from handle_mcp.stores import NotFound, StoreError
from handle_mcp.stores._http import request
from handle_mcp.stores.rema1000_auth import API, HEADERS, NAME

BASIS = {"kg": "100 g", "ltr": "100 ml", "l": "100 ml"}
NO_LABEL = "REMA 1000 viser ingen næringsdeklaration for varen (ofte frisk kød, frugt og grønt)."
UNKNOWN = "REMA 1000 kender ikke varen."


def product_nutrition(data: dict) -> ProductNutrition:
    p = data["data"]
    rows = [
        (str(r.get("name") or ""), str(r.get("value") or "")) for r in p.get("nutrition_info") or []
    ]
    unit = str(((p.get("prices") or [{}])[0] or {}).get("compare_unit") or "").lower()
    label = nutrition.label(rows, BASIS.get(unit))
    return ProductNutrition(
        store="rema1000",
        id=str(p["id"]),
        name=p.get("name") or None,
        nutrition=label,
        reason=None if label else NO_LABEL,
    )


class RemaNutritionMixin:
    """nutrition() for Rema1000Store. Uses its `_client`. Public: no login."""

    _client: Any

    async def nutrition(self, product_ids: list[str]) -> list[ProductNutrition]:
        if bad := [i for i in product_ids if not re.fullmatch(r"\d{1,12}", i)]:
            raise StoreError(
                f"Ukendt vare-id hos REMA 1000: {', '.join(bad)}. Brug id'et fra søgningen."
            )

        async def one(pid: str) -> ProductNutrition:
            resp = await request(
                self._client,
                "GET",
                f"{API}/v3/products/{pid}",
                NAME,
                params={"include": "nutrition_info"},
                headers=HEADERS,
            )
            if resp.status_code == 404:
                raise NotFound(UNKNOWN)
            if resp.status_code != 200:
                raise StoreError(f"REMA 1000 svarer {resp.status_code}. Prøv igen senere.")
            try:
                return product_nutrition(resp.json())
            except ValueError as exc:  # a queue or bot page instead of JSON: never work around it
                raise StoreError(
                    "REMA 1000 svarer ikke med data lige nu. Prøv igen senere."
                ) from exc
            except (KeyError, IndexError, TypeError, AttributeError) as exc:
                raise StoreError(
                    "REMA 1000 har ændret sit svar. handle-mcp skal opdateres."
                ) from exc

        return await nutrition.each("rema1000", product_ids, one, UNKNOWN)
