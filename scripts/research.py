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
import http.client
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
TIMEOUT = 12
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
    "de": "witzige Karikatur",
    "en": "funny comic strip",
    "es": "viñeta humor",
    "fr": "dessin d'humour",
    "it": "vignetta umoristica",
    "ja": "四コマ漫画",
    "nl": "grappige cartoon",
    "pt": "tirinha humor",
}

_OG = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.I,
)
_OG_DESC = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_DESC_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:description|description)["\']',
    re.I,
)
_CANON = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
    re.I,
)
_HREF = re.compile(r'''href=["']([^"'#]+)["']''', re.I)
_IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
_SRC = re.compile(
    r"""(?:src|data-src|data-original|data-lazy-src)=["']([^"']+)""",
    re.I,
)
_WIDTH = re.compile(r"""width=["']?(\d+)""", re.I)
_P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
_SENT = re.compile(r"(?<=[.!?。])\s+")
_MEDIA = "{http://search.yahoo.com/mrss/}"
_TAG = re.compile(r"<[^>]+>")
_GOOGLE_HOST = (
    "gstatic.com",
    "google.com",
    "news.google.",
    "googleusercontent.com",
    "ggpht.com",
    "googleapis.com",
    "googlesyndication.com",
)
_LOGO_HINT = (
    "logo", "favicon", "sprite", "icon", "wordmark", "masthead",
    "branding", "google-news", "gnews", "placeholder",
)
_TOON_HINT = (
    "charge", "cartoon", "caricatura", "vineta", "viñeta",
    "karikatur", "dessin", "vignetta", "spotprent",
)
_SKIP_HREF = (
    "google-analytics", "googletagmanager", "doubleclick", "facebook.com/",
    "twitter.com/", "instagram.com/", "whatsapp.com/", "schema.org",
    "fonts.g", "googlesyndication",
)


def _plain(text: str) -> str:
    return html.unescape(_TAG.sub("", text or "")).strip()


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


_NET = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    OSError,
    ValueError,
    http.client.IncompleteRead,
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        try:
            return response.read()
        except http.client.IncompleteRead as exc:
            return exc.partial or b""


def fetch_page(url: str) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://news.google.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            final = response.geturl()
            try:
                raw = response.read(900_000)
            except http.client.IncompleteRead as exc:
                raw = exc.partial or b""
            ctype = (response.headers.get("Content-Type") or "").lower()
    except _NET:
        return url, ""
    if "javascript" in ctype or "json" in ctype or "image/" in ctype:
        return final, ""
    return final, raw.decode("utf-8", "replace")


def googleish(url: str) -> bool:
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    return any(part in host for part in _GOOGLE_HOST) or host.endswith(".google")


def logoish(url: str) -> bool:
    blob = (url or "").lower()
    if googleish(url):
        return True
    return any(hint in blob for hint in _LOGO_HINT)


def article_href(url: str) -> bool:
    if not url or googleish(url) or logoish(url):
        return False
    blob = url.lower()
    if blob.startswith(("javascript:", "mailto:", "tel:", "#")):
        return False
    if any(bit in blob for bit in _SKIP_HREF):
        return False
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith((".js", ".css", ".json", ".xml", ".woff", ".woff2", ".ttf", ".ico")):
        return False
    return True


def abs_url(src: str, base: str) -> str:
    src = html.unescape(src or "").strip()
    if not src or src.startswith("data:"):
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/") and base.startswith("http"):
        parts = urllib.parse.urlsplit(base)
        return f"{parts.scheme}://{parts.netloc}{src}"
    return src


def follow_publisher(url: str, source_url: str = "", title: str = "") -> tuple[str, str]:
    """Leave Google News for the paper that actually drew the cartoon."""
    final, page = fetch_page(url) if url else ("", "")
    if page and not googleish(final):
        return final, page
    if page and googleish(final):
        canon = _CANON.search(page)
        if canon:
            href = abs_url(canon.group(1), final)
            if href and article_href(href):
                dest, body = fetch_page(href)
                if dest and not googleish(dest) and body:
                    return dest, body
        for href in _HREF.findall(page):
            href = abs_url(html.unescape(href), final)
            if not article_href(href):
                continue
            dest, body = fetch_page(href)
            if dest and not googleish(dest) and len(body) > 400:
                return dest, body
    if source_url:
        found = find_on_source(source_url, title)
        if found[1]:
            return found
    return final, page


