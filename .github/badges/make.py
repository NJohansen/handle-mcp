"""Write clones.json, the shields.io endpoint for the README clones badge.

Reads traffic.json (GitHub API answer) and clones-history.json.
GitHub keeps traffic for 14 days only. The history keeps the days the API still
shows, plus one sum for all older days, so no daily numbers older than 14 days are public.
"""

import json
import pathlib


def update(saved: dict, traffic: dict) -> tuple[dict, dict]:
    """Merge one traffic answer into the history. Returns (history, badge)."""
    days = dict(saved["days"])
    before = saved["before"]
    fresh = {d["timestamp"][:10]: d["uniques"] for d in traffic["clones"]}
    if fresh:
        days.update(fresh)
        first = min(fresh)
        before += sum(n for day, n in days.items() if day < first)
        days = {day: n for day, n in days.items() if day >= first}
    days = dict(sorted(days.items()))
    total = before + sum(days.values())
    message = f"{total / 1000:.1f}k".replace(".0k", "k") if total >= 1000 else str(total)
    badge = {"schemaVersion": 1, "label": "clones", "message": message, "color": "brightgreen"}
    return {"before": before, "days": days}, badge


def main() -> None:
    history = pathlib.Path("clones-history.json")
    saved = json.loads(history.read_text()) if history.exists() else {"before": 0, "days": {}}
    traffic = json.loads(pathlib.Path("traffic.json").read_text())
    new, badge = update(saved, traffic)
    history.write_text(json.dumps(new, indent=1) + "\n")
    pathlib.Path("clones.json").write_text(json.dumps(badge) + "\n")
    print(f"{badge['message']} clones")


if __name__ == "__main__":
    main()
