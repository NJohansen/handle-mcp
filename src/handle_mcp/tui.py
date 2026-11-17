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

GREEN, YELLOW, INK = "#8bd86a", "#f5e211", "#12161c"  # handlemcp.dk's logo and button
ACCENT, EDGE = "#2f9440", "#8a94a3"  # a deeper green and a grey: readable on light and on dark
WIDTH = 62  # inside a frame
# Block letters, five units high. A unit is two columns wide and one line high: about square.
LETTERS = {
    "H": ["X.X", "X.X", "XXX", "X.X", "X.X"],
    "A": ["XXX", "X.X", "XXX", "X.X", "X.X"],
    "N": ["X..X", "XX.X", "X.XX", "X..X", "X..X"],
    "D": ["XX.", "X.X", "X.X", "X.X", "XX."],
    "L": ["X..", "X..", "X..", "X..", "XXX"],
    "E": ["XXX", "X..", "XX.", "X..", "XXX"],
    "M": ["X...X", "XX.XX", "X.X.X", "X...X", "X...X"],
    "C": ["XXX", "X..", "X..", "X..", "XXX"],
    "P": ["XXX", "X.X", "XXX", "X..", "X.."],
}
# Per word: the fade of its letters from top to bottom, and the one color of its depth.
HANDLE = (GREEN, ACCENT, "#1f6e34")
MCP = ("#aeb6c2", "#6f7a88", "#444c57")


AIR = 2  # columns between letters: one for the depth, one empty


def pixels(text: str) -> list[str]:
    """A word as ten rows of pixels (half lines): every unit is 2 x 2, AIR columns between."""
    rows = [
        ("." * AIR).join(LETTERS[c][row].replace("X", "XX").replace(".", "..") for c in text)
        for row in range(5)
    ]
    return [row for row in rows for _ in (0, 1)]


def _fade(top: str, bottom: str, step: int, steps: int) -> str:
    a = [int(top[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(bottom[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(x + (y - x) * step / steps):02x}" for x, y in zip(a, b, strict=True)
    )


def painted(text: str, colors: tuple[str, str, str]) -> list[list[str | None]]:
    """A word as 12 rows of colors: the letters fade downwards, and a copy one pixel down and
    to the right, in one darker color, gives depth. Solid areas only: no lines, no outline."""
    top, bottom, depth = colors
    rows = pixels(text)
    grid: list[list[str | None]] = [[None] * (len(rows[0]) + 1) for _ in range(12)]
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            if pixel == "X":
                grid[y + 1][x + 1] = depth
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            if pixel == "X":
                grid[y][x] = _fade(top, bottom, y, 9)
    return grid


def logo_rows() -> list[str]:
    """The logo as rich markup, six lines: HANDLE in green, MCP in grey, both with depth.
    A cell is a half block: its upper pixel is the text color, its lower pixel the background."""
    left, right = painted("HANDLE", HANDLE), painted("MCP", MCP)
    out = []
    for y in range(0, 12, 2):
        line = ""
        for up, down in zip(
            left[y] + [None] * 3 + right[y], left[y + 1] + [None] * 3 + right[y + 1], strict=True
        ):
            if up and down:
                line += f"[{up} on {down}]▀[/]" if up != down else f"[{up}]█[/]"
            else:
                line += f"[{up}]▀[/]" if up else f"[{down}]▄[/]" if down else " "
        out.append(line)
    return out


def color() -> bool:
    """Bold and dim only where the terminal shows them: never in a pipe, a dumb terminal,
    with NO_COLOR, or in the old Windows console."""
    env = os.environ
    if not sys.stderr.isatty() or "NO_COLOR" in env or env.get("TERM") == "dumb":
        return False
    return os.name != "nt" or "WT_SESSION" in env


def fancy() -> bool:
    return sys.stdin.isatty() and color()


def _console() -> Any:
    from rich.console import Console

    return Console(stderr=True, highlight=False)


def _show() -> Any:
    """rich's writer to stderr. stdout stays untouched: it belongs to JSON-RPC."""
    return _console().print


def banner(store: str = "") -> None:
    """The logo, the title bar and, for one store, a line about it."""
    show, wide = _show(), _console().width >= 80
    show()
    for row in logo_rows() if wide else []:
        show(" " + row)
    show()
    show(f" [bold {INK} on {YELLOW}] ✦ HandleMCP :: Log ind :: Du betaler altid selv ✦ [/]")
    show()
    if store:
        show(f" Lad os fylde kurven hos [bold {INK} on {GREEN}] {store} [/]")
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


def _result(mark: str, text: str) -> None:
    """One line with a mark. A long line wraps under its own first word, not under the mark."""
    from rich.markup import escape
    from rich.table import Table

    row = Table.grid(padding=(0, 1))
    row.add_row(" " + mark, escape(text))
    show = _show()
    show(row)
    show()


def done(text: str) -> None:
    _result(f"[bold {ACCENT}]✔[/]", text)


def failed(text: str) -> None:
    _result("[red]✘[/]", text)


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


def choose(title: str, choices: list[str], hint: str = "", many: bool = False) -> Any:
    """Arrow keys. One answer: the first choice is where the pointer starts, and what Ctrl-C
    gives. With `many`: space marks, Enter gives the marked ones (none marked: the one the pointer is
    on), and Ctrl-C gives none."""
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    at, marked, keys = [0], set(), KeyBindings()

    def move(step: int) -> Any:
        def handler(_event: Any) -> None:
            at[0] = (at[0] + step) % len(choices)

        return handler

    for key in ("up", "k"):
        keys.add(key)(move(-1))
    for key in ("down", "j", "tab"):
        keys.add(key)(move(1))
    if many:
        keys.add("space")(lambda _event: marked.symmetric_difference_update({at[0]}))
        keys.add("enter")(lambda event: event.app.exit(result=sorted(marked or {at[0]})))
    else:
        keys.add("enter")(lambda event: event.app.exit(result=[at[0]]))

    def rows() -> list[tuple[str, str]]:
        out = []
        for number, choice in enumerate(choices):
            here = number == at[0]
            on = number in marked if many else here
            end = "" if number == len(choices) - 1 else "\n"
            line = f"{'›' if here else ' '} {'●' if on else '○'} {choice}{end}"
            out.append(("class:on" if on or here else "class:off", line))
        return out

    body = Window(FormattedTextControl(rows, focusable=True, show_cursor=False), width=WIDTH)
    answer = _ask(title, body, hint, len(choices), keys)
    picked = [choices[n] for n in (answer if answer is not None else [] if many else [0])]
    frame(title, ", ".join(picked) or "Ingen")
    return picked if many else picked[0]
