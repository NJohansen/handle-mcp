# 0011: A folder per store is grouping, not a layer

Each store had one file plus mixins next to it: `stores/nemlig.py`, `stores/nemlig_offers.py`, `stores/nemlig_recipes.py` and so on. With three stores that was 17 files in one flat folder, and every new topic adds one file per store.

## Decision

- Each store is a package: `stores/<store>/__init__.py` holds the store's class (login, calls, parsing), and `stores/<store>/<topic>.py` holds its mixins (`offers.py`, `recipes.py`, `nutrition.py`, ...).
- `stores/__init__.py` (the Store protocol, StoreError, logins, `STORES`) and `stores/_http.py` (requests, retries, `per_product()`) stay in the root: every store uses them.
- This is grouping, not a layer. The code, the classes, the mixins and the Store protocol are the same. No base class, no registry, no plugin system.
- A submodule never takes a builtin's name (`list.py`, `type.py`): inside the package it would shadow the builtin. REMA 1000's list is `shopping_list.py`.
- The size rule follows the folder: < ~550 lines per file in a store folder, < ~300 in every other file.

## Consequences

- A store's code is in one place, and a new store is one new folder. `ls stores/` shows the stores, not their topics.
- `from handle_mcp.stores.nemlig import NemligStore` works as before. Only imports of the mixin modules changed (`stores.nemlig_offers` is `stores.nemlig.offers`).
- `tests/test_safety.py` scans `src/` recursively, so the forbidden-endpoint check covers every store folder.
