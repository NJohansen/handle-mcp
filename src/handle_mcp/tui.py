"""How `handle-mcp login` looks on a real terminal: a logo, a title bar, frames and arrow keys.

Only looks. The words, the checks and the answers live in cli.py and question.py. Everything
goes to stderr, like the rest of the command line. rich and prompt_toolkit are imported here and
only when a login runs, so the MCP server starts as fast as before. `fancy()` is False in a
pipe, with NO_COLOR, with TERM=dumb or in the old Windows console: then cli.py shows plain text.
"""

from __future__ import annotations

import os
import sys
from typing import Any

BLUE, YELLOW, INK = "#9ccbf3", "#f5e211", "#12161c"  # handlemcp.dk's sky and button
ACCENT, EDGE = "#2f7fc1", "#8a94a3"  # a deeper blue and a grey: readable on light and on dark
WIDTH = 62  # inside a frame
# The wordmark in small letters, as on handlemcp.dk. Ten pixel rows per letter; two pixel rows
# make one line of half blocks, so a pixel is about square.
LETTERS = {
    "h": ["X...", "X...", "X...", "XXX.", "X..X", "X..X", "X..X", "X..X", "....", "...."],
    "a": ["....", "....", "....", ".XX.", "...X", ".XXX", "X..X", ".XXX", "....", "...."],
    "n": ["....", "....", "....", "XXX.", "X..X", "X..X", "X..X", "X..X", "....", "...."],
    "d": ["...X", "...X", "...X", ".XXX", "X..X", "X..X", "X..X", ".XXX", "....", "...."],
    "l": ["X", "X", "X", "X", "X", "X", "X", "X", ".", "."],
    "e": ["....", "....", "....", ".XX.", "X..X", "XXXX", "X...", ".XXX", "....", "...."],
    "m": [".......", ".......", ".......", "XXX.XX.", "X..X..X", "X..X..X", "X..X..X"]
    + ["X..X..X", ".......", "......."],
    "c": ["....", "....", "....", ".XXX", "X...", "X...", "X...", ".XXX", "....", "...."],
    "p": ["....", "....", "....", "XXX.", "X..X", "X..X", "X..X", "XXX.", "X...", "X..."],
}
HALF = {"XX": "█", "X.": "▀", ".X": "▄", "..": " "}


def word(text: str) -> list[str]:
    """A word as five lines of half blocks, one column of air between letters."""
    pixels = [".".join(LETTERS[letter][row] for letter in text) for row in range(10)]
    return [
        "".join(HALF[a + b] for a, b in zip(pixels[row], pixels[row + 1], strict=True))
        for row in range(0, 10, 2)
    ]


def fancy() -> bool:
    env = os.environ
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        return False
    if "NO_COLOR" in env or env.get("TERM") == "dumb":
        return False
    return os.name != "nt" or "WT_SESSION" in env


def _console() -> Any:
    from rich.console import Console

    return Console(stderr=True, highlight=False)


def _show() -> Any:
    """rich's writer to stderr. stdout stays untouched: it belongs to JSON-RPC."""
    return _console().print


def logo_rows() -> list[str]:
    """The wordmark as rich markup: handle in blue, mcp in grey. Flat, no edge, no fade."""
    return [
        f"[{ACCENT}]{a}[/] [{EDGE}]{b}[/]" for a, b in zip(word("handle"), word("mcp"), strict=True)
    ]


def banner(store: str) -> None:
    """The logo, the title bar and one line about the store."""
    show, wide = _show(), _console().width >= 48
    show()
    for row in logo_rows() if wide else []:
        show(" " + row)
    show()
    show(f" [bold {INK} on {YELLOW}] ✦ HandleMCP :: Log ind :: Du betaler altid selv ✦ [/]")
    show()
    show(f" Lad os fylde kurven hos [bold {INK} on {BLUE}] {store} [/]")
    show()


def frame(title: str, body: str, dim: tuple[str, ...] = (), hint: str = "") -> None:
    """Text in a frame. A line that starts with a name in `dim` gets that name dimmed."""
    from rich.markup import escape
    from rich.panel import Panel

    lines = []
    for line in body.splitlines():
        name = next((n for n in dim if line.startswith(n)), None)
        text = escape(line)
        lines.append(f"[dim]{escape(name)}[/]{escape(line[len(name) :])}" if name else text)
    panel = Panel("\n".join(lines), title=f"[bold {ACCENT}]{escape(title)}[/]", title_align="left")
    panel.border_style, panel.width, panel.padding = EDGE, WIDTH + 4, (0, 1)
    show = _show()
    show(panel)
    if hint:
        show(f"  [dim]{escape(hint)}[/]")
    show()


