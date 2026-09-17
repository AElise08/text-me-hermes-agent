#!/usr/bin/env python3
"""Headlines for the morning page — no chat turn, no --extra-file required.

The feed language is the language of the chat (`matriz.py language`), not a
baked-in Portuguese default. German in the thread → German headlines; English
→ English; an unknown tag still goes to Google News in that tag. Empty tag
falls back to English (never Portuguese). Items older than twelve hours are
dropped so the page is this morning, not last week.
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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = "text-me-hermes-agent/1.0 (+https://github.com/AElise08/text-me-hermes-agent)"
TIMEOUT = 8
MAX_AGE = timedelta(hours=12)
NEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

# Google News wants a country next to the language. Chat gives a tag (de, ja,
# pt-BR); we only fill the country when the tag did not already carry one.
COUNTRY = {
    "ar": "SA", "ca": "ES", "cs": "CZ", "da": "DK", "de": "DE", "el": "GR",
    "en": "US", "es": "ES", "fi": "FI", "fr": "FR", "he": "IL", "hi": "IN",
    "hu": "HU", "id": "ID", "it": "IT", "ja": "JP", "ko": "KR", "nb": "NO",
    "nl": "NL", "no": "NO", "pl": "PL", "pt": "BR", "ro": "RO", "ru": "RU",
    "sv": "SE", "th": "TH", "tr": "TR", "uk": "UA", "vi": "VN", "zh": "CN",
}

CARTOON_Q = {
    "de": "Karikatur",
    "en": "editorial cartoon",
    "es": "viñeta editorial",
    "fr": "dessin de presse",
    "it": "vignetta",
    "ja": "風刺漫画",
    "nl": "spotprent",
    "pt": "charge do dia",
}

_TAG = re.compile(r"<[^>]+>")


def tag(language: str) -> str:
    return (language or "").strip().lower().replace("_", "-")


def locale(language: str) -> tuple[str, str, str]:
    """hl, gl, ceid for Google News from the speaker's chat language.

    `de` → German edition. `pt-PT` stays Portugal. An empty tag is English —
    we do not invent Portuguese.
    """
    raw = tag(language)
    if not raw:
        return ("en", "US", "US:en")
    parts = [p for p in raw.split("-") if p]
    primary = (parts[0][:2] if parts else "en")
    region = parts[1].upper() if len(parts) > 1 and len(parts[1]) == 2 else COUNTRY.get(primary, primary.upper())
    if primary == "pt" and region == "BR":
        return ("pt-BR", "BR", "BR:pt-419")
    if primary == "zh" and region in ("CN", "SG"):
        return ("zh-CN", region, f"{region}:zh-Hans")
    if primary == "zh":
        return ("zh-TW", region, f"{region}:zh-Hant")
    hl = f"{primary}-{region}" if len(parts) > 1 else primary
    return (hl, region, f"{region}:{primary}")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read()


def _plain(text: str) -> str:
    return html.unescape(_TAG.sub("", text or "")).strip()


def _when(node: ET.Element) -> datetime | None:
    raw = (node.findtext("pubDate") or node.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def items(payload: bytes) -> list[tuple[str, str, str, datetime | None]]:
    out: list[tuple[str, str, str, datetime | None]] = []
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
            out.append((title, link, source, _when(node)))
    return out


def _fresh(
    rows: list[tuple[str, str, str, datetime | None]],
    now: datetime | None = None,
    max_age: timedelta | None = None,
) -> list[tuple[str, str, str]]:
    """Keep only items dated within max_age. Undated rows are old, skip them."""
    now = now or datetime.now(timezone.utc)
    window = max_age if max_age is not None else MAX_AGE
    kept: list[tuple[str, str, str]] = []
    for title, link, source, published in rows:
        if published is None:
            continue
        if now - published > window:
            continue
        kept.append((title, link, source))
    return kept


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
    language: str = "",
    limit: int = 4,
    now: datetime | None = None,
) -> list[str]:
    """2–4 one-line summaries in the speaker's language, from the last hours."""
    avoid_l = [a.lower() for a in (avoid or []) if a]
    hl, gl, ceid = locale(language)
    found: list[str] = []
    seen: set[str] = set()
    for interest in [i.strip() for i in (interests or []) if i and i.strip()][:4]:
        url = NEWS.format(q=urllib.parse.quote(interest), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = _fresh(items(fetch(url)), now=now)
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
            found.append(_line(title, source))
            if len(found) >= limit:
                return found
    return found


def charge(language: str = "", now: datetime | None = None) -> list[str]:
    """One recent cartoon in the speaker's language, with its source link."""
    query = CARTOON_Q.get(tag(language).split("-")[0][:2] or "en", "editorial cartoon")
    hl, gl, ceid = locale(language)
    url = NEWS.format(q=urllib.parse.quote(query), hl=hl, gl=gl, ceid=ceid)
    try:
        rows = _fresh(items(fetch(url)), now=now, max_age=timedelta(hours=48))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return []
    if not rows:
        return []
    title, link, source = rows[0]
    return [_line(title, source or query, link)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Research clips for the morning edition.")
    parser.add_argument("--interests", default="")
    parser.add_argument("--avoid", default="")
    parser.add_argument("--language", default="", help="chat language tag (de, en, ja, pt-BR, …)")
    parser.add_argument("--charge", action="store_true")
    args = parser.parse_args()
    interests = [x.strip() for x in args.interests.split(",") if x.strip()]
    avoid = [x.strip() for x in args.avoid.split(",") if x.strip()]
    out = {
        "clips": clips(interests, avoid, args.language),
        "charge": charge(args.language) if args.charge else [],
        "locale": list(locale(args.language)),
    }
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
