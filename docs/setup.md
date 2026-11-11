# Setup

Works on macOS, Linux and Windows. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/).

**1. Logins.** Save each store's login in your OS keychain (macOS Keychain, Windows Credential Locker or Linux Secret Service). It asks for email and password, logs in, and saves only the session the store gives back. The password is never saved ([ADR 0003](adr/0003-save-the-session-not-the-password.md)). When the session expires (nemlig: about once a year), the tool asks you to log in again:

```sh
uvx handle-mcp@latest login nemlig
uvx handle-mcp@latest login bilkatogo
uvx handle-mcp@latest login rema1000
```

`login rema1000` then asks for your REMA 1000 stores: search by postcode, city or name, and pick one or more in the order you prefer. The choice is saved on your machine with the session; nothing is set at REMA. A store without Køb & Hent is fine: the first one with Køb & Hent gives the pickup times. With `--from-env`, set `HANDLE_REMA1000_STORE_ID` (store ids, comma-separated) for the server instead. REMA's access token lasts about an hour; the server renews it by itself with the saved session.

`handle-mcp logout <store>` removes it again. From a clone, use `uv run handle-mcp login nemlig`.

Other ways, checked in this order:
1. Env vars `HANDLE_<STORE>_EMAIL` and `HANDLE_<STORE>_PASSWORD` (e.g. `HANDLE_NEMLIG_EMAIL`).
2. The keychain (above). Recommended.
3. A file `~/.config/handle-mcp/<store>.json`, written by `--from-env` below. It holds the session, not the password, and the server refuses it unless only you can read it (`chmod 600`). Windows has no file modes, so there it relies on your user profile's permissions ([ADR 0004](adr/0004-windows-has-no-file-modes.md)).

**Headless / AI agent.** No terminal and no keychain (a Linux server, a container, an agent that sets itself up)? Put the login in env vars for one command, which logs in and writes the session to `~/.config/handle-mcp/<store>.json` with `chmod 600`:

```sh
HANDLE_NEMLIG_EMAIL=you@example.com HANDLE_NEMLIG_PASSWORD='...' \
  uvx handle-mcp@latest login nemlig --from-env
```

The env vars are only needed for that one command; the MCP server reads the file afterwards. Remove them again: the file has no password. `handle-mcp logout <store>` removes the file. Nothing is written when the login fails.

Without any login, `list_offers` still works for nemlig; `search_products` needs a login (nemlig's search answers 500 without one). BilkaToGo needs a login for everything: the store, prices and offers follow your delivery address. REMA 1000's search and offers need no login; its pickup times do.

**2. BilkaToGo:** choose home delivery (not pickup) once on bilkatogo.dk. The server reads the store and fees from your cart.

**3. Add it to your MCP client.** Claude Code:

```sh
claude mcp add handle -- uvx handle-mcp@latest
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "handle": {
      "command": "uvx",
      "args": ["handle-mcp@latest"]
    }
  }
}
```

**Updates.** `@latest` runs the newest release from PyPI at each start, so store fixes reach you by themselves. Want to choose when to update? Put a version instead of `latest` in every command, e.g. `handle-mcp@1.5.2`, and change it when you want ([ADR 0008](adr/0008-install-the-latest-release.md)).

Then ask: *"We have 4,000 kr a month for food. Plan this week's meals."* The first time it asks who eats, what you like and which store. Open the store's website to check the cart, choose a time and pay.
