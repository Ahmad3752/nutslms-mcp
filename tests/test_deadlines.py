"""Offline tests for the date miner — no LMS or network needed."""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moodle_mcp.deadlines import find_dates, upcoming  # noqa: E402

REF = dt.date(2026, 9, 20)


def dates(text, **kw):
    return {h.date: h.confidence for h in find_dates(text, ref=REF, **kw)}


def test_numeric_dayfirst():
    d = dates("Date of Activity: Section B: 22-09-2026, Section A and C: 24-09-2026")
    assert d["2026-09-22"] == "high"
    assert d["2026-09-24"] == "high"


def test_written_month():
    assert "2026-10-20" in dates("Submission Date : 20 OCTOBER 2026")
    assert "2026-10-20" in dates("Due: October 20, 2026")
    assert "2026-10-20" in dates("submit by 20th Oct")  # year inferred


def test_iso_format():
    assert "2026-11-03" in dates("Deadline 2026-11-03 at 23:59")


def test_confidence_tiers():
    assert dates("The report is due on 01-10-2026")["2026-10-01"] == "high"
    assert dates("Lecture slides for 01-10-2026")["2026-10-01"] == "medium"
    assert dates("Founded 01-10-2026 in passing")["2026-10-01"] == "low"


def test_ignores_impossible_dates():
    assert dates("version 45-99-2026") == {}


def test_day_first_vs_month_first():
    assert "2026-09-05" in dates("due 05-09-2026")
    assert "2026-05-09" in dates("due 05-09-2026", dayfirst=False)


def test_unambiguous_day_overrides_order():
    # 22 cannot be a month, so this is 22 September either way.
    assert "2026-09-22" in dates("due 22-09-2026", dayfirst=False)


def test_upcoming_filters_past_and_far():
    hits = find_dates(
        "due 01-01-2020 and due 22-09-2026 and due 01-01-2030", ref=REF)
    got = [h.date for h in upcoming(hits, ref=REF, horizon_days=60)]
    assert got == ["2026-09-22"]


def test_year_inference_picks_nearest():
    # No year given; December is closer looking back than forward from Sept 20.
    assert "2026-12-01" in dates("exam on 1 December")


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL  {name}  {e}")
    print(f"\n{'all passed' if not fails else f'{fails} failed'}")
    raise SystemExit(1 if fails else 0)
