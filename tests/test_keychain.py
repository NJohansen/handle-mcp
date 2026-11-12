"""A login of any length fits the keychain: Windows holds 2560 bytes per entry (#151)."""

import json
import os
import sys

import keyring
import pytest

from handle_mcp import cli
from handle_mcp import stores as registry
from handle_mcp.stores import _keychain
from tests.conftest import WINDOWS_LIMIT, CredWriteError

# A REMA 1000 session with the lengths measured in a real one (2026-11-12): 2503 characters as
# saved, about twice what one Windows entry holds.
LONG = {
    "access_token": "a" * 1004,
    "refresh_token": "r" * 742,
    "api_session": "s" * 342,
    "AWSALB": "b" * 124,
    "AWSALBCORS": "c" * 124,
    "access_exp": "1" * 10,
}
SHORT = {"token": "session-1"}
SERVICE = registry.KEYCHAIN_SERVICE


def test_a_long_login_is_saved_in_pieces_and_read_back(memory_keychain):
    registry.keychain_set("fake", "a@example.com", LONG)
    assert registry.keychain_get("fake") == {"email": "a@example.com", "session": LONG}
    assert len(memory_keychain.secrets) > 1
    assert all(
        len(v.encode("utf-16-le")) <= WINDOWS_LIMIT for v in memory_keychain.secrets.values()
    )


def test_a_short_login_is_one_entry_as_before(memory_keychain):
    registry.keychain_set("fake", "a@example.com", SHORT)
    assert json.loads(memory_keychain.secrets[(SERVICE, "fake")])["session"] == SHORT
    assert len(memory_keychain.secrets) == 1


def test_a_new_login_removes_the_old_pieces(memory_keychain):
    registry.keychain_set("fake", "a@example.com", LONG)
    first = set(memory_keychain.secrets)
    registry.keychain_set("fake", "a@example.com", LONG | {"access_token": "n" * 1004})
    assert len(memory_keychain.secrets) == len(first)  # no pieces left from the first login
    assert set(memory_keychain.secrets) & first == {(SERVICE, "fake")}
    registry.keychain_set("fake", "a@example.com", SHORT)
    assert set(memory_keychain.secrets) == {(SERVICE, "fake")}


def test_logout_removes_every_piece(memory_keychain):
    registry.keychain_set("fake", "a@example.com", LONG)
    assert cli.run(["logout", "fake"]) == 0
    assert not memory_keychain.secrets


def test_a_missing_piece_gives_a_clear_error(memory_keychain):
    registry.keychain_set("fake", "a@example.com", LONG)
    piece = next(k for k in memory_keychain.secrets if k[1].endswith(".2"))
    del memory_keychain.secrets[piece]
    with pytest.raises(registry.StoreError, match="handle-mcp login fake"):
        registry.keychain_get("fake")


def test_a_failed_save_keeps_the_old_login_and_leaves_no_pieces(memory_keychain, monkeypatch):
    registry.keychain_set("fake", "a@example.com", LONG)
    before = dict(memory_keychain.secrets)
    real, calls = memory_keychain.set_password, []

    def fails_on_the_third(service, username, password):
        calls.append(username)
        if len(calls) == 3:
            raise CredWriteError(1783, "CredWrite", "The stub received bad data")
        real(service, username, password)

    monkeypatch.setattr(memory_keychain, "set_password", fails_on_the_third)
    with pytest.raises(CredWriteError):
        registry.keychain_set("fake", "a@example.com", LONG | {"access_token": "n" * 1004})
    assert memory_keychain.secrets == before


@pytest.fixture
def broken_write(memory_keychain, monkeypatch):
    def refuse(service, username, password):
        raise CredWriteError(1783, "CredWrite", "The stub received bad data")

    monkeypatch.setattr(memory_keychain, "set_password", refuse)


def test_login_says_so_when_the_keychain_refuses(broken_write, monkeypatch, capsys):
    """The Windows backend raises its own type, not a KeyringError: no traceback (#151)."""
    from tests.test_cli import CheckingStore

    monkeypatch.setattr(registry, "STORES", {"fake": CheckingStore})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("a@example.com\n"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "rigtig")
    assert cli.run(["login", "fake"]) == 1
    err = capsys.readouterr().err
    assert "Kunne ikke gemme i nøgleringen" in err and "--from-env" in err
    assert "rigtig" not in err


def test_a_renewed_session_that_cannot_be_saved_does_not_stop_the_tool(
    memory_keychain, monkeypatch
):
    registry.keychain_set("fake", "a@example.com", SHORT)

    def refuse(service, username, password):
        raise CredWriteError(1783, "CredWrite", "The stub received bad data")

    monkeypatch.setattr(memory_keychain, "set_password", refuse)
    registry.save_session("fake", "a@example.com", LONG)  # logs a warning, raises nothing
    assert registry.keychain_get("fake") == {"email": "a@example.com", "session": SHORT}


@pytest.mark.parametrize("parts", [0, -1, True, 10**9, "2"])
def test_an_entry_with_a_bad_count_is_a_broken_login_not_a_missing_one(memory_keychain, parts):
    memory_keychain.secrets[(SERVICE, "fake")] = json.dumps({"parts": parts, "id": "ab12"})
    with pytest.raises(registry.StoreError, match="Ugyldigt login"):
        registry.keychain_get("fake")


def refuse_to_read(service, username):
    raise CredWriteError(5, "CredRead", "Access is denied")


def test_a_keychain_that_cannot_be_read_gives_a_clear_error(memory_keychain, monkeypatch):
    monkeypatch.setattr(memory_keychain, "get_password", refuse_to_read)
    with pytest.raises(registry.StoreError, match="Nøgleringen kunne ikke læses"):
        registry.load_login("fake")
    assert registry.has_login("fake") is False
    registry.save_session("fake", "a@example.com", SHORT)  # raises nothing


def test_logout_says_so_when_the_keychain_refuses(memory_keychain, monkeypatch, capsys):
    monkeypatch.setattr(memory_keychain, "get_password", refuse_to_read)
    assert cli.run(["logout", "fake"]) == 1
    assert "Kunne ikke slette fra nøgleringen" in capsys.readouterr().err


@pytest.mark.real_keychain
@pytest.mark.skipif(
    sys.platform != "win32" or not os.environ.get("CI"),
    reason="writes in the real Windows Credential Manager: CI only",
)
def test_windows_credential_manager_takes_a_long_login():
    service, secret = "handle-mcp-test", json.dumps({"email": "a@example.com", "session": LONG})
    with pytest.raises(Exception):  # noqa: B017  the bug: one entry is too small
        keyring.set_password(service, "whole", secret)
    try:
        _keychain.write(service, "fake", secret)
        assert _keychain.read(service, "fake") == secret
    finally:
        _keychain.delete(service, "fake")
    assert _keychain.read(service, "fake") is None
