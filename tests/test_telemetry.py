"""Anonymous usage counts: what is sent, when, and that it can never break a tool."""

import json
import threading
from datetime import date

import pytest

from handle_mcp import server, telemetry
from handle_mcp import stores as registry
from tests.conftest import LEAK


@pytest.fixture
def sent(monkeypatch):
    """Telemetry on, with a website id, and a sender that records instead of posting."""
    events: list[dict] = []
    monkeypatch.delenv("HANDLE_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.setenv("HANDLE_TELEMETRY_WEBSITE", "site-1")
    monkeypatch.setattr(telemetry, "_post", events.append)
    monkeypatch.setattr(telemetry, "QUIET", 3600)  # tests flush by hand

    class Now(threading.Thread):  # run the "background" send at once
        def start(self):
            self.run()

    monkeypatch.setattr(telemetry.threading, "Thread", Now)
    return events


def names(events):
    return [e["payload"]["name"] for e in events]


async def fill(store="fake", items=None):
    await server.set_cart_quantities(store, items or {"2": 3})
    telemetry._flush_all()


async def test_a_filled_cart_sends_exactly_the_documented_fields(sent):
    await fill()
    event = sent[-1]["payload"]
    assert event["name"] == "cart_filled" and event["website"] == "site-1"
    assert event["url"] == "/cart_filled/fake"  # the weekly script filters stores by path
    # FakeStore: "1" x2 + "2" x3 at 12.95 + 39 fee = 103.75 kr: rounds to 100
    assert event["data"] == {
        "store": "fake",
        "basket_total_dkk": 100,
        "item_count": 5,
        "version": telemetry._version(),
        "date": date.today().isoformat(),
    }


async def test_no_personal_data_and_no_products_leave(sent):
    await fill()
    text = json.dumps(sent).lower()
    for value in [*LEAK.values(), "Andeby 1", "mælk", "Mælk"]:
        assert str(value).lower() not in text
    assert "product" not in text and "order" not in text


async def test_many_changes_count_as_one_cart(sent):
    for qty in (1, 2, 3):
        await server.set_cart_quantities("fake", {"2": qty})
    telemetry._flush_all()
    assert names(sent).count("cart_filled") == 1
    assert sent[-1]["payload"]["data"]["item_count"] == 5


async def test_an_emptied_cart_is_not_counted(sent):
    await server.set_cart_quantities("fake", {"2": 2})
    await server.set_cart_quantities("fake", {"1": 0, "2": 0})
    telemetry._flush_all()
    assert "cart_filled" not in names(sent)


async def test_a_cart_with_a_failed_line_is_not_counted(sent, monkeypatch):
    from handle_mcp.models import QuantityResult

    async def refuse(self, items):
        return [QuantityResult(pid, q, 0, False) for pid, q in items.items()]

    monkeypatch.setattr(registry.STORES["fake"], "set_quantities", refuse)
    await fill()
    assert "cart_filled" not in names(sent)


async def test_bilkatogo_is_counted_as_bilka(sent):
    telemetry.cart_filled("bilkatogo", {"total": "624.10", "lines": [{"quantity": 7}]}, [])
    telemetry._flush_all()
    assert sent[-1]["payload"]["data"]["store"] == "bilka"
    assert sent[-1]["payload"]["data"]["basket_total_dkk"] == 600


@pytest.mark.parametrize(
    ("total", "rounded"), [("0", 0), ("24.99", 0), ("25.00", 50), ("649.50", 650), ("675", 700)]
)
def test_totals_round_to_the_nearest_50(total, rounded):
    assert telemetry.basket({"total": total, "lines": []})[0] == rounded


async def test_active_at_most_once_per_day_even_after_a_restart(sent, monkeypatch):
    await server.get_cart("fake")
    await server.get_cart("fake")
    monkeypatch.setattr(telemetry, "_active_day", None)  # a new process, same day
    await server.get_cart("fake")
    assert names(sent) == ["active"]
    state = json.loads((registry.CONFIG_DIR / "telemetry.json").read_text())
    assert state == {"last_active": date.today().isoformat()}  # a date, never an id


@pytest.mark.parametrize(
    ("env", "value"),
    [("HANDLE_TELEMETRY", "0"), ("HANDLE_TELEMETRY", "off"), ("DO_NOT_TRACK", "1")],
)
async def test_env_turns_it_off(sent, monkeypatch, env, value):
    monkeypatch.setenv(env, value)
    telemetry.start()
    await fill()
    assert sent == []
    assert not (registry.CONFIG_DIR / "telemetry.json").exists()


def test_flag_turns_it_off(sent, monkeypatch):
    monkeypatch.setattr("sys.argv", ["handle-mcp", "--no-telemetry"])
    monkeypatch.setattr(server.mcp, "run", lambda transport: None)
    server.main()
    assert not telemetry.enabled() and sent == []


def test_flag_works_before_a_cli_command(monkeypatch):
    calls = []
    monkeypatch.setattr("sys.argv", ["handle-mcp", "--no-telemetry", "logout", "fake"])
    monkeypatch.setattr("handle_mcp.cli.run", lambda args: calls.append(args) or 0)
    with pytest.raises(SystemExit):
        server.main()
    assert calls == [["logout", "fake"]]


def test_the_notice_is_shown_once(sent, capsys):
    telemetry.start()
    telemetry.start()
    err = capsys.readouterr().err
    assert err.count("HANDLE_TELEMETRY=0") == 1 and "--no-telemetry" in err
    assert capsys.readouterr().out == ""  # stdout is JSON-RPC


async def test_a_failing_endpoint_never_breaks_a_tool(sent, monkeypatch):
    def boom(payload):
        raise OSError("network down")

    monkeypatch.setattr(telemetry, "_send", lambda *a, **k: boom(a))
    monkeypatch.setattr(telemetry, "_state_file", lambda: boom(None))
    result = await server.set_cart_quantities("fake", {"2": 1})
    telemetry._flush_all()
    assert result["results"][0]["ok"]


def test_post_swallows_network_errors(monkeypatch):
    def down(*args, **kwargs):
        raise OSError("no network")

    monkeypatch.setattr(telemetry.httpx, "post", down)
    telemetry._post({"type": "event"})  # does not raise


def test_post_has_a_short_timeout_and_a_configurable_url(monkeypatch):
    seen = {}
    monkeypatch.setattr(telemetry.httpx, "post", lambda url, **kw: seen.update(url=url, **kw))
    monkeypatch.setenv("HANDLE_TELEMETRY_URL", "https://umami.example.com/api/send")
    telemetry._post({"type": "event"})
    assert seen["url"] == "https://umami.example.com/api/send"
    assert seen["timeout"] <= 2


def test_no_website_id_sends_nothing(sent, monkeypatch):
    monkeypatch.delenv("HANDLE_TELEMETRY_WEBSITE")
    monkeypatch.setattr(telemetry, "WEBSITE", "")
    telemetry._send("active", {})
    assert sent == []
