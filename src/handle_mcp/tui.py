"""How `handle-mcp login` looks on a real terminal: a logo, a title bar, frames and arrow keys.

Only looks. The words, the checks and the answers live in cli.py and telemetry.py. Everything
goes to stderr, like the rest of the command line. rich and questionary are imported here and
only when a login runs, so the MCP server starts as fast as before. `fancy()` is False in a
pipe, with NO_COLOR, with TERM=dumb or in the old Windows console: then cli.py prints plain text.
"""

from __future__ import annotations

import os
import sys
from typing import Any

BLUE, YELLOW, INK = "#9ccbf3", "#f5e211", "#12161c"  # handlemcp.dk's sky and button
LETTERS = {
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "C": [" ████", "█    ", "█    ", "█    ", " ████"],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
}


def fancy() -> bool:
    env = os.environ
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        return False
    if "NO_COLOR" in env or env.get("TERM") == "dumb":
        return False
    return os.name != "nt" or "WT_SESSION" in env


def _show() -> Any:
    """rich's writer to stderr. stdout stays untouched: it belongs to JSON-RPC."""
    from rich.console import Console

    return Console(stderr=True, highlight=False).print


def _word(word: str, row: int) -> str:
    return " ".join(LETTERS[letter][row] for letter in word)


def banner(store: str) -> None:
    """The logo (Handle in blue, MCP in yellow), the title bar and one line about the store."""
    show = _show()
    show()
    for row in range(5):
        show(f" [{BLUE}]{_word('HANDLE', row)}[/]  [{YELLOW}]{_word('MCP', row)}[/]")
    show()
    show(f" [bold {INK} on {YELLOW}] HandleMCP :: Log ind :: Du betaler altid selv [/]")
    show()
    show(f" Brug den email og det kodeord, du bruger hos [bold {INK} on {BLUE}] {store} [/]")
    show()


def frame(title: str, body: str, dim: tuple[str, ...] = ()) -> None:
    """Text in a frame. A line that starts with a name in `dim` gets that name dimmed."""
    from rich.markup import escape
    from rich.panel import Panel

    lines = []
    for line in body.splitlines():
        name = next((n for n in dim if line.startswith(n)), None)
        text = escape(line)
        lines.append(f"[dim]{escape(name)}[/]{escape(line[len(name) :])}" if name else text)
    panel = Panel("\n".join(lines), title=f"[{BLUE}]{escape(title)}[/]", title_align="left")
    panel.border_style, panel.expand, panel.padding = "dim", False, (0, 1)
    show = _show()
    show()
    show(panel)


def done(text: str) -> None:
    from rich.markup import escape

    _show()(f" [green]✔[/] {escape(text)}")


def failed(text: str) -> None:
    from rich.markup import escape

    _show()(f" [red]✘[/] {escape(text)}")


def _prompt(kind: str, message: str, **more: Any) -> Any:
    import questionary
    from prompt_toolkit.output import create_output

    style = questionary.Style(
        [
            ("qmark", f"fg:{YELLOW} bold"),
            ("question", "bold"),
            ("pointer", f"fg:{YELLOW} bold"),
            ("highlighted", f"fg:{BLUE} bold"),
            ("answer", f"fg:{BLUE}"),
        ]
    )
    ask = getattr(questionary, kind)
    return ask(message, qmark=" ?", style=style, output=create_output(stdout=sys.stderr), **more)


def text(message: str) -> str:
    return (_prompt("text", message).ask() or "").strip()


def password(message: str) -> str:
    return _prompt("password", message).ask() or ""


def choose(message: str, choices: list[str]) -> str:
    """Arrow keys. The first choice is where the pointer starts, and what Ctrl-C gives."""
    hint = "(pil op/ned, Enter)"
    picked = _prompt("select", message, choices=choices, instruction=hint, pointer="›").ask()
    return picked or choices[0]
