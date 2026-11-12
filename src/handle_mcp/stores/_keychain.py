"""The OS keychain, for a secret of any length.

Windows Credential Manager holds 2560 bytes per entry, and keyring writes UTF-16: about 1280
characters. A REMA 1000 session is longer (#151). So a long secret is split: the entry <name>
holds {"parts": n, "id": x}, and the pieces are the entries <name>.<x>.1 to <name>.<x>.n.
A short secret is one entry, as it always was. See docs/adr/0012.
"""

from __future__ import annotations

import contextlib
import json
import secrets

import keyring

PIECE = 1000  # characters per entry: under the Windows limit, with room to spare


def _index(secret: str | None) -> tuple[str, int] | None:
    """(id, parts) when the entry points at pieces; None when it is the secret itself."""
    try:
        data = json.loads(secret or "")
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) != {"parts", "id"}:
        return None
    if isinstance(data["id"], str) and isinstance(data["parts"], int):
        return data["id"], data["parts"]
    return None


def _names(name: str, index: tuple[str, int] | None) -> list[str]:
    return [f"{name}.{index[0]}.{i}" for i in range(1, index[1] + 1)] if index else []


def _forget(service: str, names: list[str]) -> None:
    for piece in names:  # best effort: a piece left behind is unreachable and encrypted
        with contextlib.suppress(Exception):
            keyring.delete_password(service, piece)


def read(service: str, name: str) -> str | None:
    """The secret, or None when nothing is saved. ValueError when pieces are missing."""
    for _ in range(2):  # another process may replace the pieces between two reads: look again
        secret = keyring.get_password(service, name)
        index = _index(secret)
        if index is None:
            return secret or None
        pieces = [keyring.get_password(service, piece) for piece in _names(name, index)]
        if all(pieces):
            return "".join(pieces)
    raise ValueError("pieces of the saved login are missing")


def write(service: str, name: str, secret: str) -> None:
    """Save the secret. The pieces go first and the entry that points at them last, so a
    reader sees the old login or the new one, never a mix."""
    old = _names(name, _index(keyring.get_password(service, name)))
    if len(secret) <= PIECE:
        keyring.set_password(service, name, secret)
    else:
        parts = [secret[i : i + PIECE] for i in range(0, len(secret), PIECE)]
        index = (secrets.token_hex(4), len(parts))
        new = _names(name, index)
        try:
            for piece, part in zip(new, parts, strict=True):
                keyring.set_password(service, piece, part)
            keyring.set_password(service, name, json.dumps({"parts": index[1], "id": index[0]}))
        except BaseException:
            _forget(service, new)
            raise
    _forget(service, old)


def delete(service: str, name: str) -> None:
    """Remove the secret and its pieces. PasswordDeleteError when nothing was saved."""
    old = _names(name, _index(keyring.get_password(service, name)))
    keyring.delete_password(service, name)
    _forget(service, old)
