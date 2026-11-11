# 0009: REMA 1000's login is a cookie session, and the store choice stays local

REMA 1000 has no token API like nemlig.com or BilkaToGo. Its webshop logs in with an OAuth page and keeps the session in cookies. Its Køb & Hent times belong to a store, and REMA's own store choice is part of its cart, which handle-mcp never touches (ADR 0001, ADR 0007).

## Decision

- `handle-mcp login rema1000` runs REMA's own login once: the login page, one POST with email and password, the redirects. The redirects are followed by hand, to REMA's hosts only. A queue or a bot check stops the login: never worked around.
- Only the site's session cookies are saved (`access_token`, `refresh_token`, `api_session` and the load balancer's `AWSALB` pair), with `access_exp`. Never the password (ADR 0003).
- The access token lives about an hour. It is renewed with the cookies, through the site's own refresh call. That call is never retried: a retry could burn a refresh token that was just rotated. When REMA refuses it, the human logs in again. REMA rotates the refresh token on every renewal, and several handle-mcp processes (Claude Desktop, Claude Code, a test run) share the saved session. So before renewing, a process takes the saved session when another one already renewed it, instead of spending a refresh token that is no longer valid. Two processes that renew in the same second can still collide; a lock across processes is more than that rare case is worth.
- The login runs on its own HTTP client. Its cookies never ride along with a search or an API call, which take the Bearer token only.
- After the login, the human picks one or more stores, in order, on their own terminal. Store ids only are saved with the session, on the machine; `HANDLE_REMA1000_STORE_ID` overrides them. Nothing is set at REMA.
- The first chosen store with Køb & Hent gives `pickup_store` and the times. The store list is read again after an hour, so a store that gets Køb & Hent shows up by itself. A store without it can be chosen: search and the list still work.

## Why

- The cookies are what REMA's own webshop keeps. Anything else would need a client REMA does not expect.
- A local store choice keeps the human's REMA account as it is, and keeps handle-mcp away from REMA's cart and its store, time and payment.

Facts from the Go port [McAndersDK/handle-mcp-go](https://github.com/McAndersDK/handle-mcp-go) (MIT), verified live 2026-11-07.
