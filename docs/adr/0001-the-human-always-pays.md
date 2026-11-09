# 0001: The human always pays

handle-mcp reads stores and changes cart quantities. It never places an order, pays, reads payment cards, chooses a delivery time or changes the address. Those endpoints do not exist in the code, and `tests/test_safety.py` fails if one appears.

## Why

A cart change is reversible and costs nothing. An order spends money and commits the store to pack it. A bug, a misread API answer or a confused model must never be able to do that.

## Consequences

- The human approves and pays on the store's own website or app.
- Anything beyond the cart needs a new ADR that replaces or extends this one.
- REMA 1000 has no cart we may touch. There, "the cart" is one shopping list in REMA's app, named `handle-mcp` ([ADR 0007](0007-rema-cart-is-a-shopping-list.md)). The same limits hold: handle-mcp sets item quantities on that list and nothing else. A Køb & Hent order starts from the list, but only the human turns it into an order, picks a time and pays.
