# 0015: The login has a look

`handle-mcp login <store>` on a real terminal shows a logo, a title bar, framed questions and a choice made with the arrow keys. The look lives in `tui.py`. The words, the checks and the answers stay in `cli.py` and `question.py`.

It adds two dependencies: `rich` for the frames and colors, `prompt-toolkit` for the questions.

The rules it keeps:

- **stderr only.** stdout is JSON-RPC, also during a login.
- **Plain text where the look cannot show.** In a pipe, with `NO_COLOR`, with `TERM=dumb` and in the old Windows console, the login is the text it was before. `tui.fancy()` decides.
- **Loaded only for a login.** `tui.py` imports both libraries inside its functions, so the MCP server starts as fast as before and never loads them.
- **The same words.** The question about usage counts is `question.body()` in a frame: the look can never show other words than the plain text ([ADR 0014](0014-usage-counts-ask-first.md)).
- **No is where the pointer starts.** A blind Enter is a no, and so is Ctrl-C. A yes takes a key press.
- **A password is never shown.** Not while it is typed, and after it only as eight dots, whatever its length.

## Why

The login is the first thing a new user sees, and the only place handle-mcp talks to a human directly. It asks for a password and for a yes or no to counting. A screen that looks cared for is easier to trust and easier to read: one question at a time, each in its own frame.

Two well-known libraries are less code to own than escape codes and key handling written by hand, on three operating systems.

## Consequences

- Everyone who installs handle-mcp gets `rich` and `prompt-toolkit` and what they need, also those who only run the server. Dependabot watches them like the rest.
- The logo is drawn with half blocks in exact colors. A terminal without them still gets the frames; a narrow one (under 80 columns) gets no logo.
- `tests/test_tui.py` types into the real questions through a pipe. How it looks in a given terminal is checked by eye.
