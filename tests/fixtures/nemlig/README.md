Shapes from eisbaw/nemlig_cli `nemlig_api.md` (MIT), with personal data replaced by
fixed test values (Kunde Eksempel, Testvej 1, 9999 Eksempelby, kunde@example.com). These
files are shapes, not captures, unless a section below says otherwise.

`order_history_flex.json` and `order_details_flex.json` are real captures (2026-11-02) of an
order with flexible delivery. Name, address, notes, coupon, DebitorId and KVHX are replaced
with "X", and the order number is a test value. Product lines, amounts and dates are real.

`search.json` `Recipes`: the fields documented in `nemlig_api.md` (`Id`, `Name`, `Url`,
`TotalTime`, `NumberOfPersons`). Not a live capture yet.

## Offers (live captures, 2026-11-03 and 2026-11-14, logged in, read-only GET)

`offers_page.json`: `GET https://webapi.prod.knl.nemlig.it/productbff/api/web/page?path=/tilbud`,
the data behind nemlig.com/tilbud. `pageContent[]` has `ProductList` blocks with `header.title`
and `products[]` inline (same product shape as the recipe files; `price` and `priceOriginal`
in øre). The offer lists are "Skarp pris", "Ugens priskup", "En gave til dig", "Dagstilbud" and
"Undgå madspild"; the rest ("Frugt og grønt", "Kød", ...) are categories. No user id needed,
unlike the old `/tilbud?GetAsJson=1` + `GetByProductGroupId` (the page URL is queued by queue-it
in busy hours).

The file is two captures put together:

- The banner and the five offer lists are the 2026-11-03 capture, unchanged (5 products per
  list, one "Mix 2 stk." Priskup product added from the same capture). On 2026-11-14 the page
  had no "En gave til dig" list.
- The page fields (`structuredData`, `seo`, `topBanner`, `breadcrumbs`) and four category blocks
  are the 2026-11-14 capture. `navigationItems` is cut to the lists in the file ("Favoritter",
  a logged-in list, is left out with its block "Favoritter på tilbud").
- The category blocks are in another order than on the page: "Frugt og grønt" comes first on
  nemlig.com, but is last here, because tests read `pageContent[-1]`. Its second product
  (5024698, "2 stk. 15,-") is from 2026-11-03.

What the category blocks cover (2026-11-14 unless noted):

| Block | `header.button.url` | Products |
|---|---|---|
| Mejeri og æg | `/tilbud/mejeri-og-aeg` | 5038613 and 5040184 "Skarp pris"; 923214 cheaper than `priceOriginal`, no `campaignLines`; 706008 "Priskup" |
| Drikkevarer | `/tilbud/drikkevarer` | 106517 "Mix 2 stk. 25,-" + "Priskup"; 5604110 badge "God pris", `priceOriginal` null, no `campaignLines` (not an offer); 5070387 "Mix 2 stk. 45,-"; 5605401 cheaper; 5602213 "6 stk. 69,-" |
| Brød, kiks og kager | `/tilbud/broed-kiks-og-kager` | 5606369 a gift: `price` 0, "En gave til dig", `labelMaxQuantity` 1, sold out; 5055078 cheaper; 5062435 "God pris", `priceOriginal` null; 5047400 "Mix 2 stk. 50,-" |
| Frugt og grønt | `/tilbud/frugt-og-groent` | 5058121, 5001423 and 5049872 at 15 kr., cheaper than `priceOriginal`, no `campaignLines` and no campaign name anywhere; 5603155 "Skarp pris", sold out |

A product on offer in a category block has no campaign name and no end date: only `price` below
`priceOriginal` (and `priceDiscount`, `campaignBadge` "Spar 3,-"). The blocks on /tilbud are not
always complete: on 2026-11-14 "Mejeri og æg" had 36 products here and 61 on its sub-page,
"Drikkevarer" 200 here and 213 there.

`offers_page_frugt-og-groent.json` and `offers_page_mejeri-og-aeg.json`: the same call with
`path=/tilbud/frugt-og-groent` and `path=/tilbud/mejeri-og-aeg` (the "Se alle" links),
2026-11-14. Same shape as /tilbud, `navigationItems` empty, `breadcrumbs` Tilbud > the page.

- Frugt og grønt: one block, "Friske favoritter til kurven", 35 products on the page (the same
  35 as the block on /tilbud), cut to 6.
