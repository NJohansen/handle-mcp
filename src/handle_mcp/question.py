"""The question handle-mcp asks before it counts anything (docs/adr/0014).

Who asks, why, what is counted, where it goes and how to say no. Short on purpose: every event
and field is one link away, on handlemcp.dk/privatliv and in the README. cli.py shows it after
a login and for `handle-mcp telemetry on`.
"""

from __future__ import annotations

TITLE = "Anonym tælling i handle-mcp"
WHY = """\
  Hej, Niclas Johansen her. Jeg har bygget handle-mcp.
  Må jeg tælle anonymt, når den fylder en kurv?

  handle-mcp er lavet til dig, der vil handle nemmere.
  Tallene hjælper med at holde den gratis. De kan også vise
  butikkerne, at den giver mening for dem."""
FACTS = (
    ("Tæller", "butik, antal varer, afrundet beløb pr. fyldt kurv"),
    ("Dagligt", "start, første værktøj, login, version, styresystem"),
    ("Aldrig", "navn, adresse, varer"),
    ("Deles", "kun samlede tal"),
    ("Ligger hos", "Umami (statistik uden cookies, USA)"),
    ("IP-adresse", "ses af Umami, som af ethvert website du besøger"),
    ("Slå fra", "handle-mcp telemetry off"),
    ("Detaljer", "handlemcp.dk/privatliv"),
)


def question(color: bool = False) -> str:
    """The question as text. With color: a bold title and dim row names, nothing else."""
    bold, dim, end = ("\033[1m", "\033[2m", "\033[0m") if color else ("", "", "")
    rows = "\n".join(f"  {dim}{name:<11}{end} {fact}" for name, fact in FACTS)
    return f"\n  {bold}{TITLE}{end}\n\n{WHY}\n\n{rows}\n"


QUESTION = question()
