"""Explicit exclusions in a shopping-list item and claims in a product name."""

import re
from typing import Any

ABSENCE = re.compile(
    r"\b(?:uden|u\.|fri\s+for|frit\s+for)\s+(?:(?:tilsat|tilsatte)\s+)?([a-zæøå]+)\b",
    re.IGNORECASE,
)
FREE = re.compile(r"\b([a-zæøå]{3,})fri(?:t|e)?\b", re.IGNORECASE)


def excluded_terms(item: str) -> set[str]:
    return {m.group(1).lower() for pattern in (ABSENCE, FREE) for m in pattern.finditer(item)}


def without_constraints(item: str) -> str:
    return FREE.sub(" ", ABSENCE.sub(" ", item))


def constraint_status(item: str, product: Any) -> str:
    """A name can claim an exclusion; it cannot verify an ingredient label."""
    terms = excluded_terms(item)
    if not terms:
        return "free"
    name = product.get("name") if isinstance(product, dict) else product.name
    text = (name or "").lower()
    claims = 0
    for term in terms:
        word = re.escape(term)
        claim = (
            rf"\b(?:{word}fri(?:t|e)?|u{word}(?:et|ede|e)?|"
            rf"(?:uden|u\.|fri\s+for|frit\s+for)\s+(?:(?:tilsat|tilsatte)\s+)?{word})\b"
        )
        remaining, count = re.subn(claim, " ", text)
        if term in remaining:
            return "conflict"
        claims += bool(count)
    return "free" if claims == len(terms) else "unknown"
