#!/usr/bin/env python3
"""Turn a dumped day with clock times into every calendar interval.

Works for any person, any language they wrote the dump in. The model must
not pick one 'focus' block — this parser is the grid.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

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


def _label(window: str) -> str:
    """Use the words they used, not a fixed school/physio vocabulary."""
    before = re.split(r"\d", window, maxsplit=1)[0]
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", before)
    keep = [t for t in tokens if t.casefold() not in STOP]
    if not keep:
        return "Busy"
    return " ".join(keep[-2:]).strip().capitalize()


def _covered(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= index < b for a, b in spans)


def _period(*parts: str | None) -> str:
    return " ".join(p for p in parts if p) 


def parse(text: str, day: datetime) -> list[dict]:
    """Named intervals in order. Lone starts close at the next clock or +60m."""
    text = text or ""
    day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    hits: list[tuple[datetime, datetime, str]] = []
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
        around = text[max(0, match.start() - 50) : match.end() + 8]
        hits.append((start, end, _label(around)))
        spans.append((match.start(), match.end()))

    for match in HOUR.finditer(text):
        if _covered(match.start(), spans):
            continue
        prefix = text[max(0, match.start() - 12) : match.start()]
        if re.search(r"(?:at[eé]|until|till)\s+(?:umas?\s+)?$", prefix, re.I):
            continue
        around = text[max(0, match.start() - 40) : match.end() + 8]
        if not re.search(r"[A-Za-zÀ-ÿ]{3,}", around):
            continue
        period = match.group(4) or ""
        start = _at(day, int(match.group(1)), int(match.group(2) or 0), period)
        until = UNTIL.search(text[match.end() : match.end() + 180])
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
        hits.append((start, end, _label(around)))

    hits.sort(key=lambda item: item[0])
    closed: list[tuple[datetime, datetime, str]] = []
    for i, (start, end, label) in enumerate(hits):
        if end == start + timedelta(minutes=60) and i + 1 < len(hits):
            nxt = hits[i + 1][0]
            if start < nxt <= start + timedelta(hours=4):
                end = nxt
        closed.append((start, end, label))

    merged: list[dict] = []
    for start, end, label in closed:
        if merged:
            prev_end = datetime.fromisoformat(merged[-1]["end"])
            if start < prev_end and label.casefold() == merged[-1]["text"].casefold():
                if end > prev_end:
                    merged[-1]["end"] = end.isoformat()
                continue
        if end <= start:
            continue
        merged.append({"text": label, "start": start.isoformat(), "end": end.isoformat()})
    return merged
