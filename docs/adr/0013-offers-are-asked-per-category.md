# 0013: Offers are asked per category

Date: 2026-11-14

## Context

`list_offers` showed a small part of each store's offers, and nothing said so (live 2026-11-14):

- nemlig: only the five lists on /tilbud (Skarp pris, Priskup, Dagstilbud, Undgå madspild,
  gifts). The page also has a block per category, and 1,273 products in those blocks were on
  none of the five lists. A campaign such as fruit at one price was never in the answer.
- BilkaToGo: the first 25 of about 14,600 offers, in the index's own order. More than half of
  the offers are clothes, toys and other non-food.
- REMA 1000: 191 of the leaflet's 416 products were dropped, because they are advertised at a
  fixed price and are no campaign.

One answer with every offer is over 1,000 products per store: too slow, and too much for a
model to read well.

## Decision

`list_offers` takes an optional `category`, one of twelve names in `stores.OFFER_CATEGORIES`.

- Without it the answer is the first look it was, plus nemlig's gifts wherever they are.
- With it each store gives every offer in the category, up to 100 per store.
- Each store maps a name to one or more of its own categories: nemlig's sub-pages of /tilbud,
  BilkaToGo's `consumerFacingHierarchy.lvl0`, REMA 1000's departments. A store's categories do
  not line up: BilkaToGo keeps cold cuts in "Mejeri & køl", so "pålæg" and "mejeri og æg" give
  the same list there.
- An unknown name is an error that lists the known names. A guess would drop offers in silence.
- A product at its normal price in a category list is no offer and is left out.
- A leaflet product at a fixed price is an offer with no price before, in `list_offers` only.
  Campaigns come first, so a fixed price never pushes a price cut out of the answer.

## Consequences

- A category call is one small request per store (nemlig about 0.3 s, against 1.3 s for the
  whole page), so asking for five categories costs less than one answer with everything.
- The caller must ask per category. The tool description says so. A caller that does not ask
  sees what it saw before.
- nemlig's fish offers have no sub-page, so "kød og fisk" is meat only there.
- nemlig's category pages give no end date: `offer_until` is `null` on those products.
- nemlig has no name for a campaign that has no block of its own: such a product is "Tilbud"
  with the price before.
- A new category in a store needs a line in that store's map.
