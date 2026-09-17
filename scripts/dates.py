#!/usr/bin/env python3
"""Pull candidate dates out of a page the owner sent — never invent one."""
from __future__ import annotations

import re
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

MAX_HTML_BYTES = 1_000_000


def safe_url(url: str) -> bool:
    """Allow ordinary public web pages, never local services or file URLs."""
    parsed = urllib.parse.urlsplit((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password or port not in {None, 80, 443}:
        return False
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        addresses = {
            info[4][0] for info in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
        }
    except OSError:
        return False
    try:
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


class _PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not safe_url(newurl):
            raise urllib.error.URLError("redirect to a non-public URL blocked")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def public_opener():
    return urllib.request.build_opener(_PublicRedirect())


def fetch_html_page(url: str) -> tuple[str, str]:
    """Fetch a user-supplied public page with size and redirect limits."""
    if not safe_url(url):
        raise ValueError("URL must be a public http(s) page")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "text-me/1.0", "Accept": "text/html,application/xhtml+xml"},
    )
    opener = public_opener()
    try:
        with opener.open(request, timeout=12) as response:
            final = response.geturl()
            if not safe_url(final):
                raise ValueError("redirect to a non-public URL blocked")
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "xhtml" not in content_type:
                raise ValueError("URL did not return HTML")
            raw = response.read(MAX_HTML_BYTES + 1)
    except urllib.error.URLError as exc:
        raise ValueError(f"could not fetch URL: {exc.reason}") from exc
    if len(raw) > MAX_HTML_BYTES:
        raise ValueError("URL response is too large")
    return final, raw.decode("utf-8", "replace")


def fetch_html(url: str) -> str:
    return fetch_html_page(url)[1]

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
