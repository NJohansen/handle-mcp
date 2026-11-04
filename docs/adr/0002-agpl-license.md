# 0002: AGPL-3.0 license

handle-mcp is licensed under AGPL-3.0-only from version 1.1.0. Version 1.0.0 and older stay MIT.

## Why

MIT lets anyone, a store included, run handle-mcp as a closed paid service and give nothing back. AGPL keeps the project free to use, change and share, but anyone who runs a changed version as a network service must offer its source under the same license. It is still open source.

`-only`, not `-or-later`: a future license version from the FSF does not apply without a new decision here.

## Consequences

- Every commit up to this change is by the maintainer, so no contributor had to agree.
- Code already released under MIT stays MIT. The change applies from 1.1.0.
- Third-party code and fixtures keep their own license. MIT code is compatible; its notice goes in `CREDITS.md`.
- New dependencies and copied code must be AGPL-compatible.