def _title_bits(title: str) -> list[str]:
    stop = {
        "noticias", "notícias", "região", "santa", "para", "from", "with",
        "charge", "charges", "dia", "hoje", "today", "veja",
    }
    return [w for w in re.findall(r"[a-záéíóúãõâêôç0-9]{4,}", (title or "").casefold()) if w not in stop][:8]


def find_on_source(source_url: str, title: str = "") -> tuple[str, str]:
    """Open the paper's site and pick the piece that matches the headline."""
    if not source_url:
        return "", ""
    if source_url.startswith("//"):
        source_url = "https:" + source_url
    elif not source_url.startswith("http"):
        source_url = "https://" + source_url.lstrip("/")
    landed, page = fetch_page(source_url)
    if not page:
        return "", ""
    bits = _title_bits(title)
    ranked: list[tuple[int, str]] = []
    for href in _HREF.findall(page):
        url = abs_url(href, landed or source_url)
        if not article_href(url):
            continue
        blob = url.lower()
        score = sum(5 for hint in _TOON_HINT if hint in blob) + sum(1 for w in bits if w in blob)
        if score:
            ranked.append((score, url))
    ranked.sort(key=lambda row: -row[0])
    for _score, url in ranked[:5]:
        dest, body = fetch_page(url)
        if dest and not googleish(dest) and len(body) > 400:
            return dest, body
    return landed, page


def _image_url(node: ET.Element) -> str:
    for name in ("content", "thumbnail"):
        el = node.find(_MEDIA + name)
        if el is not None and (el.get("url") or "").strip():
            return el.get("url").strip()
    enc = node.find("enclosure")
    if enc is not None:
        typ = (enc.get("type") or "").lower()
        url = (enc.get("url") or "").strip()
        if url and (typ.startswith("image") or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))):
            return url
    return ""


def og_image(html_text: str) -> str:
    match = _OG.search(html_text) or _OG_REV.search(html_text)
    return html.unescape(match.group(1).strip()) if match else ""


def og_description(html_text: str) -> str:
    match = _OG_DESC.search(html_text) or _OG_DESC_REV.search(html_text)
    return html.unescape(match.group(1).strip()) if match else ""


def fetch_image(url: str) -> bytes:
    if not url:
        return b""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        data = response.read(2_000_000)
        ctype = (response.headers.get("Content-Type") or "").lower()
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[:4] == b"RIFF" or "image/" in ctype:
        return data
    return b""


def usable_image(url: str, data: bytes) -> bool:
    if not data or logoish(url):
        return False
    try:
        from PIL import Image

        im = Image.open(BytesIO(data))
        width, height = im.size
    except (OSError, ValueError):
        return False
    if width < 280 or height < 180 or width * height < 80_000:
        return False
    return True


def image_candidates(html_text: str, base: str) -> list[str]:
    ranked: list[tuple[int, str]] = []
    og = og_image(html_text)
    if og:
        url = abs_url(og, base)
        if url and not logoish(url):
            ranked.append((1200, url))
    for tag_html in _IMG_TAG.findall(html_text):
        src = _SRC.search(tag_html)
        if not src:
            continue
        url = abs_url(src.group(1), base)
        if not url or logoish(url):
            continue
        width = int(_WIDTH.search(tag_html).group(1)) if _WIDTH.search(tag_html) else 0
        score = width
        blob = (url + " " + tag_html).lower()
        if any(hint in blob for hint in _TOON_HINT):
            score += 800
        ranked.append((score, url))
    seen: set[str] = set()
    out: list[str] = []
    for _score, url in sorted(ranked, key=lambda row: -row[0]):
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out[:8]


