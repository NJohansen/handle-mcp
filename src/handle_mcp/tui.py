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
ACCENT, EDGE = "#3d8fd1", "#8a94a3"  # small text and frames: readable on light and on dark
WIDTH = 62  # inside a frame
# Block letters with a shadow edge, six rows each: HANDLE and MCP.
LOGO = """\
██╗  ██╗ █████╗ ███╗   ██╗██████╗ ██╗     ███████╗███╗   ███╗ ██████╗██████╗
██║  ██║██╔══██╗████╗  ██║██╔══██╗██║     ██╔════╝████╗ ████║██╔════╝██╔══██╗
███████║███████║██╔██╗ ██║██║  ██║██║     █████╗  ██╔████╔██║██║     ██████╔╝
██╔══██║██╔══██║██║╚██╗██║██║  ██║██║     ██╔══╝  ██║╚██╔╝██║██║     ██╔═══╝
██║  ██║██║  ██║██║ ╚████║██████╔╝███████╗███████╗██║ ╚═╝ ██║╚██████╗██║
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚══════╝╚═╝     ╚═╝ ╚═════╝╚═╝""".splitlines()


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


def _mix(step: int, steps: int) -> str:
    """A color on the way from the sky blue to the button yellow."""
    a, b = (
        (int(BLUE[i : i + 2], 16) for i in (1, 3, 5)),
        (int(YELLOW[i : i + 2], 16) for i in (1, 3, 5)),
    )
    return "#" + "".join(
        f"{round(x + (y - x) * step / steps):02x}" for x, y in zip(a, b, strict=True)
    )


def logo_rows() -> list[str]:
    """The logo as rich markup: the blocks fade from blue to yellow, the shadow edge is one blue."""
    rows = []
    for number, line in enumerate(LOGO):
        fill, out, run, block = _mix(min(number, 4), 4), "", "", None
        for char in line + "\0":  # the end mark closes the last run
            kind = None if char == "\0" else char == "█"
            if kind != block and run:
                out += f"[{fill if block else ACCENT}]{run}[/]"
                run = ""
            block, run = kind, run + char if char != "\0" else ""
        rows.append(out)
    return rows


def banner(store: str) -> None:
    """The logo, the title bar and one line about the store."""
    show, wide = _show(), _console().width > max(map(len, LOGO)) + 2
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

    _show()(f" [green]✔[/] {escape(text)}\n")


def failed(text: str) -> None:
    from rich.markup import escape

    _show()(f" [red]✘[/] {escape(text)}\n")


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
    top = [("class:edge", "┌ "), ("class:title", title)]
    top.append(("class:edge", " " + "─" * (WIDTH - len(title) - 1) + "┐"))
    middle = VSplit([side(), Window(width=1), body, Window(width=1), side()])
    bottom = [("class:edge", "└" + "─" * (WIDTH + 2) + "┘")]
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
    )
    return app.run()


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
            out.append(("class:on" if on else "class:off", f"{'› ●' if on else '  ○'} {choice}\n"))
        return out

    body = Window(FormattedTextControl(rows, focusable=True, show_cursor=False), width=WIDTH)
    picked = _ask(title, body, hint, len(choices), keys) or choices[0]
    frame(title, picked)
    return picked
