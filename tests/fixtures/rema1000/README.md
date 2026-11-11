# REMA 1000 fixtures

Real answers from `https://api.digital.rema1000.dk/api`, captured 2026-11-08 with GET only, logged
out. Public product data: nothing personal in them. Trimmed: each product keeps `id`, `name`,
`underline`, `department` and `category` (id and name), `barcodes`, `labels` (id and name),
`prices`, `is_available_in_all_stores` and `is_weight_item`; `meta.pagination` keeps the page
numbers only.

| File | Call | Kept |
|---|---|---|
| `search_milk.json` | `search/products?query=mælk&per_page=3` | the 3 products |
| `search_oksekod.json` | `search/products?query=hakket oksekød&per_page=100` | the 5 "HK. OKSEKØD" products, the blend "HK. OKSEKØD, 35% GRØNT" first |
| `stores.json` | `v3/stores?per_page=100&page=1`, captured 2026-11-09, logged out | 6 stores, 3 with Køb & Hent first. Only `id`, `name`, `postal_code`, `city`, `is_click_and_collect_active`: phone, address, the merchant's name and opening hours are cut. `meta` says one page |
| `offers.json` | `search/products?filter[labels]=9001&sort=department&per_page=4` | 2 products. `prices` has the offer period (is_campaign, max 6, `price_over_max_quantity`) and the normal price after it |

Prices are kroner as JSON numbers (`7.95`), not øre. `ending_at` is the last day of a period.

The login and the pickup times (`v3/stores/{id}/time-slots`) need a REMA account, so
`tests/test_rema1000_login.py` builds them in code, in the shape the Go port
[McAndersDK/handle-mcp-go](https://github.com/McAndersDK/handle-mcp-go) verified live on
2026-11-07: the slots are `data`: day -> list of `{from, to, is_available}` in UTC.

`product_skyr.json`, `product_letmaelk.json`, `product_oksekoed.json`:
`GET https://api.digital.rema1000.dk/api/v3/products/{id}?include=nutrition_info` for 20385
(skyr vanilje), 20758 (letmælk) and 400171 (hakket oksekød), captured 2026-11-11 without a
login, trimmed to `id`, `name`, `underline`, `prices` and `nutrition_info`. The rows are
`{name, value}`: "Energi" = "318 KJ / 75 kcal", "Fedt" = "< 0,5", values without a unit. The
oksekød has `nutrition_info: []`. An unknown id answers 404 `{"error_type": "NotFound"}`.
Public product data, nothing personal.
