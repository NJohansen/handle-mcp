# 0016: Nemlig authentication redirects are disabled

Nemlig's login and API calls use an HTTP client that does not follow redirects.

## Decision

- `NemligStore._send()` rejects 3xx responses instead of forwarding the request.
- Queue-it redirects keep their existing Danish queue error. They are not followed or bypassed.
- The login JSON field `RedirectUrl` is not treated as an instruction to send the login request elsewhere.
- A trusted redirect, if Nemlig later proves that one is required, must be implemented explicitly and manually with a narrow host allowlist.

## Why

Httpx may repeat a 307 or 308 request to a different host, including the original method and body. The Nemlig login body contains the email and password. Automatic redirects could therefore forward credentials to an unexpected origin.

The live login tested on 2026-11-18 returned a normal 200 response and used `RedirectUrl` only as JSON data. The live read-only Nemlig suite still passed with redirects disabled.

## Consequences

- Old or changed Nemlig endpoints that return an unexplained redirect fail safely.
- A real and required Nemlig redirect needs explicit implementation and tests; it must not rely on automatic cross-host forwarding.
