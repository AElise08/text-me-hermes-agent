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
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cartoon as cartoon_mod
import dates as dates_mod

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
    "tirinha", "quadrinho", "comic", "cartum", "humor",
)
_LOCALISH = (
    "prefeitura",
    "câmara municipal",
    "camara municipal",
    "secretaria municipal",
)
COMIC_HOMES = {
    "pt": (
        "https://www.willtirando.com.br/",
        "https://www.umsabadoqualquer.com/",
        "https://www.humorpolitico.com.br/",
    ),
    "en": (
        "https://xkcd.com/",
        "https://www.gocomics.com/",
    ),
    "de": ("https://xkcd.com/",),
    "es": ("https://www.umsabadoqualquer.com/",),
    "fr": ("https://xkcd.com/",),
}
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
    if not dates_mod.safe_url(url):
        raise urllib.error.URLError("non-public URL blocked")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    with dates_mod.public_opener().open(req, timeout=TIMEOUT) as response:
        try:
            return response.read()
        except http.client.IncompleteRead as exc:
            return exc.partial or b""


def fetch_page(url: str) -> tuple[str, str]:
    try:
        final, page = dates_mod.fetch_html_page(url)
    except (ValueError, _NET):
        return url, ""
    return final, page


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
    if not dates_mod.safe_url(url):
        return b""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    with dates_mod.public_opener().open(req, timeout=TIMEOUT) as response:
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


def first_sentences(text: str, n: int = 4, limit: int = 720) -> str:
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
    "página principal",
    "aceitar cookies",
    "subscribe",
    "centro de memória",
    "all rights reserved",
    "javascript",
    "artigos salvos",
    "minha folha",
    "área personalizada",
    "area personalizada",
    "conteúdo criado em parceria",
    "conteudo criado em parceria",
    "últimas notícias do brasil e do mundo",
    "ultimas noticias do brasil e do mundo",
    "cnpj:",
)


def echoes_title(happened: str, title: str) -> bool:
    compact = re.sub(r"\W+", "", (happened or "").casefold())
    head = re.sub(r"\W+", "", (title or "").casefold())[:48]
    return not happened or (bool(head) and head in compact)


def clean_lede(text: str, title: str = "") -> str:
    blob = (text or "").casefold()
    if any(bit in blob for bit in _JUNK_LEDE):
        return ""
    if echoes_title(text, title) and len(text or "") < 140:
        return ""
    text = (text or "").strip()
    if len(text) < 40:
        return ""
    bits = [w for w in _title_bits(title) if len(w) >= 5]
    if len(bits) >= 2 and not any(w in blob for w in bits):
        return ""
    return text


def article_lede(url: str, source_url: str = "", title: str = "") -> str:
    if not url and not source_url:
        return ""
    _final, page = follow_publisher(url, source_url, title)
    if not page:
        return ""
    desc = clean_lede(first_sentences(og_description(page), 4, 720), title)
    if len(desc) >= 140:
        return desc
    paras: list[str] = []
    for match in _P.finditer(page):
        bit = first_sentences(_plain(match.group(1)), 3, 320)
        bit = clean_lede(bit, title) or (bit if len(bit) >= 70 else "")
        if len(bit) >= 50:
            paras.append(bit)
        if len(paras) >= 3:
            break
    return first_sentences(" ".join(paras) or desc, 4, 720)


