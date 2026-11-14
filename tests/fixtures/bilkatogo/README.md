Real, redacted BilkaToGo answers from nickknissen/bilkatogo
(https://github.com/nickknissen/bilkatogo, MIT License, Copyright (c) 2026 Nick Nissen).

`cart_logged_in.json` is a pickup cart (Bilka Vejle). `cart_home.json` is the same cart
changed by hand to look like home delivery. It is not a real capture. A live test on
2026-11-01 confirmed the fields it uses (fees, minimum order, address marker).

`algolia_offers.json`: live capture 2026-11-02 (public search-only key, read-only). One query:

    POST https://f9vbjlr1bk-dsn.algolia.net/1/indexes/*/queries
    {"requests": [{"indexName": "prod_BILKATOGO_PRODUCTS", "params":
      "query=&hitsPerPage=10&filters=isInOffer:1653 AND isInAssortmentIn:1653 AND nonsearchable:false
       &attributesToRetrieve=[name,brand,gtin,netcontent,productType,price,isInCurrentLeaflet,cpOffer,multipromos,storeData.1653]"}]}

`isInOffer` is a list of store ids (not `true`), so filter `isInOffer:<sid>`. 1653 is a public
store id. Offer fields are in `storeData.<sid>`: `offerDescription` ("Skarp pris",
"Mix 10 for 25,00", "Se Her"), `price` / `unitsOfMeasureOfferPrice` in øre, `multiPromoPrice` +
`offerCount` for mix offers, `offerMax` / `offerMaxDescription`, `offerFrom` / `offerUntil`
(empty in this capture), `beforePrice` (0 in this capture).

## Offers by category (live capture, 2026-11-14, public search-only key, read-only)

Same endpoint and index as `algolia_offers.json`. The store id in `params` and the `storeData`
key are replaced with 1653, the public store id the other fixtures use, so the counts belong to
another store than 1653. `_highlightResult` and Algolia's timing fields are removed.

`offers_facets.json`: `query=&hitsPerPage=0&filters=isInOffer:<sid> AND isInAssortmentIn:<sid>
AND nonsearchable:false&facets=[...]&maxValuesPerFacet=200`. The index has two category trees,
both facets: `categories.lvl0`-`lvl2` (13 top names, "Frugt og grønt") and
`consumerFacingHierarchy.lvl0`-`lvl4` (22 top names, "Frugt & grønt"; the tree behind
`deepestCategoryPath`). The file keeps `lvl0` of both; the call also asked for `lvl1` and
`searchHierachy`. `nbHits` is every offer in the store: 14,644.

`offers_category.json`: the offers in one category:

    filters=consumerFacingHierarchy.lvl0:"Frugt & grønt" AND isInOffer:<sid>
            AND isInAssortmentIn:<sid> AND nonsearchable:false
    attributesToRetrieve=[name,brand,gtin,netcontent,productType,deepestCategoryPath,price,
                          storeData.<sid>,leafletTitle,isInCurrentLeaflet,categories,
                          consumerFacingHierarchy]

24 hits, cut to 6: two mix offers ("Mix 10 for 25,00", "Mix 3 for 35,00"), two "Skarp pris" and
two "Se Her". The last four are in the leaflet: `isInCurrentLeaflet` true and `leafletTitle`
the leaflet's name for the offer ("Danske lammefjordskartofler"); the mix offers have
`isInCurrentLeaflet` false and `leafletTitle` "". `categories.lvl0:"Frugt og grønt"` gives 69
hits instead: it also holds 43 products from "Mejeri & køl" (sandwich salads) in the other tree.

## `available_delivery_dates.json` (live capture, 2026-11-02, logged in, read-only GET)

`GET https://api.bilkatogo.dk/api/shop/v3/AvailableDeliveryDates?u=w`, trimmed to 3 days. `uid`,
`eid` and `tid` (personal/session ids) are replaced with "X". Home delivery, night slot only.
Mon is closed (past deadline), Tue is sold out (`closed_text` "udsolgt", no intervals), Wed is open.

## `recipes/` (live capture, 2026-11-06, no login, read-only GET)

`GET https://www.bilkatogo.dk/_nuxt/static/1793920097/inspiration/opskrifter/<path>/payload.js`
for `""` (opskrifter), `madplaner` (week 46), `aftensmad`, `aftensmad/danske-retter`,
`aftensmad/danske-retter/karbonader` and `aftensmad/pastaretter/carbonara`, saved as they came.
`unknown-page.html` is what the site answers for a page it does not know
(`/inspiration/opskrifter/nope/`): HTTP 200, the website's HTML with the build id.
No personal data: the pages are public. The only name is the recipes' author.
In `test_bilkatogo_recipes.py` the Algolia hits for the recipe's products are
`algolia_products.json` hits with `objectID` changed by hand to karbonader's item numbers.

`algolia_nutrition.json`: one Algolia result (`results[0]`) for
`filters=objectID:19753 OR objectID:120041 OR objectID:20824` with
`attributesToRetrieve=["name","infos"]`, captured 2026-11-11 without a login. Skyr (19753)
and rugbrød (20824) have `infos` code `nutritional_100`; hakket oksekød (120041) has none.
The rows are `{type: 2, title, value}`: "Næringsindhold pr." = "100 g", two "Energi" rows
("233 kJ", "55 kcal"), "- heraf mættede fedtsyrer", "1.017 kJ" with a thousands dot. Public
product data, nothing personal.
