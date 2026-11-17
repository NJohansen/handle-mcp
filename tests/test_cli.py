"""`handle-mcp login/logout <store>`: saves in the keychain only when the login works."""

import io
import json
import os

import pytest

from handle_mcp import cli
from handle_mcp import stores as registry
from tests.conftest import FakeStore

SAVED = {"email": "a@example.com", "session": {"token": "session-1"}}
OLD = {"token": "old"}


class CheckingStore(FakeStore):
    async def get_cart(self):
        if registry.load_login("fake")["password"] != "rigtig":
            raise registry.StoreError("Tjek email og kodeord.")
        return await super().get_cart()


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setattr(registry, "STORES", {"fake": CheckingStore})

    def type_in(email, password):
        monkeypatch.setattr("sys.stdin", io.StringIO(email + "\n"))
        monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: password)

    return type_in


def test_login_saves_a_working_login(terminal, memory_keychain, capsys):
    terminal("a@example.com", "rigtig")
    assert cli.run(["login", "fake"]) == 0
    assert registry.keychain_get("fake") == SAVED  # the session, never the password
    out = capsys.readouterr()
    assert out.out == ""  # nothing on stdout, and the password is never shown
    assert "rigtig" not in out.err and "Logget ind" in out.err


def test_wrong_password_saves_nothing(terminal, memory_keychain, capsys):
    terminal("a@example.com", "forkert")
    assert cli.run(["login", "fake"]) == 1
    assert registry.keychain_get("fake") is None
    assert "Tjek email og kodeord" in capsys.readouterr().err


def test_logout_removes_the_login(memory_keychain):
    registry.keychain_set("fake", "a@example.com", OLD)
    assert cli.run(["logout", "fake"]) == 0
    assert registry.keychain_get("fake") is None


def test_unknown_command_or_store_shows_usage(capsys):
    assert cli.run(["login", "netto"]) == 2
    assert "Brug: handle-mcp login" in capsys.readouterr().err


def test_failed_relogin_keeps_the_old_login(terminal, memory_keychain):
    registry.keychain_set("fake", "a@example.com", OLD)
    terminal("a@example.com", "forkert")
    assert cli.run(["login", "fake"]) == 1
    assert registry.keychain_get("fake") == {"email": "a@example.com", "session": OLD}
    assert "HANDLE_FAKE_PASSWORD" not in os.environ  # the check leaves no env vars


def test_logout_without_a_keychain_says_so(monkeypatch, capsys):
    from keyring.errors import NoKeyringError

    def no_keychain(*_args):
        raise NoKeyringError("no backend")

    monkeypatch.setattr(registry.keyring, "delete_password", no_keychain)
    assert cli.run(["logout", "fake"]) == 1
    assert "Ingen nøglering" in capsys.readouterr().err


@pytest.mark.parametrize("secret", ["not json", '{"email": "a@example.com"}', "[]"])
def test_broken_keychain_entry_gives_a_clear_error(memory_keychain, secret):
    memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")] = secret
    with pytest.raises(registry.StoreError, match="Ugyldigt login i nøgleringen"):
        registry.keychain_get("fake")


def test_load_login_surfaces_a_broken_keychain_entry(memory_keychain):
    memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")] = "not json"
    with pytest.raises(registry.StoreError, match="handle-mcp login fake"):
        registry.load_login("fake")


@pytest.fixture
def config_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "CONFIG_DIR", tmp_path / "handle-mcp")
    monkeypatch.setattr(registry, "STORES", {"fake": CheckingStore})
    return tmp_path / "handle-mcp"


def _mode_is(path, mode):
    """Windows has no mode bits (always 0o666): only POSIX can check them."""
    return os.name == "nt" or path.stat().st_mode & 0o777 == mode


def test_login_from_env_writes_an_owner_only_file(config_dir, monkeypatch, capsys):
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "rigtig")
    assert cli.run(["login", "fake", "--from-env"]) == 0
    path = config_dir / "fake.json"
    assert _mode_is(path, 0o600)
    assert _mode_is(config_dir, 0o700)
    monkeypatch.delenv("HANDLE_FAKE_EMAIL")
    monkeypatch.delenv("HANDLE_FAKE_PASSWORD")
    assert registry.load_login("fake") == SAVED
    assert "rigtig" not in path.read_text(encoding="utf-8")
    out = capsys.readouterr()
    assert out.out == "" and "rigtig" not in out.err and str(path) in out.err