def why_matters(
    interest: str,
    language: str,
    title: str = "",
    happened: str = "",
    goals: dict | None = None,
) -> str:
    """Why this clip is on the page — urgency, impact, goals, novelty, a decision."""
    primary = tag(language).split("-")[0][:2]
    blob = f"{title} {happened}".casefold()
    work = ((goals or {}).get("work") or "").casefold()
    life = ((goals or {}).get("life") or "").casefold()
    work_hit = bool(work) and any(len(w) > 4 and w in blob for w in work.split())
    life_hit = bool(life) and any(len(w) > 4 and w in blob for w in life.split())
    urgent = any(w in blob for w in ("hoje", "today", "agora", "now", "prazo", "deadline", "urgente"))
    decide = any(
        w in blob
        for w in (
            "decisão",
            "decisao",
            "vota",
            "votação",
            "votacao",
            "aprova",
            "approve",
            "should you",
            "needs your yes",
        )
    )
    money = any(w in blob for w in ("pag", "preço", "price", "bolsa", "funding", "investimento"))
    concrete = (title.split(" - ")[0].split(" — ")[0]).strip()
    if len(concrete) > 90:
        concrete = concrete[:87] + "…"
    if primary == "pt":
        if work_hit:
            return "Tem a ver com a tua meta de trabalho."
        if life_hit:
            return "Tem a ver com a tua meta de vida."
        if decide:
            return "Isso envolve uma decisão de verdade — voto, aprovação, sim ou não."
        if urgent:
            return "Saiu nas últimas horas."
        if money:
            return "Tem efeito prático de dinheiro ou custo."
        return "É recente e está no que você acompanha."
    if work_hit:
        return "This touches what you are doing at work."
    if life_hit:
        return "This touches what you are doing in life."
    if decide:
        return "This is an actual choice — a vote, an approval, a yes or no."
    if urgent:
        return "This moved in the last hours."
    if money:
        return "There is a practical money or cost stake."
    return "It's recent and on what you follow."


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


_JUNK_TITLE = (
    "criptomoeda",
    "cripto ",
    "crypto",
    "forex",
    "ikki-tousen",
    "250 vezes",
    "250x",
    "notícias do dia no brasil",
    "noticias do dia no brasil",
    "notícias do dia no mundo",
    "we're giving away",
    "1 trillion tokens",
    "trillion tokens",
    "experiential labs",
)


def _search_queries(interests, goals, about) -> list[str]:
    out = []
    for interest in interests or []:
        if (interest or "").strip():
            out.append(interest.strip())
    for value in (goals or {}).values():
        words = [w for w in re.findall(r"[A-Za-zÀ-ÿ]{5,}", value or "")]
        if words:
            out.append(" ".join(words[:5]))
    for item in about or []:
        words = [w for w in re.findall(r"[A-Za-zÀ-ÿ]{5,}", item or "")]
        if len(words) >= 2:
            out.append(" ".join(words[:5]))
        elif (item or "").strip():
            out.append(item.strip())
    seen = set()
    unique = []
    for query in out:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(query)
    return unique[:8]


def _clip_rank(row: dict) -> int:
    why = (row.get("why") or "").casefold()
    score = 0
    if "meta de trabalho" in why or "doing at work" in why:
        score += 4
    if "meta de vida" in why or "doing in life" in why:
        score += 4
    if "decisão de verdade" in why or "actual choice" in why:
        score += 3
    if "últimas horas" in why or "last hours" in why:
        score += 2
    if row.get("happened"):
        score += 1
    return score


def _too_close(title: str, seen_titles: list[str]) -> bool:
    words = set(re.findall(r"[a-zà-ÿ]{4,}", title.casefold()))
    if len(words) < 3:
        return False
    for other in seen_titles:
        other_w = set(re.findall(r"[a-zà-ÿ]{4,}", other))
        if not other_w:
            continue
        if len(words & other_w) / min(len(words), len(other_w)) >= 0.55:
            return True
    return False


def _skip_local(title: str, avoid_l: list[str]) -> bool:
    if not any("local" in a for a in avoid_l):
        return False
    blob = title.casefold()
    return any(bit in blob for bit in _LOCALISH)


