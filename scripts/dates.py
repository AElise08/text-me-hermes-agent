#!/usr/bin/env python3
"""Pull candidate dates out of a page the owner sent — never invent one."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

ISO = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?")
DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
NAMED = re.compile(
    r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b",
    re.I,
)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    try:
        parser.feed(html)
    except Exception:
        return html
    return " ".join(parser.parts)


def parse_html(html: str, now: datetime | None = None) -> list[dict]:
    """Return unique ISO datetimes found in the page, future-first."""
    now = now or datetime.now(timezone.utc)
    text = html_to_text(html)
    found: list[datetime] = []
    for match in ISO.finditer(text):
        stamp = match.group(1)
        clock = match.group(2) or "00:00"
        found.append(datetime.fromisoformat(f"{stamp}T{clock}:00+00:00"))
    for match in DMY.finditer(text):
        d, m, y = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if m > 12 and d <= 12:
            d, m = m, d
        if 1 <= m <= 12 and 1 <= d <= 31:
            found.append(datetime(y, m, d, tzinfo=timezone.utc))
    for match in NAMED.finditer(text):
        month = MONTHS[match.group(1).lower()]
        found.append(datetime(int(match.group(3)), month, int(match.group(2)), tzinfo=timezone.utc))
    uniq: list[datetime] = []
    seen: set[str] = set()
    for item in found:
        key = item.date().isoformat()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    future = [x for x in uniq if x.date() >= now.date()]
    ordered = sorted(future or uniq)
    return [{"iso": x.isoformat(), "date": x.date().isoformat()} for x in ordered]


def latest(candidates: Iterable[dict]) -> dict | None:
    items = list(candidates)
    return items[-1] if items else None
