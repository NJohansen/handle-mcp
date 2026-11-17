"""The real frames and questions of tui.py, with keys from a pipe. No terminal, no network."""

from __future__ import annotations

import os

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from handle_mcp import question, tui

DOWN, UP, ENTER, CTRL_C = "\x1b[B", "\x1b[A", "\r", "\x03"


@pytest.fixture
def keys(monkeypatch):
    """Type into the open question. The answer frame is recorded, not drawn."""
    frames: list[tuple[str, str]] = []
    monkeypatch.setattr(tui, "frame", lambda title, body, **_: frames.append((title, body)))
    if os.name == "nt":  # a test run has no Windows console to draw on: the keys still run
        monkeypatch.setattr("prompt_toolkit.output.create_output", lambda **_: DummyOutput())
    with create_pipe_input() as pipe, create_app_session(input=pipe):
        pipe.frames = frames
        yield pipe


@pytest.mark.parametrize(
    ("typed", "picked"),
    [
        (ENTER, "Nej"),  # a blind Enter is a no
        (DOWN + ENTER, "Ja"),
        ("j" + ENTER, "Ja"),
        (DOWN + DOWN + ENTER, "Nej"),  # past the end: back to the top
        (UP + ENTER, "Ja"),
        (DOWN + CTRL_C, "Nej"),  # Ctrl-C is the first choice, wherever the pointer is
    ],
)
def test_choose_moves_with_the_keys_and_ctrl_c_is_the_first_choice(keys, typed, picked):
    keys.send_text(typed)
    assert tui.choose("Tæl med?", ["Nej", "Ja"]) == picked
    assert keys.frames == [("Tæl med?", picked)]


@pytest.mark.parametrize(
    ("typed", "picked"),
    [
        (ENTER + ENTER, ["nemlig"]),  # Enter marks and moves to Videre; Enter again goes on
        (DOWN + ENTER + ENTER, ["bilkatogo"]),
        (ENTER + UP + ENTER + ENTER, ["nemlig", "rema1000"]),  # up from Videre: the last store
        (" " + DOWN + DOWN + " " + DOWN + ENTER, ["nemlig", "rema1000"]),  # space marks in place
        (" " + " " + DOWN + " " + DOWN + DOWN + ENTER, ["bilkatogo"]),  # twice takes the mark off
        (UP + ENTER + UP + " " + DOWN + ENTER, ["rema1000"]),  # Videre waits for a store
        (" " + ENTER + ENTER, ["nemlig"]),  # Enter on a marked store keeps the mark
        (ENTER + DOWN + " " + UP + ENTER + CTRL_C, []),  # space took it off: Videre waits
        (" " + DOWN + " " + CTRL_C, []),  # Ctrl-C picks nothing
    ],
)
def test_choose_many_marks_with_space(keys, typed, picked):
    keys.send_text(typed)
    stores = ["nemlig", "bilkatogo", "rema1000"]
    assert tui.choose("Hvor handler du?", stores, many=True) == picked
    assert keys.frames == [("Hvor handler du?", ", ".join(picked) or "Ingen")]


def test_text_gives_what_was_typed_and_ctrl_c_gives_nothing(keys):
    keys.send_text("  a@example.com " + ENTER)
    assert tui.text("Email") == "a@example.com"
    keys.send_text("a@exa" + CTRL_C)
    assert tui.text("Email") == ""


def test_a_password_is_never_shown_and_never_its_real_length(keys, capsys):
    keys.send_text("hemmelig-og-langt" + ENTER)
    assert tui.password("Kodeord") == "hemmelig-og-langt"
    assert keys.frames == [("Kodeord", "•" * 8)]
    out = capsys.readouterr()
    assert "hemmelig" not in out.err and out.out == ""


def test_the_banner_and_a_frame_go_to_stderr_only(capsys):
    tui.banner("nemlig")
    tui.frame(question.TITLE, question.body(), dim=tuple(n for n, _ in question.FACTS))
    tui.done("Logget ind.")
    tui.failed("Login blev ikke gemt.")
    out = capsys.readouterr()
    assert out.out == ""  # stdout belongs to JSON-RPC
    for words in ("HandleMCP", "nemlig", question.TITLE, "Slå fra", "✔ Logget ind.", "✘ Login"):
        assert words in out.err
    for line in question.body().splitlines():  # every word of the question is in the frame
        assert line in out.err


def test_the_body_is_the_question_without_its_title_and_indent():
    plain = [line.strip() for line in question.QUESTION.splitlines()[3:]]
    assert [line.strip() for line in question.body().splitlines()] == plain
