#!/usr/bin/env python3
"""Turn a dumped day with clock times into every calendar interval.

Works for any person, any language they wrote the dump in. The model must
not pick one 'focus' block — this parser is the grid.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

HOUR = re.compile(
    r"\b(\d{1,2})(?:[:hH](\d{2}))?\s*(h|hrs?|horas?)?(?:\s*(da\s+(manh[ãa]|tarde|noite)|am|pm))?\b",
    re.I,
)
RANGE = re.compile(
    r"(?:das?|entre|de|from|between)\s+"
    r"(\d{1,2})(?:[:hH:](\d{2}))?\s*(?:h|hrs?)?\s*(am|pm)?"
    r"\s*(?:[-–]|às?|as|ate|até|e|and|to|pra|para)\s*"
    r"(?:umas?\s+)?"
    r"(\d{1,2})(?:[:hH:](\d{2}))?\s*(?:h|hrs?|horas?)?\s*(am|pm)?"
    r"(?:\s*(da\s+(manh[ãa]|tarde|noite)))?",
    re.I,
)
UNTIL = re.compile(
    r"\b(?:at[eé]|until|till)\s+(?:umas?\s+)?(\d{1,2})(?:[:hH](\d{2}))?\s*(?:h|hrs?)?(?:\s*(da\s+(tarde|noite)|pm))?",
    re.I,
)
STOP = {
    "the", "and", "then", "have", "from", "with", "that", "this", "hoje",
    "amanha", "amanhã", "depois", "então", "entao", "também", "tambem",
    "vou", "ter", "uma", "umas", "para", "pra", "até", "ate", "das", "dos",
    "nao", "não", "consigo", "fazer", "muita", "coisa", "fora", "isso",
    "tomorrow", "today", "after", "before", "probably", "also", "just",
    "between", "until",
}


def _hour(h: int, m: int, period: str, prev: datetime | None = None) -> tuple[int, int]:
    period = (period or "").lower()
    if "pm" in period or "tarde" in period or "noite" in period:
        if h < 12:
            h += 12
    elif ("am" in period or "manh" in period) and h == 12:
        h = 0
    if prev is not None and h < prev.hour and h <= 8 and prev.hour >= 11:
        h += 12
    return min(h, 23), min(m, 59)


def _at(day: datetime, h: int, m: int, period: str = "", prev: datetime | None = None) -> datetime:
    h, m = _hour(h, m, period, prev)
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def _label(prefix: str) -> str:
    """Words glued to this clock, not a previous interval in the lookback."""
    after = re.split(r"\d+(?:[:hH]\d{2})?\s*(?:h|hrs?)?", prefix or "")[-1]
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", after)
    keep = [t for t in tokens if t.casefold() not in STOP]
    if not keep:
        tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", prefix or "")
        keep = [t for t in tokens if t.casefold() not in STOP]
    if not keep:
        return "Busy"
    return " ".join(keep[-2:]).strip().capitalize()


def _covered(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= index < b for a, b in spans)


def _period(*parts: str | None) -> str:
    return " ".join(p for p in parts if p)


DAY_NAMES = (
    (r"segunda(?:s|-feiras?)?", "MO"),
    (r"ter[cç]a(?:s|-feiras?)?", "TU"),
    (r"quarta(?:s|-feiras?)?", "WE"),
    (r"quinta(?:s|-feiras?)?", "TH"),
    (r"sexta(?:s|-feiras?)?", "FR"),
    (r"s[aá]bado(?:s)?", "SA"),
    (r"domingo(?:s)?", "SU"),
    (r"mondays?", "MO"),
    (r"tuesdays?", "TU"),
    (r"wednesdays?", "WE"),
    (r"thursdays?", "TH"),
    (r"fridays?", "FR"),
    (r"saturdays?", "SA"),
    (r"sundays?", "SU"),
)
_PY_DAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def weekday_codes(text: str) -> list[str]:
    seen: list[str] = []
    blob = text or ""
    for pattern, code in DAY_NAMES:
        if re.search(rf"\b{pattern}\b", blob, re.I) and code not in seen:
            seen.append(code)
    return seen


def wants_weekly(text: str, codes: list[str]) -> bool:
    blob = text or ""
    if re.search(r"\b(tod[oa]s?|every|each)\b", blob, re.I):
        return True
    if len(codes) >= 2:
        return True
    if re.search(
        r"\b(?:segundas|ter[cç]as|quartas|quintas|sextas|s[aá]bados|domingos|"
        r"mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays)\b",
        blob,
        re.I,
    ):
        return True
    return False


def recurrence_for(text: str) -> list[str]:
    codes = weekday_codes(text)
    if not wants_weekly(text, codes):
        return []
    if codes:
        return [f"RRULE:FREQ=WEEKLY;BYDAY={','.join(codes)}"]
    if re.search(r"\b(semanas?|weeks?)\b", text or "", re.I):
        return ["RRULE:FREQ=WEEKLY"]
    return []


def snap_week(start: datetime, end: datetime, codes: list[str]) -> tuple[datetime, datetime]:
    if not codes:
        return start, end
    want = [_PY_DAY[c] for c in codes if c in _PY_DAY]
    if not want:
        return start, end
    length = end - start
    base = start.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(8):
        cand = base + timedelta(days=i)
        if cand.weekday() in want:
            new_start = start.replace(year=cand.year, month=cand.month, day=cand.day)
            return new_start, new_start + length
    return start, end


_RECURRENCE_BREAK = re.compile(
    r"\s+(?:e|and)\s+(?=(?:(?:a|o|the)\s+)?[A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]{3,}){0,3}\s+(?:tod[oa]s?|every|each)\b)",
    re.I,
)


def _recurrence_window(text: str, start: int, end: int) -> str:
    """Keep a routine's weekday with its own interval, not the next routine."""
    left = max(0, start - 60)
    around = text[left : min(len(text), end + 40)]
    current_start, current_end = start - left, end - left
    before, after = 0, len(around)
    for boundary in _RECURRENCE_BREAK.finditer(around):
        if boundary.end() <= current_start:
            before = boundary.end()
        elif boundary.end() > current_end:
            after = boundary.start()
            break
    return around[before:after]


