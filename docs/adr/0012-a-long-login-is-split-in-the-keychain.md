# 0012: A long login is split in the keychain

A saved login longer than 1000 characters is split over several keychain entries. The entry `<store>` then holds `{"parts": n, "id": x}`, and the pieces are the entries `<store>.<x>.1` to `<store>.<x>.n`. A shorter login is one entry, as before. The code is `stores/_keychain.py`.

## Why

Windows Credential Manager holds 2560 bytes per entry, and keyring writes UTF-16: about 1280 characters. A REMA 1000 session (two tokens and three cookies) is about 2500 characters as saved, so `handle-mcp login rema1000` could not save on Windows (#151). The Windows backend also raises its own error type, not a `KeyringError`, so the human saw a traceback.

The other choices were worse:

- Fall back to the login file without asking: the session would be in plain text on disk when the human asked for the keychain.
- Save less of the session: the size of a token is the store's choice, and it can grow again.

## Consequences

- The split is the same on every OS, so the tests on every OS cover it. The keychain in the tests has the Windows limit, and a test on Windows in CI writes a long login in the real Credential Manager.
- The pieces are written first and the entry that points at them last, with a new id for each save. A reader gets the old login or the new one, never a mix. The old pieces are removed after the save, and `logout` removes all of them.
- Two processes that save at the same moment can leave the pieces of the loser behind. They are encrypted, and nothing points at them.
- A save that fails is caught whatever its type. `login` says so in Danish and names `--from-env`; the server logs a warning and continues.
- An older handle-mcp cannot read a split login. It asks for a new login.
