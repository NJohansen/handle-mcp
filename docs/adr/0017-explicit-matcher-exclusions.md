# 0017: Explicit matcher exclusions are constraints

Shopping-list items can include an explicit absence requirement, for example
"peanutbutter uden sukker", "øl uden alkohol" or "brød glutenfri".

## Decision

- `uden` and `u.` start an exclusion constraint.
- A `fri` suffix, such as `sukkerfri`, means the named term must be absent.
- `fri for tilsat sukker` means the excluded term is `sukker`; `tilsat` is descriptive filler.
- Exclusion terms are removed from the store search query.
- A product that mentions the excluded term positively is rejected.
- Conflicting positive text wins over a free-from claim if both are present.
- A product-name claim, even `sukkerfri`, does not verify a dietary constraint or make the match sure.

## Why

A normal word match proves only that words in the item occur in the product name.
It cannot prove that a stated dietary or ingredient constraint is met.
Marking a product as sure when it says "med sukker" is a concrete shopping error.

## Consequences

- Negative requirements must be checked before a match is ranked or marked sure.
- Any constrained match remains visibly uncertain; product names are not ingredient-label verification.
- Additional constraint vocabulary can be added when it has a real store or recipe case.