def parse(text: str, day: datetime) -> list[dict]:
    """Named intervals in order. Lone starts close at the next clock or +60m."""
    text = text or ""
    day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    hits: list[tuple[datetime, datetime, str, list[str]]] = []
    spans: list[tuple[int, int]] = []

    for match in RANGE.finditer(text):
        start_p = match.group(3) or ""
        end_p = _period(match.group(6), match.group(7))
        start = _at(day, int(match.group(1)), int(match.group(2) or 0), start_p)
        end = _at(day, int(match.group(4)), int(match.group(5) or 0), end_p, start)
        if end <= start:
            end = _at(day, int(match.group(4)), int(match.group(5) or 0), "tarde", start)
        if end <= start:
            end = start + timedelta(minutes=60)
        around = _recurrence_window(text, match.start(), match.end())
        rec = recurrence_for(around)
        if rec:
            codes = weekday_codes(around)
            start, end = snap_week(start, end, codes)
        prefix = text[max(0, match.start() - 40) : match.start()]
        hits.append((start, end, _label(prefix), rec))
        spans.append((match.start(), match.end()))

    for match in HOUR.finditer(text):
        if _covered(match.start(), spans):
            continue
        prefix = text[max(0, match.start() - 12) : match.start()]
        if re.search(r"(?:at[eé]|until|till)\s+(?:umas?\s+)?$", prefix, re.I):
            continue
        around = _recurrence_window(text, match.start(), match.end())
        if not re.search(r"[A-Za-zÀ-ÿ]{3,}", around):
            continue
        period = match.group(4) or ""
        start = _at(day, int(match.group(1)), int(match.group(2) or 0), period)
        rest = text[match.end() : match.end() + 180]
        until = UNTIL.search(rest)
        if until and (HOUR.search(rest[: until.start()]) or RANGE.search(rest[: until.start()])):
            until = None
        if until:
            end = _at(
                day,
                int(until.group(1)),
                int(until.group(2) or 0),
                until.group(3) or period,
                start,
            )
        else:
            end = start + timedelta(minutes=60)
        rec = recurrence_for(around)
        if rec:
            start, end = snap_week(start, end, weekday_codes(around))
        title = _label(text[max(0, match.start() - 40) : match.start()])
        hits.append((start, end, title, rec))

    hits.sort(key=lambda item: item[0])
    closed: list[tuple[datetime, datetime, str, list[str]]] = []
    for i, (start, end, label, rec) in enumerate(hits):
        if end == start + timedelta(minutes=60) and i + 1 < len(hits):
            nxt = hits[i + 1][0]
            if start < nxt <= start + timedelta(hours=4):
                end = nxt
        closed.append((start, end, label, rec))

    merged: list[dict] = []
    for start, end, label, rec in closed:
        if merged:
            prev_end = datetime.fromisoformat(merged[-1]["end"])
            if start < prev_end and label.casefold() == merged[-1]["text"].casefold():
                if end > prev_end:
                    merged[-1]["end"] = end.isoformat()
                if rec and not merged[-1].get("recurrence"):
                    merged[-1]["recurrence"] = rec
                continue
        if end <= start:
            continue
        item = {"text": label, "start": start.isoformat(), "end": end.isoformat()}
        if rec:
            item["recurrence"] = rec
        merged.append(item)
    return merged


