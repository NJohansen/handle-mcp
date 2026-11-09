# 0005: Anonymous usage counts, no id

handle-mcp sends four events to Umami, a funnel from install to a filled cart: `server_started` (os), `first_tool_call` (tool name) and `login_ok` (store), each at most once per machine (and store) per day, and `cart_filled` (store, total rounded to 50 kr, item count). Every event has version and date (day only). Every cart link the human clicks carries `utm_source=handlemcp&utm_medium=mcp&utm_campaign=cart`. On by default. Off with `HANDLE_TELEMETRY=0`, `DO_NOT_TRACK=1` or `--no-telemetry`. The first tool answer on a machine carries `telemetry_notice`, and the server instructions tell the model to pass it on: the human hears it once, in the chat. The same text goes to stderr (the client's log) until then.

## Why

To show the stores how many carts and kroner handle-mcp sends them, for a partner deal, and to see where people stop between install and a filled cart. `first_tool_call` separates real users from catalogs and scanners that only list the tools. The UTM tags let the store measure it in its own analytics; the events are our own count next to it.

No install id. A random id saved on the user's machine is pseudonymous personal data, and saving it for statistics needs consent under the ePrivacy rules. Without an id, the event fields point to no person: they are counts. The request itself still carries the sender's IP address, which is personal data under GDPR. Umami Cloud uses it to answer and to guess the country, and does not save it; Umami is our data processor. On by default with opt-out is therefore a choice about the IP too: we accept it because the IP is never stored, the purpose is narrow (counting carts per store), the human is told in the chat on first use, and one env var turns it off. If that balance changes, the answer is opt-in. Unique machines per week come from Umami's own daily-rotating visitor hash, as on handlemcp.dk. The local file holds only a flag and the last day per daily event.

## Consequences

- Opt-out only works if people know. A notice in a log file nobody reads would be hidden tracking, so the notice goes where the human reads: the chat. The README says it in the first lines.
- Umami sees the sender's IP address (to answer and to guess the country). It does not save it. The privacy page says so.

- A cart counts once per order: after 30 minutes without changes (a model fills a cart in many calls), then the store is locked, so edits to the same cart send nothing. The lock is a store name in `telemetry.json`. A read that finds the cart empty (after checkout) sends a waiting cart at once and unlocks the store. A write to a locked store reads the cart first, so the next order counts even when the model goes straight to the write. A cart emptied through handle-mcp and a cart with a refused line do not count. A normal close sends a waiting cart; a killed process loses it (too few, never too many).
- Weekly active machines and retention are estimates, not exact. Daily events count machine-days.
- `login_ok` means a store sent back the user's cart; a login that is never used is not counted. `first_tool_call` counts a call when it starts, also one that fails (e.g. no login): the user tried. Its file read and write run once a day on the event loop; a tiny local file, accepted.
- Sends run in a daemon thread with a 2 s timeout. Every error is logged at debug level and never reaches a tool. Waiting carts are sent when the server stops.
- Tests and CI never send: `tests/conftest.py` sets `HANDLE_TELEMETRY=0`.
- REMA 1000 has a shopping list, not a cart ([ADR 0007](0007-rema-cart-is-a-shopping-list.md)). A filled list counts as its own event, `list_filled` (store, total rounded to 50 kr, item count), with the same once-per-list rule. The privacy page on handlemcp.dk names it too.
