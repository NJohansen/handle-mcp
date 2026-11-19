# 0018: Guesses do not make basket totals

`compare_basket` may suggest a store result when no product name matches. Keep that candidate and its price visible for review, but do not include it in a basket total as if it were the requested item.

If any line is a guess, `products_total` and `total` are `null`, and `minimum_met` is unknown (`null`). Add a note naming the guessed items. Do not silently sum only the confirmed lines: that subtotal could be mistaken for the full basket total. Fees and per-line candidates remain available. Store comparisons still use only items every store has matched without a guess.

## Why

A guessed product can be unrelated to the requested item. Including its price makes a store quote look complete when it is not; dropping it silently makes a partial subtotal look complete instead.

## Consequences

- The model must resolve or disclose guessed products before relying on aggregate totals or minimum-order status.
- Consumers of `compare_basket` must handle `null` totals when a quote is incomplete.