def test_login_from_env_with_a_wrong_password_saves_nothing(config_dir, monkeypatch, capsys):
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "forkert")
    assert cli.run(["login", "fake", "--from-env"]) == 1
    assert not (config_dir / "fake.json").exists()
    assert "Tjek email og kodeord" in capsys.readouterr().err


def test_login_from_env_without_env_vars_says_which(config_dir, monkeypatch, capsys):
    monkeypatch.delenv("HANDLE_FAKE_EMAIL", raising=False)
    monkeypatch.delenv("HANDLE_FAKE_PASSWORD", raising=False)
    assert cli.run(["login", "fake", "--from-env"]) == 1
    assert "HANDLE_FAKE_EMAIL" in capsys.readouterr().err


def test_logout_removes_the_file_too(config_dir, capsys):
    registry.config_set("fake", "a@example.com", OLD)
    assert cli.run(["logout", "fake"]) == 0
    assert not (config_dir / "fake.json").exists()
    assert "slettet fra config-filen." in capsys.readouterr().err  # one line, not two


def test_logout_removes_file_and_keychain_in_one_line(config_dir, capsys):
    registry.config_set("fake", "a@example.com", OLD)
    registry.keychain_set("fake", "a@example.com", OLD)
    assert cli.run(["logout", "fake"]) == 0
    assert "slettet fra config-filen og nøgleringen." in capsys.readouterr().err


def test_logout_file_only_without_a_keychain(config_dir, monkeypatch, capsys):
    from keyring.errors import NoKeyringError

    def no_keychain(*_args):
        raise NoKeyringError("no backend")

    monkeypatch.setattr(registry.keyring, "delete_password", no_keychain)
    registry.config_set("fake", "a@example.com", OLD)
    assert cli.run(["logout", "fake"]) == 0
    assert "slettet fra config-filen." in capsys.readouterr().err


def test_login_from_env_tightens_an_existing_wide_file(config_dir, monkeypatch):
    config_dir.mkdir()
    old = config_dir / "fake.json"
    old.write_text(
        '{"email": "old@example.com", "password": "gammelt-og-langt-kodeord"}', encoding="utf-8"
    )
    old.chmod(0o644)
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "rigtig")
    assert cli.run(["login", "fake", "--from-env"]) == 0
    assert _mode_is(old, 0o600)
    assert old.read_text(encoding="utf-8") == json.dumps(SAVED)  # no old tail, no password


def test_login_from_env_warns_when_the_keychain_wins(config_dir, monkeypatch, capsys):
    registry.keychain_set("fake", "old@example.com", OLD)
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "rigtig")
    assert cli.run(["login", "fake", "--from-env"]) == 0
    assert "nøgleringen har også et login" in capsys.readouterr().err


def test_missing_login_error_names_the_headless_way(config_dir):
    with pytest.raises(registry.StoreError, match="handle-mcp login fake --from-env"):
        registry.load_login("fake")


def test_login_from_env_survives_a_broken_keychain_entry(
    config_dir, memory_keychain, monkeypatch, capsys
):
    memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")] = "not json"
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "rigtig")
    assert cli.run(["login", "fake", "--from-env"]) == 0
    assert (config_dir / "fake.json").exists()
    assert "nøgleringen har også et login" in capsys.readouterr().err


@pytest.mark.parametrize(
    "secret", ['{"email": "a@example.com", "session": {}}', '{"session": {"t": "x"}}']
)
def test_entry_without_session_or_password_is_broken(memory_keychain, secret):
    memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")] = secret
    with pytest.raises(registry.StoreError, match="Ugyldigt login i nøgleringen"):
        registry.keychain_get("fake")


def test_an_old_saved_password_is_still_read(memory_keychain):
    """Saved before docs/adr/0003: read once, then the store replaces it with a session."""
    memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")] = json.dumps(
        {"email": "a@example.com", "password": "rigtig"}
    )
    assert registry.load_login("fake") == {"email": "a@example.com", "password": "rigtig"}
    registry.save_session("fake", "a@example.com", {"token": "new"})
    assert registry.load_login("fake") == {"email": "a@example.com", "session": {"token": "new"}}
    assert "rigtig" not in memory_keychain.secrets[(registry.KEYCHAIN_SERVICE, "fake")]


