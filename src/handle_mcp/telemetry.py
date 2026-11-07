"""Anonymous usage counts: how many carts and kroner handle-mcp fills in each store per week.

No id, no names, no addresses, no logins, no products, no order ids (docs/adr/0005). The only
file is `telemetry.json` in the config folder: the notice was shown, and the last day an
"active" event went out. Off with HANDLE_TELEMETRY=0, DO_NOT_TRACK=1 or `--no-telemetry`.
Every send runs in a background thread with a short timeout. A failure is logged, never raised.
"""

from __future__ import annotations

import atexit
import functools
import json
import logging
import os
import sys
import threading
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from handle_mcp import stores as registry

log = logging.getLogger(__name__)

URL = "https://cloud.umami.is/api/send"  # Umami's event API; HANDLE_TELEMETRY_URL overrides
WEBSITE = ""  # the Umami website that counts the events; HANDLE_TELEMETRY_WEBSITE overrides
HOSTNAME = "app.handlemcp.dk"  # a label in Umami, not a server
TIMEOUT = 2.0  # seconds
QUIET = 300.0  # seconds without a cart change before the cart counts as filled
ROUND_TO = Decimal(50)  # kroner
STORE_NAMES = {"bilkatogo": "bilka"}
OFF = {"0", "false", "no", "off"}

NOTICE = """\
handle-mcp tæller anonymt, hvor mange kurve den fylder: butik, beløb (afrundet til 50 kr.),
antal varer, version og dato. Ingen navne, adresser, logins, varer eller ordre-id.
Slå det fra med HANDLE_TELEMETRY=0 eller: handle-mcp --no-telemetry
Læs mere: https://github.com/NJohansen/handle-mcp#brugsstatistik
"""

_off = False
_active_day: str | None = None
_lock = threading.Lock()
_pending: dict[str, tuple[threading.Timer, dict[str, Any]]] = {}


def _safe(fn: Callable[..., None]) -> Callable[..., None]:
    """Telemetry never breaks a tool: every error ends here, in the log."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            log.debug("telemetry failed", exc_info=True)

    return wrapper


def disable() -> None:
    global _off
    _off = True


def enabled() -> bool:
    if _off or os.environ.get("HANDLE_TELEMETRY", "").strip().lower() in OFF:
        return False
    return os.environ.get("DO_NOT_TRACK", "").strip().lower() in {"", *OFF}


def _version() -> str:
    try:
        return version("handle-mcp")
    except PackageNotFoundError:
        return "unknown"


def _state_file():
    return registry.CONFIG_DIR / "telemetry.json"


def _state() -> dict[str, Any]:
    try:
        state = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _save(state: dict[str, Any]) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


@_safe
def start() -> None:
    """At server start: the notice once per machine, then today's "active" event."""
    if not enabled():
        return
    state = _state()
    if not state.get("notice_shown"):
        sys.stderr.write(NOTICE)
        _save({**state, "notice_shown": True})
    active()


@_safe
def active() -> None:
    """At most one "active" event per machine per day. Cheap: called on every tool answer."""
    global _active_day
    today = date.today().isoformat()
    if _active_day == today or not enabled():
        return
    _active_day = today
    state = _state()
    if state.get("last_active") == today:
        return
    _save({**state, "last_active": today})
    _send("active", {})


def _get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def basket(cart: Any) -> tuple[int, int]:
    """(total in kroner rounded to the nearest 50, number of items) of a cart."""
    total = Decimal(str(_get(cart, "total") or 0))
    items = sum(int(_get(line, "quantity") or 0) for line in _get(cart, "lines") or [])
    return int((total / ROUND_TO).quantize(Decimal(1), ROUND_HALF_UP) * ROUND_TO), items


@_safe
def cart_filled(store: str, cart: Any, results: list[Any]) -> None:
    """A cart changed. Counted only when every line went in. A model fills a cart in many
    calls, so the event waits until the cart is quiet for QUIET seconds and counts it once."""
    if not enabled() or not all(_get(r, "ok") for r in results):
        return
    total, items = basket(cart)
    with _lock:
        if old := _pending.pop(store, None):
            old[0].cancel()
        if not items:  # an emptied cart is not a filled one
            return
        data = {"store": STORE_NAMES.get(store, store), "basket_total_dkk": total}
        data["item_count"] = items
        timer = threading.Timer(QUIET, _flush, args=(store,))
        timer.daemon = True
        _pending[store] = (timer, data)
        timer.start()


@_safe
def _flush(store: str, wait: bool = False) -> None:
    with _lock:
        entry = _pending.pop(store, None)
    if entry:
        entry[0].cancel()
        _send("cart_filled", entry[1], wait)


@atexit.register
def _flush_all() -> None:
    """The MCP client closes the server: count the carts still waiting, then stop."""
    for store in list(_pending):
        _flush(store, wait=True)


def _send(event: str, data: dict[str, Any], wait: bool = False) -> None:
    website = os.environ.get("HANDLE_TELEMETRY_WEBSITE", WEBSITE)
    if not website:
        log.debug("telemetry: no website id, %s not sent", event)
        return
    data = {**data, "version": _version(), "date": date.today().isoformat()}
    payload = {
        "type": "event",
        "payload": {
            "website": website,
            "hostname": HOSTNAME,
            "url": "/".join(["", event, *([data["store"]] if "store" in data else [])]),
            "name": event,
            "data": data,
        },
    }
    thread = threading.Thread(target=_post, args=(payload,), daemon=True)
    thread.start()
    if wait:  # at exit: give the last event its timeout before Python stops the thread
        thread.join(TIMEOUT)


def _post(payload: dict[str, Any]) -> None:
    try:
        httpx.post(
            os.environ.get("HANDLE_TELEMETRY_URL") or URL,
            json=payload,
            headers={"User-Agent": f"Mozilla/5.0 (compatible; handle-mcp/{_version()})"},
            timeout=TIMEOUT,
        )
    except Exception:
        log.debug("telemetry: send failed", exc_info=True)
