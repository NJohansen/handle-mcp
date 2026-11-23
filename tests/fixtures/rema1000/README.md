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

`offers_department.json`: `search/products?filter[labels]=9001&filter[departments]=10&sort=department&per_page=100`,
captured 2026-11-14, logged out, trimmed like the files above.
12 products in the answer, 3 kept: two campaign products (`is_campaign` and `is_advertised` true,
max 6, the normal price after it) and "FULDK. BURGER", which is in the leaflet (label 9001,
`is_advertised` true) but is no campaign (`is_campaign` false, one price period to 2027-02-06).
On 2026-11-14 the leaflet had 416 products: 225 campaigns and 191 advertised only.

`filter[departments]=<department id>` is the department filter. `filter[department]`,
`filter[department_id]` and `filter[is_campaign]` answer 400; a plain `department=` is ignored.
No call lists the departments: `meta.filters` has only `labels`, and `GET departments` answers
405. The leaflet's departments on 2026-11-14, counted by paging through label 9001:

| id | Department | Products |
|---|---|---|
| 10 | Brød & Bavinchi | 12 |
| 20 | Frugt & grønt | 7 |
| 30 | Kød, fisk & fjerkræ | 29 |
| 40 | Køl | 19 |
| 50 | Frost | 31 |
| 60 | Mejeri | 1 |
| 70 | Ost m.v. | 15 |
| 80 | Kolonial | 97 |
| 90 | Drikkevarer | 50 |
| 100 | Husholdning | 18 |
| 110 | Baby og småbørn | 26 |
| 120 | Personlig pleje | 28 |
| 130 | Slik | 81 |
| 160 | Nemt & hurtigt | 2 |

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

## Recipes

Captured 2026-11-23 with GET only, logged out. Public: nothing personal in them.

| File | Call | Kept |
|---|---|---|
| `recipes_search.json` | `search/recipes?query=lasagne&per_page=2` | the 2 recipes, without ingredients and steps. "Glutenfri lasagne" has `servings.amount` 0 |
| `recipe_lasagne.json` | `rema1000dk/entities?filter[type]=recipe&filter[slug]=lasagne` | the whole recipe: 3 ingredient groups, 3 groups of steps |
| `recipe_tags.json` | `rema1000dk/entities?filter[type]=recipeTag&per_page=100` | all 30 tags: `id`, `type`, title and slug |
| `recipes_by_tag.json` | `rema1000dk/entities?filter[type]=recipe&filter[tags.sys.id]=5Q5t9rpmNk4jp1ygKZDEHx&per_page=3&sort=-created_at` (the tag "Avisopskrifter") | the 3 newest of 13, without ingredients and steps |

Trimmed: a recipe keeps `id`, `type`, `created_at`, title, slug, the image's `url`, `customForm`
(without `relatedProducts`), its tags (`id`, `type`, title, slug), `popularity` and
`allProductsAvailable`. An ingredient's `digitalProduct` keeps `id`, `title`,
`amount_of_content`, `unit_of_content`, `is_basic_ingredient`, `amount` and `active_product`
(`id`, `name`, `underline`, `labels`, `prices`). `meta.pagination` keeps the page numbers only.

- The search answers with whole recipes, like the entity call. It has no tag filter:
  `filter[tags]`, `filter[tag]`, `tags=` and eight more spellings are ignored (708 recipes
  every time). The tag filter is `filter[tags.sys.id]=<tag id>` on `rema1000dk/entities`, as the
  website's own tag pages ask. `filter[tags]` there answers 400. Two ids with a comma find
  nothing, so more tags are checked in the answer.
- `sort=-popularity` and `sort=-created_at` work on both calls.
- `digitalProduct.amount` is packs for the recipe's own persons. Salt in a second ingredient
  group has `amount` 0. The sum of `price * amount` for products that are not
  `is_basic_ingredient` is the `price` REMA shows for the recipe (lasagne: 87).
- `totalTime` was 0 in all 23 recipes read. 20 of 289 ingredients had no `active_product`,
  15 had no `digitalProduct`.