def test_save_session_replaces_an_old_password_in_the_file(config_dir):
    config_dir.mkdir(mode=0o700)
    path = config_dir / "fake.json"
    path.write_text('{"email": "a@example.com", "password": "rigtig"}', encoding="utf-8")
    path.chmod(0o600)
    registry.save_session("fake", "a@example.com", {"token": "new"})
    assert "rigtig" not in path.read_text(encoding="utf-8")
    assert _mode_is(path, 0o600)


def test_save_session_never_writes_when_env_vars_hold_the_login(config_dir, monkeypatch):
    monkeypatch.setenv("HANDLE_FAKE_EMAIL", "a@example.com")
    monkeypatch.setenv("HANDLE_FAKE_PASSWORD", "rigtig")
    registry.save_session("fake", "a@example.com", {"token": "new"})
    assert not (config_dir / "fake.json").exists()


class Tty(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def asked(monkeypatch, terminal, memory_keychain):
    """A login on a real terminal, with no answer saved and nothing in the environment."""
    monkeypatch.delenv("HANDLE_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)

    def login(reply):
        monkeypatch.setattr("sys.stdin", Tty(f"a@example.com\n{reply}\n"))
        monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "rigtig")
        return cli.run(["login", "fake"])

    return login


@pytest.mark.parametrize(("reply", "saved"), [("j", True), ("ja", True), ("", False), ("n", False)])
def test_login_asks_once_and_only_a_yes_turns_counting_on(asked, capsys, reply, saved):
    assert asked(reply) == 0
    err = capsys.readouterr().err
    assert "Tæl med? (j = ja, Enter = nej)" in err and "handle-mcp telemetry off" in err
    assert "\033" not in err  # the test terminal is not a real one: plain text
    assert cli.telemetry.answer() is saved and cli.telemetry.enabled() is saved
    assert asked("j") == 0  # the second login does not ask again
    assert "Tæl med?" not in capsys.readouterr().err
    assert cli.telemetry.answer() is saved


def test_login_without_a_terminal_never_asks(terminal, memory_keychain, monkeypatch, capsys):
    monkeypatch.delenv("HANDLE_TELEMETRY", raising=False)
    terminal("a@example.com", "rigtig")
    assert cli.run(["login", "fake"]) == 0
    assert "Tæl med?" not in capsys.readouterr().err
    assert cli.telemetry.answer() is None and not cli.telemetry.enabled()


def test_login_does_not_ask_when_the_environment_has_answered(asked, monkeypatch, capsys):
    monkeypatch.setenv("HANDLE_TELEMETRY", "0")
    assert asked("j") == 0
    assert "Tæl med?" not in capsys.readouterr().err and cli.telemetry.answer() is None


def test_telemetry_on_off_status(monkeypatch, capsys):
    monkeypatch.delenv("HANDLE_TELEMETRY", raising=False)
    assert cli.run(["telemetry", "status"]) == 0
    assert "slået fra. Du er ikke blevet spurgt endnu." in capsys.readouterr().err
    assert cli.run(["telemetry", "on"]) == 0 and cli.telemetry.enabled()
    assert cli.question.QUESTION in capsys.readouterr().err  # on shows the whole question, plain
    assert cli.run(["telemetry", "status"]) == 0
    assert "slået til." in capsys.readouterr().err
    monkeypatch.setenv("DO_NOT_TRACK", "1")  # the environment wins, and both commands say so
    assert cli.run(["telemetry", "on"]) == 0 and cli.run(["telemetry", "status"]) == 0
    err = capsys.readouterr().err
    assert (
        err.count("slået fra: HANDLE_TELEMETRY=0, DO_NOT_TRACK=1") == 2 and "slået til" not in err
    )
    monkeypatch.delenv("DO_NOT_TRACK")
    assert cli.run(["telemetry", "off"]) == 0 and not cli.telemetry.enabled()
    assert cli.run(["telemetry", "maybe"]) == 2
    assert capsys.readouterr().out == ""


def test_telemetry_on_says_so_when_the_answer_cannot_be_saved(monkeypatch, capsys):
    def read_only(yes):
        raise PermissionError("read-only")

    monkeypatch.setattr(cli.telemetry, "set_consent", read_only)
    assert cli.run(["telemetry", "on"]) == 1
    assert "Kunne ikke gemme dit svar (PermissionError)" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("env", "name", "tty", "color"),
    [
        ({}, "posix", True, True),
        ({}, "posix", False, False),
        ({"NO_COLOR": "1"}, "posix", True, False),
        ({"TERM": "dumb"}, "posix", True, False),
        ({}, "nt", True, False),
        ({"WT_SESSION": "x"}, "nt", True, True),
    ],
)
def test_color_only_where_the_terminal_shows_it(monkeypatch, env, name, tty, color):
    for key in ("NO_COLOR", "TERM", "WT_SESSION"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli.os, "name", name)
    monkeypatch.setattr("sys.stderr", Tty() if tty else io.StringIO())
    assert cli._color() is color