def image_for(article_url: str, rss_image: str = "", source_url: str = "", title: str = "") -> bytes:
    """Bytes of the cartoon from the publisher, never a Google News mark."""
    tried: list[str] = []
    if rss_image and not logoish(rss_image):
        tried.append(rss_image)
    landed, page = follow_publisher(article_url, source_url, title)
    base = landed or source_url or article_url
    if page:
        tried.extend(image_candidates(page, base))
    for src in tried:
        try:
            data = fetch_image(src)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        if usable_image(src, data):
            return data
    return b""


def first_sentences(text: str, n: int = 2, limit: int = 360) -> str:
    text = " ".join(_plain(text).split())
    if not text:
        return ""
    parts = [p.strip() for p in _SENT.split(text) if p.strip()]
    joined = " ".join(parts[:n] or [text])
    if len(joined) > limit:
        joined = joined[: limit - 1].rsplit(" ", 1)[0] + "…"
    return joined


_JUNK_LEDE = (
    "cobertura jornalística abrangente",
    "google notícias",
    "google news",
    "agregada de fontes do mundo inteiro",
)


def echoes_title(happened: str, title: str) -> bool:
    compact = re.sub(r"\W+", "", (happened or "").casefold())
    head = re.sub(r"\W+", "", (title or "").casefold())[:48]
    return not happened or (bool(head) and head in compact)


def clean_lede(text: str, title: str = "") -> str:
    blob = (text or "").casefold()
    if any(bit in blob for bit in _JUNK_LEDE):
        return ""
    if echoes_title(text, title):
        return ""
    text = (text or "").strip()
    if len(text) < 40:
        return ""
    bits = _title_bits(title)
    need = 2 if len(bits) >= 2 else 1
    if bits and sum(1 for w in bits if w in blob) < need:
        return ""
    return text


def article_lede(url: str, source_url: str = "", title: str = "") -> str:
    if not url and not source_url:
        return ""
    _final, page = follow_publisher(url, source_url, title)
    if not page:
        return ""
    desc = clean_lede(first_sentences(og_description(page)), title)
    if len(desc) >= 80:
        return desc
    paras: list[str] = []
    for match in _P.finditer(page):
        bit = clean_lede(first_sentences(_plain(match.group(1)), 1, 240), title)
        if len(bit) >= 40:
            paras.append(bit)
        if len(paras) >= 2:
            break
    return first_sentences(" ".join(paras) or desc, 2)


def why_matters(
    interest: str,
    language: str,
    title: str = "",
    happened: str = "",
    goals: dict | None = None,
) -> str:
    """Why this clip is on the page — urgency, impact, goals, novelty, a decision."""
    primary = tag(language).split("-")[0][:2]
    blob = f"{title} {happened} {interest}".casefold()
    work = ((goals or {}).get("work") or "").casefold()
    life = ((goals or {}).get("life") or "").casefold()
    work_hit = bool(work) and any(len(w) > 4 and w in blob for w in work.split())
    life_hit = bool(life) and any(len(w) > 4 and w in blob for w in life.split())
    urgent = any(w in blob for w in ("hoje", "today", "agora", "now", "prazo", "deadline", "urgente"))
    decide = any(w in blob for w in ("deve", "should", "pode", "decis", "voto", "approve", "risco"))
    money = any(w in blob for w in ("pag", "preço", "price", "bolsa", "funding", "investimento"))
    concrete = (title.split(" - ")[0].split(" — ")[0]).strip()
    if len(concrete) > 90:
        concrete = concrete[:87] + "…"
    if primary == "pt":
        if work_hit:
            return f"Impacto na meta de trabalho: {concrete}."
        if life_hit:
            return f"Mexe com a tua meta de vida: {concrete}."
        if decide:
            return f"Pode pedir uma decisão tua: {concrete}."
        if urgent:
            return f"Urgência — isto mexeu nas últimas horas: {concrete}."
        if money:
            return f"Tem efeito prático (dinheiro, custo, recurso): {concrete}."
        return f"Novidade em {interest}: {concrete}."
    if work_hit:
        return f"Hits the work goal: {concrete}."
    if life_hit:
        return f"Hits the life goal: {concrete}."
    if decide:
        return f"May need a call from you: {concrete}."
    if urgent:
        return f"Urgent — this moved in the last hours: {concrete}."
    if money:
        return f"Practical stake (money, cost, resource): {concrete}."
    return f"New in {interest}: {concrete}."


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