def done(text: str) -> None:
    from rich.markup import escape

    _show()(f" [bold {ACCENT}]✔[/] {escape(text)}\n")


def failed(text: str) -> None:
    from rich.markup import escape

    _show()(f" [red]✘[/] {escape(text)}\n")


def edges(title: str) -> tuple[str, str, str]:
    """The top of a frame, left and right of its title, and its bottom: all WIDTH + 4 wide."""
    return "╭─ ", " " + "─" * (WIDTH - len(title) - 1) + "╮", "╰" + "─" * (WIDTH + 2) + "╯"


def _ask(title: str, body: Any, hint: str, height: int, keys: Any = None) -> Any:
    """One framed question on stderr. It is erased when answered; the caller prints the answer."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.output import create_output
    from prompt_toolkit.styles import Style

    def line(parts: list[tuple[str, str]]) -> Window:
        return Window(FormattedTextControl(parts), height=1)

    def side() -> Window:
        return Window(width=1, char="│", style="class:edge", height=height)

    keys = keys or KeyBindings()
    keys.add("c-c")(lambda event: event.app.exit(result=None))
    left, right, under = edges(title)
    top = [("class:edge", left), ("class:title", title), ("class:edge", right)]
    middle = VSplit([side(), Window(width=1), body, Window(width=1), side()])
    bottom = [("class:edge", under)]
    rows = [line(top), middle, line(bottom), line([("class:hint", "  " + hint)])]
    style = Style.from_dict(
        {"edge": EDGE, "title": f"bold {ACCENT}", "hint": EDGE, "on": f"bold {ACCENT}", "off": EDGE}
    )
    app: Any = Application(
        layout=Layout(HSplit(rows), focused_element=body),
        key_bindings=keys,
        style=style,
        erase_when_done=True,
        output=create_output(stdout=sys.stderr),
        color_depth=_depth(),
    )
    return app.run()


def _depth() -> Any:
    """Exact colors where the terminal says it has them; else what prompt_toolkit picks."""
    from prompt_toolkit.output import ColorDepth

    exact = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
    return ColorDepth.DEPTH_24_BIT if exact else None


def _typed(title: str, hint: str, secret: bool) -> str:
    from prompt_toolkit.widgets import TextArea

    def accept(buffer: Any) -> bool:
        from prompt_toolkit.application import get_app

        get_app().exit(result=buffer.text)
        return True

    box = TextArea(multiline=False, password=secret, height=1, width=WIDTH, accept_handler=accept)
    answer = (_ask(title, box, hint, 1) or "").strip()
    frame(title, "•" * 8 if secret and answer else answer)  # never the real length
    return answer


def text(title: str, hint: str = "") -> str:
    return _typed(title, hint, secret=False)


def password(title: str, hint: str = "") -> str:
    return _typed(title, hint, secret=True)


def choose(title: str, choices: list[str], hint: str = "") -> str:
    """Arrow keys. The first choice is where the pointer starts, and what Ctrl-C gives."""
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    at, keys = [0], KeyBindings()

    def move(step: int) -> Any:
        def handler(_event: Any) -> None:
            at[0] = (at[0] + step) % len(choices)

        return handler

    for key in ("up", "k"):
        keys.add(key)(move(-1))
    for key in ("down", "j", "tab"):
        keys.add(key)(move(1))
    keys.add("enter")(lambda event: event.app.exit(result=choices[at[0]]))

    def rows() -> list[tuple[str, str]]:
        out = []
        for number, choice in enumerate(choices):
            on = number == at[0]
            end = "" if number == len(choices) - 1 else "\n"
            out.append(
                ("class:on" if on else "class:off", f"{'› ●' if on else '  ○'} {choice}{end}")
            )
        return out

    body = Window(FormattedTextControl(rows, focusable=True, show_cursor=False), width=WIDTH)
    picked = _ask(title, body, hint, len(choices), keys) or choices[0]
    frame(title, picked)
    return picked
