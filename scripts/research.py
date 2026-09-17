#!/usr/bin/env python3
"""Headlines for the morning page — no chat turn, no --extra-file required.

Pulls public RSS for whatever this person named as interests, drops what they
asked to keep out, and optionally one editorial cartoon with its source link.
Network failure is empty, never fatal: the rest of the edition still goes out.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "text-me-hermes-agent/1.0 (+https://github.com/AElise08/text-me-hermes-agent)"
TIMEOUT = 8
NEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
CARTOON = "https://www.theguardian.com/tone/cartoons/rss"

LOCALE = {
    "pt": ("pt-BR", "BR", "BR:pt-419"),
    "es": ("es", "ES", "ES:es"),
    "en": ("en-US", "US", "US:en"),
}

_TAG = re.compile(r"<[^>]+>")


def locale(language: str) -> tuple[str, str, str]:
    return LOCALE.get((language or "en").lower()[:2], LOCALE["en"])


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read()


def _plain(text: str) -> str:
    return html.unescape(_TAG.sub("", text or "")).strip()


def items(payload: bytes) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return out
    for node in root.iter("item"):
        title = _plain(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        source = ""
        src = node.find("source")
        if src is not None and (src.text or "").strip():
            source = _plain(src.text)
        if title:
            out.append((title, link, source))
    return out


def _line(title: str, source: str, link: str = "") -> str:
    line = title
    if source and source.casefold() not in title.casefold():
        line = f"{title} — {source}"
    if link:
        line = f"{line} {link}".strip()
    return line


def clips(
    interests: list[str] | None,
    avoid: list[str] | None = None,
    language: str = "en",
    limit: int = 4,
) -> list[str]:
    """2–4 one-line summaries matching their interests, nothing they asked to skip."""
    avoid_l = [a.lower() for a in (avoid or []) if a]
    hl, gl, ceid = locale(language)
    found: list[str] = []
    seen: set[str] = set()
    for interest in [i.strip() for i in (interests or []) if i and i.strip()][:4]:
        url = NEWS.format(q=urllib.parse.quote(interest), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = items(fetch(url))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        for title, _link, source in rows:
            blob = f"{title} {source}".lower()
            if any(term in blob for term in avoid_l):
                continue
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            # Kindle page: a sentence, not a URL dump.
            found.append(_line(title, source))
            if len(found) >= limit:
                return found
    return found


def charge(language: str = "en") -> list[str]:
    """One editorial cartoon with its source link, if the feed answers."""
    try:
        rows = items(fetch(CARTOON))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return []
    if not rows:
        return []
    title, link, source = rows[0]
    src = source or "The Guardian"
    return [_line(title, src, link)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Research clips for the morning edition.")
    parser.add_argument("--interests", default="")
    parser.add_argument("--avoid", default="")
    parser.add_argument("--language", default="en")
    parser.add_argument("--charge", action="store_true")
    args = parser.parse_args()
    interests = [x.strip() for x in args.interests.split(",") if x.strip()]
    avoid = [x.strip() for x in args.avoid.split(",") if x.strip()]
    out = {
        "clips": clips(interests, avoid, args.language),
        "charge": charge(args.language) if args.charge else [],
    }
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
