"""The clones badge script in .github/badges/make.py."""

import importlib.util
import pathlib

_path = pathlib.Path(__file__).parents[1] / ".github" / "badges" / "make.py"
_spec = importlib.util.spec_from_file_location("badges_make", _path)
make = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make)


def _traffic(*days):
    return {"clones": [{"timestamp": f"{d}T00:00:00Z", "uniques": n} for d, n in days]}


def test_first_run_saves_every_day():
    history, badge = make.update(
        {"before": 0, "days": {}}, _traffic(("2026-11-07", 607), ("2026-11-08", 5))
    )
    assert history == {"before": 0, "days": {"2026-11-07": 607, "2026-11-08": 5}}
    assert badge["message"] == "612"


def test_api_overwrites_a_day_and_folds_older_days():
    saved = {"before": 100, "days": {"2026-10-20": 5, "2026-11-01": 7}}
    history, badge = make.update(saved, _traffic(("2026-10-26", 10), ("2026-11-01", 9)))
    assert history == {"before": 105, "days": {"2026-10-26": 10, "2026-11-01": 9}}
    assert badge["message"] == "124"


def test_no_clones_keeps_the_history():
    saved = {"before": 3, "days": {"2026-11-01": 7, "2026-11-02": 8}}
    history, badge = make.update(saved, _traffic())
    assert history == saved
    assert badge["message"] == "18"


def test_thousands_are_short():
    _, badge = make.update({"before": 1150, "days": {}}, _traffic())
    assert badge["message"] == "1.1k"
    _, badge = make.update({"before": 2000, "days": {}}, _traffic())
    assert badge["message"] == "2k"