def clips(
    interests: list[str] | None,
    avoid: list[str] | None = None,
    language: str = "",
    limit: int = 8,
    now: datetime | None = None,
    goals: dict | None = None,
    about: list[str] | None = None,
) -> list[dict]:
    """Recent pieces scored against their goals — enough to fill a newspaper well."""
    avoid_l = [a.lower() for a in (avoid or []) if a]
    hl, gl, ceid = locale(language)
    found: list[dict] = []
    seen: set[str] = set()
    for interest in _search_queries(interests, goals, about):
        url = NEWS.format(q=urllib.parse.quote(interest), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = _fresh(items(fetch(url)), now=now)
        except _NET:
            continue
        for title, link, source, _image, description, source_url in rows[:6]:
            blob = f"{title} {source}".lower()
            key = title.casefold()
            if any(term in blob for term in avoid_l):
                continue
            if _skip_local(title, avoid_l):
                continue
            if any(bit in key for bit in _JUNK_TITLE):
                continue
            if key in seen or _too_close(title, list(seen)):
                continue
            seen.add(key)
            happened = first_sentences(description)
            found.append(
                {
                    "title": title,
                    "source": source,
                    "happened": happened,
                    "why": why_matters(interest, language, title, happened, goals),
                    "_link": link,
                    "_source_url": source_url,
                    "_query": interest,
                }
            )
    found.sort(key=_clip_rank, reverse=True)
    chosen: list[dict] = []
    for row in found[: limit + 6]:
        happened = row.get("happened") or ""
        title = row["title"]
        query = row.get("_query") or ((interests or ["news"])[0] if interests else "news")
        if echoes_title(happened, title) or len(happened) < 160:
            try:
                happened = article_lede(row.get("_link") or "", row.get("_source_url") or "", title) or happened
            except _NET:
                pass
            happened = clean_lede(happened, title)
            if any(bit in (happened or "").casefold() for bit in _JUNK_LEDE):
                happened = ""
            row["happened"] = happened
            row["why"] = why_matters(query, language, title, happened, goals)
        row.pop("_link", None)
        row.pop("_source_url", None)
        row.pop("_query", None)
        if len((row.get("happened") or "").strip()) < 40:
            continue
        chosen.append(row)
        if len(chosen) >= limit:
            break
    return chosen


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


def _cartoon_hint(title: str, link: str = "", source: str = "") -> bool:
    blob = f"{title} {link} {source}".casefold()
    return any(hint in blob for hint in _TOON_HINT)


def _usable_cartoon(blob: bytes) -> bool:
    """Keep published drawings. Drop empty bytes, logos we already filtered, and photos of people."""
    if not blob:
        return False
    return not cartoon_mod.looks_like_photo(blob)


def _home_cartoon(language: str) -> dict | None:
    """A strip from a real comic site, not a drawing we invented."""
    primary = tag(language).split("-")[0][:2] or "en"
    homes = COMIC_HOMES.get(primary) or COMIC_HOMES["en"]
    for home in homes:
        try:
            landed, page = fetch_page(home)
        except _NET:
            continue
        if not page:
            continue
        title = ""
        match = re.search(r"<title>([^<]+)</title>", page, re.I)
        if match:
            title = _plain(match.group(1)).split("|")[0].split("–")[0].split("—")[0].strip()
        picture = b""
        for src in image_candidates(page, landed or home):
            try:
                data = fetch_image(src)
            except _NET:
                continue
            if usable_image(src, data) and _usable_cartoon(data):
                picture = data
                break
        if not picture:
            continue
        host = urllib.parse.urlsplit(landed or home).netloc.replace("www.", "")
        return {
            "title": title or host,
            "source": host,
            "link": landed or home,
            "line": _line(title or host, host),
            "image": picture,
        }
    return None


def charge(language: str = "", now: datetime | None = None) -> list[dict]:
    """One recent funny cartoon from the web in the speaker's language."""
    primary = tag(language).split("-")[0][:2] or "en"
    home = _home_cartoon(language)
    if home:
        return [home]
    queries = [CARTOON_Q.get(primary, "funny comic")]
    if primary == "pt":
        queries = ["tirinha", "charge do dia", "tirinha do dia", "cartum humor", "quadrinho humor"]
    elif primary == "en":
        queries = ["funny comic strip", "comic strip today", "editorial cartoon funny"]
    hl, gl, ceid = locale(language)
    hinted: list[dict] = []
    other: list[dict] = []
    empty = None
    for query in queries:
        url = NEWS.format(q=urllib.parse.quote(query), hl=hl, gl=gl, ceid=ceid)
        try:
            rows = _fresh(items(fetch(url)), now=now, max_age=timedelta(hours=48))
        except _NET:
            continue
        for title, link, source, rss_image, _desc, source_url in rows[:12]:
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
            if picture and _usable_cartoon(picture):
                if _cartoon_hint(title, link, source):
                    hinted.append(row)
                else:
                    other.append(row)
            elif empty is None and not picture:
                empty = row
            if hinted:
                return [hinted[0]]
    if other:
        return [other[0]]
    return [empty] if empty else []


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
