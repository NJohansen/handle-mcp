# 0005: Anonymous usage counts, no id

handle-mcp sends two events to Umami: `cart_filled` (store, total rounded to 50 kr, item count, version, date) and `active` (version, date, at most once per machine per day). Every cart link the human clicks carries `utm_source=handlemcp&utm_medium=mcp&utm_campaign=cart`. On by default. Off with `HANDLE_TELEMETRY=0`, `DO_NOT_TRACK=1` or `--no-telemetry`. A notice on stderr at the first start says what is counted and how to turn it off.

## Why

To show the stores how many carts and kroner handle-mcp sends them, for a partner deal. The UTM tags let the store measure it in its own analytics; the events are our own count next to it.

No install id. A random id saved on the user's machine is pseudonymous personal data, and saving it for statistics needs consent under the ePrivacy rules. Without an id, nothing points to a person: the events are counts. Unique machines per week come from Umami's own daily-rotating visitor hash, as on handlemcp.dk. The local file holds only a flag and a date.

## Consequences

- A cart counts once after 5 minutes without changes (a model fills a cart in many calls). A cart changed again an hour later counts again. An emptied cart and a cart with a refused line do not count.
- Weekly active machines and retention are estimates, not exact.
- Sends run in a daemon thread with a 2 s timeout. Every error is logged at debug level and never reaches a tool. Waiting carts are sent when the server stops.
- Tests and CI never send: `tests/conftest.py` sets `HANDLE_TELEMETRY=0`.