- Mejeri og æg: two blocks. "Lurpak kun 12 kr. " (`layout` "Onerow") is a campaign block: the
  block title is the only place the campaign name is. Both its products are kept. "Mejeri og æg"
  is cut to 7: the 4 from `offers_page.json` and 3 that are not in the Mejeri block on /tilbud
  (5605447 and 5071597 are in no block on /tilbud; 5062129 is only in another block there).

In all three files `tracking`/`dataLayerTracking` are removed, and `isFavorite`,
`isInShoppingList` and `quantity` are false, false and 0.

The home page (`path=/`) answers a `testPage` with an empty `pageContent`, logged in or not
(2026-11-14), so the gifts on the front page are not in this call. No fixture for it.

## `search_gift.json`

`GET https://webapi.prod.knl.nemlig.it/searchgateway/api/search?query=mums rosinboller&take=10&skip=0&recipeCount=0&timestamp=…&timeslotUtc=…&deliveryZoneId=…`,
trimmed to product 5606321 (Facets, Ads, Recipes emptied). Free gift: `Price` 20.45 but
`Campaign` = `{Type: ProductCampaignFreeProduct, Code: U, CampaignPrice: 0, MaxQuantity: 1,
IntervalEnd: 2026-12-31T22:59:59Z}`, `SubCategory` "Gave fra nemlig.com".

## `delivery_days.json` (live capture, 2026-11-02, logged in, read-only GET)

`GET https://www.nemlig.com/webapi/v2/Delivery/GetDeliveryDays?days=3&showForSubscriptions=false`,
3 days, nothing removed: the answer has no personal data (slot ids are global). `Type` 0 =
Personlig, 1 = Fleksibel. `Availability` 0 = free, 1 = past deadline. Tue 14-21: Personlig 19 kr,
Fleksibel 25 kr. Wed 14-21 Personlig: 0 kr.

## Recipes (live captures, 2026-11-03, read-only GETs)

nemlig's website moved to Angular. Page URLs with `?GetAsJson=1` now give HTML, and in busy
hours they redirect to queue-it. The recipe pages read from `productbff`, with the same Bearer
token as `/webapi/` (`GET /webapi/Token`). `tracking` and `dataLayerTracking` removed,
`isFavorite`/`isInShoppingList` set to false, at most 2 alternatives per ingredient.

| File | Call |
|---|---|
| `recipe_details.json` | `GET https://webapi.prod.knl.nemlig.it/productbff/api/web/meals/recipeDetails/kebabfad-med-fladbrod-98001303` (without `structuredData`) |
| `recipe_products.json` | `GET .../meals/recipeProductDialog?recipeId=kebabfad-med-fladbrod-98001303&servings=4&maxProductsPerIngredient=10`: `includedProducts` to buy, `selfSuppliedProducts` "Vi regner med du har". `price` is øre. `servings` 2-12 changes `item.quantity` |
| `recipes_by_tag.json` | `GET .../meals/allRecipes?skip=0&take=8&categoryPath=aftensmad&filters=familievenlig&filters=budgetvenlig`: `filters[]` is nemlig's tag list (groups of `{path, title}`), `requestedCategory.recipes[]` the hits (tags combine with AND; no `categoryPath` = aftensmad) |
| `recipe_search.json` | `GET .../search/recipes?query=kylling karry&take=5&skip=0`: `searchResult.items[]` with `id` (the slug), `title`, no time or persons. The old searchgateway `Recipes` also has recipes the new API answers 500 for |
| `meals_page.json` | `GET .../page?path=/maaltider`: "Ugens udvalgte", `pageContent[].recipes[]` |

Also seen in the website's code, not used: `meals/filters/{path}` (one tag, all categories),
`meals/purchased` ("Mine opskrifter", 401 without login) and
`POST /webapi/basket/AddRecipeToBasket` (never call it: we fill the cart with
`set_cart_quantities` after the human says yes).

`product_details_cocio.json` and `product_details_flanksteak.json`:
`GET https://webapi.prod.knl.nemlig.it/productbff/api/web/productDetails/{id}` for 5070417
(Cocio kakaomælk) and 5027322 (flanksteak), captured 2026-11-11 with the anonymous token,
`structuredData` removed. `product.detailDeclaration[]` has `tableHeader`
("Næringsindhold pr. 100 ml", "") and `tableItems` ([label, value]); "Energi" is
"329 kJ / 78 Kcal" in one value. The flanksteak has an empty table. No EAN anywhere.
Public product data, nothing personal.
