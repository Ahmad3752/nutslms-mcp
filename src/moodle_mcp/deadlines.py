"""Find dates that look like obligations inside free text.

Where instructors publish coursework as documents instead of Moodle activities,
the only machine-readable signal is a date written in prose. We locate dates in
the formats that actually show up in course handouts, then score each by the
words around it so that "Date of Activity: 22-09-2026" outranks a citation year
in a reading list.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, asdict

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# Words that suggest a date is something you must act on.
STRONG = re.compile(
    r"\b(due|deadline|submit|submission|last date|cut ?off|closes?|closing|"
    r"exam|quiz|test|viva|presentation|present|defend|assessment|assessed|"
    r"graded|grading|activity|assignment|project|report|midterm|final|"
    r"deliverable|hand ?in|turn ?in|conduct(?:ed)?|scheduled|will be held)\b",
    re.I)
WEAK = re.compile(r"\b(class|lecture|session|week|lab|workshop|seminar)\b", re.I)

_D = r"(\d{1,2})"
_Y = r"(\d{4}|\d{2})"
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"

PATTERNS = [
    # 2026-09-22
    (re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"), "ymd"),
    # 22-09-2026 / 22/09/26   (day-first; see dayfirst flag)
    (re.compile(rf"\b{_D}[-/.]{_D}[-/.]{_Y}\b"), "dmy"),
    # 22 September 2026 / 22nd Sept
    (re.compile(rf"\b{_D}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MON}\.?(?:\s*,?\s*(\d{{4}}))?\b", re.I), "dMy"),
    # September 22, 2026 / Sept 22
    (re.compile(rf"\b{_MON}\s+{_D}(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?\b", re.I), "Mdy"),
]


@dataclass
class Hit:
    date: str
    confidence: str
    matched: str
    context: str

    def dict(self) -> dict:
        return asdict(self)


def _mk(y: int | None, m: int, d: int, ref: dt.date) -> dt.date | None:
    if not (1 <= m <= 12):
        return None
    if y is None:
        # No year written. Choose the nearest plausible one around `ref`.
        best = None
        for cand in (ref.year, ref.year + 1, ref.year - 1):
            try:
                c = dt.date(cand, m, d)
            except ValueError:
                continue
            if best is None or abs((c - ref).days) < abs((best - ref).days):
                best = c
        return best
    if y < 100:
        y += 2000
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str, ref: dt.date | None = None,
               dayfirst: bool = True) -> list[Hit]:
    """Extract dated obligations, most confident and soonest first."""
    ref = ref or dt.date.today()
    hits: dict[str, Hit] = {}

    for rx, kind in PATTERNS:
        for m in rx.finditer(text):
            g = m.groups()
            date = None
            if kind == "ymd":
                date = _mk(int(g[0]), int(g[1]), int(g[2]), ref)
            elif kind == "dmy":
                a, b = int(g[0]), int(g[1])
                if not dayfirst or a > 12:
                    a, b = (b, a) if a > 12 else (a, b)
                    date = _mk(int(g[2]), b, a, ref) if a > 12 else _mk(int(g[2]), a, b, ref)
                else:
                    date = _mk(int(g[2]), b, a, ref)
            elif kind == "dMy":
                mon = MONTHS.get(g[1][:3].lower())
                if mon:
                    date = _mk(int(g[2]) if g[2] else None, mon, int(g[0]), ref)
            elif kind == "Mdy":
                mon = MONTHS.get(g[0][:3].lower())
                if mon:
                    date = _mk(int(g[2]) if g[2] else None, mon, int(g[1]), ref)
            if not date:
                continue

            lo, hi = max(0, m.start() - 130), min(len(text), m.end() + 130)
            ctx = re.sub(r"\s+", " ", text[lo:hi]).strip()
            if STRONG.search(ctx):
                conf = "high"
            elif WEAK.search(ctx):
                conf = "medium"
            else:
                conf = "low"

            key = date.isoformat()
            prior = hits.get(key)
            rank = {"high": 3, "medium": 2, "low": 1}
            if prior is None or rank[conf] > rank[prior.confidence]:
                hits[key] = Hit(key, conf, m.group(0), ctx)

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(hits.values(), key=lambda h: (order[h.confidence], h.date))


def upcoming(hits: list[Hit], ref: dt.date | None = None,
             horizon_days: int = 120) -> list[Hit]:
    """Keep only dates that are still ahead and not absurdly far out."""
    ref = ref or dt.date.today()
    out = []
    for h in hits:
        d = dt.date.fromisoformat(h.date)
        if 0 <= (d - ref).days <= horizon_days:
            out.append(h)
    return sorted(out, key=lambda h: h.date)