@pytest.fixture
def fancy(monkeypatch, terminal, memory_keychain):
    """A login where the terminal can show the logo, frames and arrow keys. Records what it shows."""
    monkeypatch.delenv("HANDLE_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    shown: list[str] = []
    monkeypatch.setattr("sys.stdin", Tty())
    monkeypatch.setattr(cli.tui, "fancy", lambda: True)
    monkeypatch.setattr(cli.tui, "banner", lambda store: shown.append(f"banner {store}"))
    monkeypatch.setattr(cli.tui, "text", lambda _title, _hint="": "a@example.com")
    monkeypatch.setattr(cli.tui, "password", lambda _title, _hint="": "rigtig")
    monkeypatch.setattr(cli.tui, "frame", lambda title, body, dim=(), hint="": shown.append(body))
    monkeypatch.setattr(cli.tui, "done", shown.append)
    monkeypatch.setattr(cli.tui, "failed", shown.append)
    return shown


@pytest.mark.parametrize(("pick", "saved"), [(0, False), (1, True)])
def test_the_fancy_login_asks_with_no_first_and_the_same_words(fancy, monkeypatch, pick, saved):
    offered: list[list[str]] = []

    def choose(_title, choices, _hint=""):
        offered.append(choices)
        return choices[pick]

    monkeypatch.setattr(cli.tui, "choose", choose)
    assert cli.run(["login", "fake"]) == 0
    assert offered == [["Nej tak", "Ja, tæl med"]]  # the pointer starts on no
    assert cli.telemetry.answer() is saved
    body = fancy[2]
    plain = [line.strip() for line in cli.question.QUESTION.splitlines()[3:]]
    assert [line.strip() for line in body.splitlines()] == plain
    assert fancy[0] == "banner fake" and "Logget ind på fake" in fancy[1]


@pytest.mark.parametrize(
    ("env", "name", "tty", "expected"),
    [
        ({}, "posix", True, True),
        ({}, "posix", False, False),
        ({"NO_COLOR": "1"}, "posix", True, False),
        ({"TERM": "dumb"}, "posix", True, False),
        ({}, "nt", True, False),
        ({"WT_SESSION": "x"}, "nt", True, True),
    ],
)
def test_the_fancy_login_only_on_a_terminal_that_shows_it(monkeypatch, env, name, tty, expected):
    for key in ("NO_COLOR", "TERM", "WT_SESSION"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli.tui.os, "name", name)
    monkeypatch.setattr("sys.stdin", Tty() if tty else io.StringIO())
    monkeypatch.setattr("sys.stderr", Tty() if tty else io.StringIO())
    assert cli.tui.fancy() is expected


def test_the_logo_rows_line_up_and_fade_from_blue_to_yellow():
    assert len(cli.tui.LOGO) == 6 and max(map(len, cli.tui.LOGO)) <= 78
    rows = cli.tui.logo_rows()
    assert cli.tui.BLUE in rows[0] and cli.tui.YELLOW in rows[4]
    assert all(cli.tui.ACCENT in row for row in rows)  # the shadow edge
    assert cli.tui._mix(0, 4) == cli.tui.BLUE and cli.tui._mix(4, 4) == cli.tui.YELLOW
