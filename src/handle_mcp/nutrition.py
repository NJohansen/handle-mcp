"""Read a nutrition label ("Næringsindhold") the way Danish stores write it.

Rows are (label, value) pairs: ("Energi", "329 kJ / 78 Kcal"), ("- heraf mættede fedtsyrer",
"0,1 g"), ("Salt", "<0,01 g"). Decimals use a comma, thousands a dot ("1.017 kJ"). Values
come back as plain decimal strings with a dot, as exact as the label: docs/adr/0010.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from handle_mcp.models import Nutrition

# Label words → field, checked in order: "mættede fedtsyrer" before "fedt",
# "sukkerarter" before "kulhydrat" (Bilka writes "- heraf sukkerarter" on its own row).
FIELDS = (
    ("mætte", "saturated_fat"),
    ("sukker", "sugar"),
    ("fedt", "fat"),
    ("kulhydrat", "carbohydrate"),
    ("protein", "protein"),
    ("salt", "salt"),
    ("fibre", "fibre"),
)
NUMBER = re.compile(r"(<|under\s+)?\s*(\d[\d.]*(?:,\d+)?)\s*(kj|kcal|g)?", re.IGNORECASE)


def number(text: str) -> str | None:
    """'0,13' → '0.13', '1.017' → '1017', '2.1' → '2.1', '<0,5' → '<0.5'. None if no number."""
    m = NUMBER.search(text or "")
    if not m:
        return None
    raw = m.group(2)
    if "," in raw:  # comma decimals: every dot is a thousands dot
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", raw):  # "1.017": thousands
        raw = raw.replace(".", "")
    try:
        value = Decimal(raw.rstrip("."))
    except InvalidOperation:
        return None
    text_value = format(value, "f")
    return f"<{text_value}" if m.group(1) else text_value


def energy(text: str) -> dict[str, str]:
    """'329 kJ / 78 Kcal' → both; '233 kJ' or '55 kcal' → one. A number without a unit: none."""
    found = {}
    for m in NUMBER.finditer(text or ""):
        unit = (m.group(3) or "").lower()
        if unit in ("kj", "kcal") and (value := number(m.group(0))):
            found.setdefault(f"energy_{unit}", value)
    return found


def basis(text: str | None) -> str | None:
    """'Næringsindhold pr. 100 ml' or '100 g' → '100 ml' / '100 g'. None if it does not say."""
    m = re.search(r"100\s*(ml|g)\b", text or "", re.IGNORECASE)
    return f"100 {m.group(1).lower()}" if m else None


def label(rows: list[tuple[str, str]], per: str | None) -> Nutrition | None:
    """The rows of one label. None when no row is a nutrient we know (an empty table)."""
    values: dict[str, str] = {}
    for title, value in rows:
        name = (title or "").lower()
        if "energi" in name:
            for key, v in energy(value).items():
                values.setdefault(key, v)
            continue
        if "umætte" in name:  # enkelt-/flerumættede: not the saturated fat
            continue
        key = next((f for word, f in FIELDS if word in name), None)
        if key and (v := number(value)) is not None:
            values.setdefault(key, v)
    return Nutrition(per=per, **values) if values else None