def _when(value: str) -> datetime | None:
    raw = str(value or "")
    if "T" not in raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _all_day(value: str) -> date | None:
    raw = str(value or "")
    if "T" in raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def overlaps(a: dict, b: dict) -> bool:
    a_day, b_day = _all_day(a.get("start") or ""), _all_day(b.get("start") or "")
    if a_day and b_day:
        a_end, b_end = _all_day(a.get("end") or ""), _all_day(b.get("end") or "")
        return bool(a_end and b_end and a_day < b_end and b_day < a_end)
    if a_day or b_day:
        all_day, timed = (a, b) if a_day else (b, a)
        start = _all_day(all_day.get("start") or "")
        end = _all_day(all_day.get("end") or "")
        timed_start, timed_end = _when(timed.get("start") or ""), _when(timed.get("end") or "")
        if not all((start, end, timed_start, timed_end)):
            return False
        all_start = timed_start.replace(
            year=start.year, month=start.month, day=start.day, hour=0, minute=0, second=0, microsecond=0
        )
        all_end = all_start + timedelta(days=(end - start).days)
        return timed_start < all_end and all_start < timed_end
    a0, a1 = _when(a.get("start") or ""), _when(a.get("end") or "")
    b0, b1 = _when(b.get("start") or ""), _when(b.get("end") or "")
    if not all((a0, a1, b0, b1)):
        return False
    return a0 < b1 and b0 < a1


def _stamp_min(item: dict) -> str:
    when = _when(item.get("start") or "")
    return when.strftime("%Y-%m-%dT%H:%M") if when else str(item.get("start") or "")[:16]


def conflicts(planned: list[dict], existing: list[dict] | None = None) -> list[dict]:
    """Overlaps inside the dump, or against events already on the calendar."""
    out: list[dict] = []
    items = list(planned or [])
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if overlaps(a, b):
                out.append(
                    {
                        "new": a.get("text") or "",
                        "existing": b.get("text") or "",
                        "kind": "dump",
                    }
                )
    for a in items:
        for raw in existing or []:
            other = {
                "start": raw.get("start"),
                "end": raw.get("end"),
                "text": raw.get("summary") or raw.get("text") or "",
            }
            if not overlaps(a, other):
                continue
            if _stamp_min(a) == _stamp_min(other) and (a.get("text") or "").casefold() == (
                other.get("text") or ""
            ).casefold():
                continue
            out.append(
                {
                    "new": a.get("text") or "",
                    "existing": other.get("text") or "",
                    "kind": "calendar",
                }
            )
    return out
