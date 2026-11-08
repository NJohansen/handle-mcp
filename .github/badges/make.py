"""Write clones.json, the shields.io endpoint for the README clones badge.

Reads traffic.json (GitHub API answer) and clones-history.json.
GitHub keeps traffic for 14 days only. The history keeps the days the API still
shows, plus one sum for all older days, so no daily numbers older than 14 days are public.
"""

import json
import pathlib

history = pathlib.Path("clones-history.json")
saved = json.loads(history.read_text()) if history.exists() else {"before": 0, "days": {}}
fresh = {
    d["timestamp"][:10]: d["uniques"]
    for d in json.loads(pathlib.Path("traffic.json").read_text())["clones"]
}
days = {**saved["days"], **fresh}
first = min(fresh, default=max(days, default=""))
before = saved["before"] + sum(n for day, n in days.items() if day < first)
days = {day: n for day, n in sorted(days.items()) if day >= first}
history.write_text(json.dumps({"before": before, "days": days}, indent=1) + "\n")
total = before + sum(days.values())
message = f"{total / 1000:.1f}k".replace(".0k", "k") if total >= 1000 else str(total)
badge = {"schemaVersion": 1, "label": "clones", "message": message, "color": "brightgreen"}
pathlib.Path("clones.json").write_text(json.dumps(badge) + "\n")
print(f"{total} clones")
