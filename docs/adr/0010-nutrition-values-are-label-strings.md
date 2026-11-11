# 0010: Nutrition values are the label's numbers as strings, not money

`get_nutrition` returns what the store's "Næringsindhold" table says per 100 g or 100 ml. The stores write `"0,13 g"`, `"1.017 kJ"`, `"329 kJ / 78 Kcal"` and `"<0,5 g"`.

## Decision

- Every value is a string with a dot decimal and as many decimals as the label: `"0.13"`, `"1017"`, `"4.0"`. It is not a Decimal, so `privacy.jsonable()` does not round it to two decimals like money (ADR 0002). Salt `"0.125"` stays `"0.125"`.
- "Less than" stays in the value: `"<0.5"`. Dropping the `<` would make a guess look like a fact.
- `per` is `"100 g"` or `"100 ml"` from the label's header, or `null` when the store does not say. Values are never converted between the two. REMA 1000's table says "Pr. 100 g/ml": there `per` follows the product's price unit (kg → `"100 g"`, ltr → `"100 ml"`), and is `null` for a product sold per piece.
- A line the label leaves out is `null`. A product without a label (often fresh meat, fruit and vegetables) has `nutrition: null` and a Danish `reason`.
- Nutrition is its own tool, not a field in `search_products` or `compare_basket`: nemlig needs one call per product, and the answers stay small.

## Consequences

- A model that wants a number parses the string. One with a `<` is an upper bound.
- `"2.100 g"` with a dot decimal would read as 2100. No store writes that today: BilkaToGo and nemlig's productbff use a comma decimal.