def items(payload: bytes) -> list[tuple[str, str, str, datetime | None, str, str, str]]:
    out: list[tuple[str, str, str, datetime | None, str, str, str]] = []
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return out
    for node in root.iter("item"):
        title = _plain(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        source = ""
        source_url = ""
        src = node.find("source")
        if src is not None:
            if (src.text or "").strip():
                source = _plain(src.text)
            source_url = (src.get("url") or "").strip()
        if title:
            out.append((title, link, source, _when(node), _image_url(node), node.findtext("description") or "", source_url))
    return out


def _fresh(
    rows: list[tuple[str, str, str, datetime | None, str, str, str]],
    now: datetime | None = None,
    max_age: timedelta | None = None,
) -> list[tuple[str, str, str, str, str, str]]:
    """Keep only items dated within max_age. Undated rows are old, skip them."""
    now = now or datetime.now(timezone.utc)
    window = max_age if max_age is not None else MAX_AGE
    kept: list[tuple[str, str, str, str, str, str]] = []
    for title, link, source, published, image, description, source_url in rows:
        if published is None:
            continue
        if now - published > window:
            continue
        kept.append((title, link, source, image, description, source_url))
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
    goals: dict | None = None,
) -> list[dict]:
    """A few recent pieces: what happened, and why it matches an interest."""
    avoid_l = [a.lower() for a in (avoid or []) if a]
    hl, gl, ceid = locale(language)
    found: list[dict] = []
    seen: set[str] = set()
    for interest in [i.strip() for i in (interests or []) if i and i.strip()][:4]:
        url = NEWS.format(q=urllib.parse.quote(interest), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = _fresh(items(fetch(url)), now=now)
        except _NET:
            continue
        for title, link, source, _image, description, source_url in rows:
            blob = f"{title} {source}".lower()
            if any(term in blob for term in avoid_l):
                continue
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            happened = first_sentences(description)
            if echoes_title(happened, title) or len(happened) < 80:
                try:
                    happened = article_lede(link, source_url, title) or happened
                except _NET:
                    pass
            happened = clean_lede(happened, title)
            found.append(
                {
                    "title": title,
                    "source": source,
                    "happened": happened,
                    "why": why_matters(interest, language, title, happened, goals),
                }
            )
            if len(found) >= limit:
                return found
    return found


_SKIP_CHARGE = (
    "espelho da democracia",
    "arte da crítica",
    "arte da critica",
    "o que é uma charge",
    "o que e uma charge",
    "história da charge",
    "historia da charge",
)


def _charge_ok(title: str) -> bool:
    blob = (title or "").casefold()
    return not any(bit in blob for bit in _SKIP_CHARGE)


def charge(language: str = "", now: datetime | None = None) -> list[dict]:
    """One recent funny cartoon in the speaker's language, with image bytes when we can."""
    primary = tag(language).split("-")[0][:2] or "en"
    queries = [CARTOON_Q.get(primary, "funny comic")]
    if primary == "pt":
        queries = ["tirinha humor", "charge humor", "charge do dia"]
    elif primary == "en":
        queries = ["funny comic strip", "editorial cartoon funny"]
    hl, gl, ceid = locale(language)
    picked = None
    for query in queries:
        url = NEWS.format(q=urllib.parse.quote(query), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = _fresh(items(fetch(url)), now=now, max_age=timedelta(hours=48))
        except _NET:
            continue
        for title, link, source, rss_image, _desc, source_url in rows[:8]:
            if not _charge_ok(title):
                continue
            try:
                picture = image_for(link, rss_image, source_url=source_url, title=title)
            except _NET:
                picture = b""
            row = {
                "title": title,
                "source": source or query,
                "link": link,
                "line": _line(title, source or query),
                "image": picture,
            }
            if picture:
                return [row]
            if picked is None:
                picked = row
    return [picked] if picked else []


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
        "charge": [
            {k: v for k, v in row.items() if k != "image"} | {"has_image": bool(row.get("image"))}
            for row in (charge(args.language) if args.charge else [])
        ],
        "locale": list(locale(args.language)),
    }
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
