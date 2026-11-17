"""Command line for a human in a terminal: save or remove a store login.

    handle-mcp login                    on a terminal: pick your stores, then as below for each
    handle-mcp login nemlig             asks for email and password, logs in, saves the store's
                                        session in the keychain
    handle-mcp login nemlig --from-env  reads HANDLE_NEMLIG_EMAIL/_PASSWORD, logs in, saves the
                                        session in ~/.config/handle-mcp/nemlig.json (chmod 600).
                                        For a headless machine or an AI agent with no terminal.
    handle-mcp logout nemlig            removes the login from the keychain and the file
    handle-mcp telemetry on|off|status  anonymous usage counts: off until you say yes (ADR 0014)

A store that needs a pickup store (REMA 1000) asks for it after the login, on this terminal.
With --from-env, set HANDLE_<STORE>_STORE_ID (store ids, comma-separated) for the server.

The password is used for one login and then forgotten: never saved, echoed or logged. Only the
session the store gives back is saved (docs/adr/0003). When it expires, log in again.
"""

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import sys
from typing import Any

from keyring.errors import KeyringError

from handle_mcp import question, telemetry, tui
from handle_mcp import stores as registry


def configure_logging() -> None:
    """Log to stderr. httpx logs every request URL at INFO, and URLs can hold ids and
    tokens. MCP clients keep stderr in log files, so httpx only speaks on warnings."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main(mcp: Any) -> None:
    """`handle-mcp`: the MCP server over stdio, or with arguments this command line."""
    configure_logging()
    args = sys.argv[1:]
    if "--no-telemetry" in args:
        telemetry.disable()
        args.remove("--no-telemetry")
    if args:  # `handle-mcp login <store>` from a terminal, not from an MCP client
        sys.exit(run(args))
    telemetry.start()
    mcp.run("stdio")


def _say(text: str) -> None:
    sys.stderr.write(text + "\n")


def run(args: list[str]) -> int:
    known = ", ".join(sorted(registry.STORES))
    if args[:1] == ["telemetry"]:
        return _telemetry(args[1:])
    from_env = "--from-env" in args
    args = [a for a in args if a != "--from-env"]
    if args == ["login"] and not from_env and tui.fancy():
        return _login_picked()
    if len(args) != 2 or args[0] not in ("login", "logout") or args[1] not in registry.STORES:
        _say(
            "Brug: handle-mcp login <butik> [--from-env]  eller  handle-mcp logout <butik>\n"
            f"Butikker: {known}\n"
            "Uden terminal: sæt HANDLE_<BUTIK>_EMAIL og HANDLE_<BUTIK>_PASSWORD, kør med --from-env\n"
            "Anonym tælling: handle-mcp telemetry on|off|status"
        )
        return 2
    command, store = args
    if command == "logout":
        return _logout(store)
    if from_env:
        return _login_from_env(store)
    fancy = tui.fancy()  # a real terminal gets the logo, frames and arrow keys; the words stay
    if fancy:
        tui.banner(store)
    code = _login(store, fancy)
    if code == 0:
        _ask_telemetry(fancy)
    return code


def _login_picked() -> int:
    """`handle-mcp login` with no store, on a terminal that can show a list: pick the stores,
    log in to each in turn. The question about counting comes once, after a login that worked."""
    tui.banner()
    hint = "Pil op/ned flytter. Mellemrum vælger. Enter bekræfter."
    picked = tui.choose("Hvor handler du?", list(registry.STORES), hint, many=True)
    if not picked:
        _say("Ingen butik valgt. Intet er gemt.")
        return 1
    codes = [_login(store, fancy=True) for store in picked]
    if 0 in codes:
        _ask_telemetry(fancy=True)
    return max(codes)


def _login(store: str, fancy: bool) -> int:
    if fancy:
        email = tui.text(f"Email til {store}", "Den email, du bruger på butikkens hjemmeside.")
        # No email (empty, or Ctrl-C): stop here, do not ask for the password.
        password = email and tui.password(f"Kodeord til {store}", "Vises ikke, og gemmes ikke.")
    else:
        _say(
            f"Log ind på {store}. Brug den email og det kodeord, du bruger på butikkens hjemmeside."
        )
        sys.stderr.write(f"Email til {store}: ")
        sys.stderr.flush()
        email = sys.stdin.readline().strip()
        password = getpass.getpass(f"Kodeord til {store} (vises ikke): ")
    if not email or not password:
        _say("Email og kodeord skal udfyldes. Intet er gemt.")
        return 1
    try:  # log in first, save after: a failed login never touches a saved one
        session = _check(store, email, password, choose=True)
    except registry.StoreError as exc:
        text = f"Login blev ikke gemt: {exc}\nEt tidligere gemt login er uændret."
        tui.failed(text) if fancy else _say(text)
        return 1
    try:
        registry.keychain_set(store, email, session)
    except Exception as exc:  # noqa: BLE001  the Windows backend raises its own type
        _say(
            f"Kunne ikke gemme i nøgleringen ({type(exc).__name__}). Intet er gemt.\n"
            f"Uden nøglering: sæt HANDLE_{store.upper()}_EMAIL og _PASSWORD, "
            f"og kør: handle-mcp login {store} --from-env"
        )
        return 1
    text = f"Logget ind på {store}. Sessionen er gemt i nøgleringen. Kodeordet er ikke gemt."
    tui.done(text) if fancy else _say(text)
    return 0


def _ask_telemetry(fancy: bool = False) -> None:
    """Once, on a real terminal, after a login that worked. Enter or anything but yes is a no."""
    try:
        if not telemetry.ask() or not sys.stdin.isatty():
            return
        if fancy:
            names = tuple(name for name, _ in question.FACTS)
            tui.frame(question.TITLE, question.body(), dim=names)
            hint = "Pil op/ned vælger. Enter bekræfter."
            yes = tui.choose("Tæl med?", ["Nej", "Ja"], hint) == "Ja"
        else:
            _say(question.question(color=_color()))
            yes = _ask("  Tæl med? (j = ja, Enter = nej): ").lower() in ("j", "ja", "y", "yes")
        telemetry.set_consent(yes)
        text = "Tak. Tællingen er slået til." if yes else "Tællingen er slået fra. Intet sendes."
        tui.done(text) if fancy else _say(text)
    except Exception:  # the question never breaks a login
        logging.getLogger(__name__).debug("telemetry question failed", exc_info=True)


def _color() -> bool:
    """Bold and dim only where the terminal shows them: never in a pipe, a dumb terminal,
    with NO_COLOR, or in the old Windows console."""
    env = os.environ
    if not sys.stderr.isatty() or "NO_COLOR" in env or env.get("TERM") == "dumb":
        return False
    return os.name != "nt" or "WT_SESSION" in env


FORCED_OFF = "HANDLE_TELEMETRY=0, DO_NOT_TRACK=1 eller --no-telemetry er sat, og de vinder."


def _telemetry(args: list[str]) -> int:
    if args not in (["on"], ["off"], ["status"]):
        _say("Brug: handle-mcp telemetry on|off|status")
        return 2
    try:
        if args != ["status"]:
            telemetry.set_consent(args == ["on"])
    except OSError as exc:
        _say(f"Kunne ikke gemme dit svar ({type(exc).__name__}). Intet er ændret.")
        return 1
    if args == ["on"]:
        _say("Det har du sagt ja til:\n" + question.QUESTION)
    if args == ["off"]:
        _say("Tællingen er slået fra. Intet sendes.")
    elif telemetry.enabled():
        _say("Anonym tælling er slået til. Fra igen: handle-mcp telemetry off")
    elif telemetry.forced_off():
        _say(f"Anonym tælling er slået fra: {FORCED_OFF}")
    else:
        asked = "" if telemetry.answer() is not None else " Du er ikke blevet spurgt endnu."
        _say(f"Anonym tælling er slået fra.{asked}")
    return 0


def _logout(store: str) -> int:
    removed = ["config-filen"] if registry.config_delete(store) else []
    try:
        if registry.keychain_delete(store):
            removed.append("nøgleringen")
    except KeyringError as exc:
        if not removed:
            _say(f"Ingen nøglering på denne maskine: {exc}")
            return 1
    except Exception as exc:  # noqa: BLE001  the Windows backend raises its own type
        _say(f"Kunne ikke slette fra nøgleringen ({type(exc).__name__}).")
        return 1
    _say(f"Login slettet fra {' og '.join(removed)}." if removed else "Der var intet gemt login.")
    return 0


def _login_from_env(store: str) -> int:
    """No terminal, no keychain: a headless box or an AI agent. The env vars are read once,
    checked against the store and saved in a file only the owner can read."""
    prefix = f"HANDLE_{store.upper()}_"
    email, password = os.environ.get(prefix + "EMAIL"), os.environ.get(prefix + "PASSWORD")
    if not email or not password:
        _say(f"Sæt {prefix}EMAIL og {prefix}PASSWORD, og kør igen. Intet er gemt.")
        return 1
    try:  # log in first, save after: a failed login never touches a saved one
        session = _check(store, email, password)
    except registry.StoreError as exc:
        _say(f"Login blev ikke gemt: {exc}\nEt tidligere gemt login er uændret.")
        return 1
    path = registry.config_set(store, email, session)
    _say(
        f"Logget ind på {store}. Sessionen er gemt i {path} (kun du kan læse den). "
        f"Kodeordet er ikke gemt: fjern {prefix}PASSWORD igen."
    )
    try:
        shadowed = registry.keychain_get(store) is not None
    except registry.StoreError:  # a broken entry: load_login will complain about it too
        shadowed = True
    if shadowed:  # load_login reads the keychain first
        _say(
            f"OBS: nøgleringen har også et login til {store}, og det vinder over filen. "
            f"Fjern det med: handle-mcp logout {store}, og kør så --from-env igen."
        )
    return 0


def _ask(text: str) -> str:
    sys.stderr.write(text)
    sys.stderr.flush()
    return sys.stdin.readline().strip()


def _numbers(raw: str, most: int) -> list[int]:
    """ "2, 1" as list positions 1..most, in order, without repeats."""
    out: list[int] = []
    for part in raw.replace(" ", ",").split(","):
        if part.isdigit() and 1 <= int(part) <= most and int(part) not in out:
            out.append(int(part))
    return out


async def _choose(instance: Any) -> None:
    """Pick the stores in order of preference. The list is the store's own, shown here only."""
    _say("Vælg de butikker, du vil bruge, i den rækkefølge du foretrækker dem.")
    while query := _ask("Søg efter butik (postnummer, by eller navn; tom = spring over): "):
        choices = await instance.store_choices(query)
        if not choices:
            _say("Ingen butikker passer. Prøv en anden søgning.")
            continue
        for i, (_, text) in enumerate(choices, 1):
            _say(f"{i:>3}. {text}")
        picked = _numbers(_ask("Skriv numrene, fx 2,1 (tom = søg igen): "), len(choices))
        if picked:
            instance.choose_stores([choices[i - 1][0] for i in picked])
            _say("Valgt: " + " | ".join(choices[i - 1][1] for i in picked))
            return
    _say(f"Ingen butik valgt. Vælg senere med: handle-mcp login {instance.name}")


async def _verify(instance: Any, choose: bool) -> None:
    check = getattr(instance, "check_login", None)  # a store with no cart to read yet
    await (check() if check else instance.get_cart())
    if choose and hasattr(instance, "store_choices"):
        await _choose(instance)


def _check(store: str, email: str, password: str, choose: bool = False) -> dict[str, str]:
    """A real, read-only login with these values (they win over saved ones via env vars).
    With `choose`, a store that needs a pickup store asks for it. Returns the session."""
    prefix = f"HANDLE_{store.upper()}_"
    keys = {prefix + "EMAIL": email, prefix + "PASSWORD": password}
    before = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    instance = registry.STORES[store]()
    try:
        asyncio.run(_verify(instance, choose))
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    session = instance.session()
    if not session:
        raise registry.StoreError(f"{store} gav ingen session tilbage. API'et kan have ændret sig.")
    return session
