# 0019: Match tortilla wraps without chips

For `tortilla wraps`, the matcher treats tortilla and wraps as related terms rather than requiring both in a product name. A tortilla is a full name match; a product named only as a wrap is a partial match to review. `tortilla`/`tortillas` and `wrap`/`wraps` are singular and plural. A product named as chips is excluded when tortilla or wraps were requested without chips.

## Why

REMA 1000 returns both `TORTILLAS HVEDE` and `TORTILLA CHIPS` for `tortilla wraps`. Without these rules the chips can rank higher while the tortillas do not reach the candidate list.

## Consequences

- The rules also apply to other stores. Asking for tortilla chips still finds chips.
- A pack sold by weight cannot be assumed to contain the requested number of pieces. It remains uncertain.
- A partial wrap match may be a prepared wrap rather than a pack of tortillas; the caller must check it.
- A tortilla with an unrequested filling is also marked uncertain.
