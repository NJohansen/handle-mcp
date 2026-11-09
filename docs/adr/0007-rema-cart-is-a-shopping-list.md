# 0007: REMA 1000's cart is a shopping list

REMA 1000 is the third store. Its webshop is pickup only (Køb & Hent), in some stores. handle-mcp never touches REMA's own cart: it is tied to a pickup store, a pickup time, a coupon and payment jobs, and all of that is the human's (ADR 0001, ADR 0006). The cart in handle-mcp is a shopping list in REMA's app, the same lists the human already uses.

This extends ADR 0001: for REMA 1000, the list is the cart, and the list writes below are the only writes allowed. The list is close to an order, because REMA's terms say a Køb & Hent order starts from it. So the same lines hold as for a cart: the human opens the list, turns it into an order, picks the time and pays. handle-mcp never does any of those.

## One list called "handle-mcp"

- `get_cart` and `set_cart_quantities` use the one list named exactly `handle-mcp`. It is created on the first write and never made primary.
- A line the human ticks off in the app (`bought: true`) is bought: `get_cart` leaves it out, and the next write removes it. The list empties itself while the human shops.
- Quantities are absolute, and every write is read back, as in the other stores.
- If a Køb & Hent order does not tick the lines off, the model asks "Er listen handlet?" and empties the list after a yes.

## Safe writes

Creating the list and adding a line are POSTs, not absolute. They are never retried blindly: after a timeout, a network error, a 429 or a 5xx, the adapter reads the list again, up to 3 times 1 second apart, and POSTs only if the list or the line is still missing. Changes and removals set absolute values and keep the normal retries.

A read that lags can still let a second list or line through. The adapter recovers by itself, so the human never has to clean up:

- Two or more lists named `handle-mcp`: the one with the lowest id is the list. The others are left alone, never deleted, and `get_cart` names them in a warning.
- A product on two lines of the list: its quantity is the sum. The next write sets the first line and removes the others.

## The pickup store

`handle-mcp login rema1000` asks for one or more stores, in order, on the human's own terminal. The choice is saved locally with the session. Nothing is set at REMA. A store without Køb & Hent can be chosen: the list is also for shopping in the store yourself, and pickup times appear when the store gets Køb & Hent. The first chosen store with Køb & Hent gives `pickup_store` and the pickup times.

## Fees

Køb & Hent has a packing fee and a packaging fee that vary with the order size (terms, part 7.1). The calls we know do not give them, so `fees` is `null` with a reason, and `compare_basket` says the fee is missing. The trip to the store is not priced (ADR 0006).

## Never

The adapter never calls REMA's cart or payment endpoints, sets a store, a time or a coupon, touches another list, deletes a list, makes a list primary, shares a list, or reads a list `with=users` (names and emails). `tests/test_safety.py` greps for `v3/cart`, `v3/jobs`, `vendor-baskets`, `checkoutCallback`, `/payment`, a `DELETE` and `primary` set to true.

## Counting

A filled list is not a filled cart. It is counted as its own event, `list_filled` (store, total rounded to 50 kr, item count), with the same rule as `cart_filled` in ADR 0005: once per list, after 30 minutes without changes. Kept apart, so the numbers for the stores never mix carts and lists.

## Why

- A list is the one place REMA lets a program write that the human sees and controls, and that cannot order, pick a time or take money.
- One fixed name keeps handle-mcp away from the human's own lists and gives one list, not a new one each day.
- REMA's own webshop makes the same list calls, so they are what REMA expects to see.

Facts and design from the Go port [McAndersDK/handle-mcp-go](https://github.com/McAndersDK/handle-mcp-go) (MIT): its ADR 0008 and research, verified live 2026-11-07. It uses one list per day; we use one fixed list.

## Not proven live

The list writes have not been tried live. The PR that adds the list starts with one live write test, and stops if it fails. REMA's own terms say a Køb & Hent order starts from the shopping list ([handelsbetingelser](https://rema1000.dk/information/handelsbetingelser-scan-selv), part 3). Whether the order ticks the lines off is not known.
