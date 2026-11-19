# 0017: Explicit matcher exclusions are constraints

Shopping-list items can include an explicit absence requirement, for example
"peanutbutter uden sukker", "øl uden alkohol" or "brød glutenfri".

## Decision

- `uden` and `u.` apply to the next word, not the rest of the item.
- A `fri` suffix, such as `sukkerfri`, means the named term must be absent; `Afri` is not a claim.
- `fri for tilsat sukker` means the excluded term is `sukker`; `tilsat` is descriptive filler.
- The requirement stays in the store search query, but is not a normal product-name match word.
- Only the product name is checked: a positive mention is rejected, and an explicit claim ranks
  before a product with no claim. The brand and category do not prove the product's contents.
- Conflicting positive text wins over a free-from claim if both are present.
- A product-name claim, even `sukkerfri`, does not verify a dietary constraint or make the match sure.
- `uden tilsat sukker` is a name claim, not proof that the product contains no sugar.

## Why

A normal word match proves only that words in the item occur in the product name.
It cannot prove that a stated dietary or ingredient constraint is met.
Marking a product as sure when it says "med sukker" is a concrete shopping error.

## Consequences

- Negative requirements must be checked before a match is ranked or marked sure.
- Any constrained match remains visibly uncertain; product names are not ingredient-label verification.
- If a list says `uden sukker og laktose`, only `sukker` is treated as an exclusion. Write
  `uden sukker og uden laktose` to state two separate exclusions.
- Additional constraint vocabulary can be added when it has a real store or recipe case.
