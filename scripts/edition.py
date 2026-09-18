#!/usr/bin/env python3
"""Build the daily edition: markdown, Kindle EPUB, and a printer PDF."""
from __future__ import annotations

import html
import json
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

import pdf as pdf_mod
import schedule as schedule_mod

_DATE_SUFFIX = re.compile(r"\s*[—–-]\s*\d{1,2}/\d{1,2}\s*$")

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:language>{lang}</dc:language>
    <dc:identifier id="BookId">text-me-{day}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="body" href="body.html" media-type="application/xhtml+xml"/>
    {images}
  </manifest>
  <spine toc="ncx">
    <itemref idref="body"/>
  </spine>
</package>
"""

NCX = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="text-me-{day}"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    <navPoint id="start" playOrder="1"><navLabel><text>{title}</text></navLabel><content src="body.html"/></navPoint>
  </navMap>
</ncx>
"""


_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
_PAPER_CSS = (
    "@font-face{font-family:Textme;src:url(UnifrakturCook-Bold.ttf)}"
    "@font-face{font-family:Masthead;src:url(PlayfairDisplay-Bold.ttf);font-weight:700}"
    "@font-face{font-family:Masthead;src:url(PlayfairDisplay-Regular.ttf);font-weight:400}"
    "body{font-family:Georgia,'Palatino Linotype',serif;font-size:1.05em;line-height:1.65;"
    "margin:1em 1.15em;color:#1a1a1a}"
    "p.masthead{font-family:Textme,serif;font-size:2.7em;text-align:center;"
    "margin:.15em 0 .05em;line-height:1.05;color:#111}"
    "p.tagline{text-align:center;font-style:italic;font-size:.82em;margin:0 0 .35em;color:#444}"
    "h1{font-family:Georgia,'Palatino Linotype',serif;font-size:1.35em;font-weight:700;"
    "text-align:center;letter-spacing:.02em;line-height:1.2;"
    "border-top:4px double #111;border-bottom:1px solid #111;"
    "padding:.18em 0 .2em;margin:0}"
    "p.folio{text-align:center;font-variant:small-caps;letter-spacing:.16em;font-size:.78em;"
    "line-height:1.35;margin:.4em 0 1em;border-bottom:4px double #111;padding-bottom:.5em;"
    "font-family:Georgia,serif}"
    "h2{font-family:Georgia,serif;font-size:.78em;letter-spacing:.18em;font-weight:700;"
    "text-transform:uppercase;text-align:center;"
    "border-top:2px solid #111;border-bottom:1px solid #111;"
    "padding:.28em 0;margin:1.55em 0 .5em}"
    "h3{font-family:Georgia,serif;font-size:1.12em;font-weight:700;line-height:1.3;margin:.9em 0 .2em}"
    "p{line-height:1.65;margin:.32em 0}"
    "p.kicker{font-size:1.12em;line-height:1.55;text-align:center;margin:.2em 1.2em 1em}"
    "p.times{font-variant-numeric:tabular-nums;font-feature-settings:'tnum' 1;font-family:Georgia,'Liberation Serif',serif;letter-spacing:.02em}"
    "p.note{font-style:italic;text-align:center;font-size:.9em;line-height:1.45;margin:.45em 0 .8em}"
    "img{width:100%;height:auto;margin:.5em 0;border:1px solid #111;padding:2px}"
)


def font_files() -> list[tuple[str, bytes, str]]:
    out: list[tuple[str, bytes, str]] = []
    for name in ("UnifrakturCook-Bold.ttf", "PlayfairDisplay-Bold.ttf", "PlayfairDisplay-Regular.ttf"):
        path = _FONT_DIR / name
        if not path.exists():
            path = Path("/opt/matriz/fonts") / name
        if path.exists():
            out.append((name, path.read_bytes(), "application/x-font-ttf"))
    return out


def md_to_html(md: str) -> str:
    pt = any(
        bit in md.casefold()
        for bit in ("reporte", "hoje em uma frase", "próximas", "charge do dia")
    )
    tagline = (
        "Teus planos no papel, pra não ter que guardar na cabeça."
        if pt
        else "Your plans on paper, so you don't have to keep them in your head."
    )
    lines = []
    prev = ""
    masthead = False
    for raw in md.splitlines():
        line = raw
        stripped_raw = raw.strip()
        if stripped_raw == "---":
            lines.append('<div style="page-break-before:always"></div>')
            prev = "break"
            continue
        pictured = _IMG.search(raw)
        if pictured:
            alt = html.escape(pictured.group(1))
            src = html.escape(pictured.group(2))
            lines.append(
                f'<p style="page-break-before:always"><img alt="{alt}" src="{src}"/></p>'
            )
            prev = "img"
            continue
        line = html.escape(raw)
        stripped = line.strip()
        if line.startswith("### "):
            lines.append(f"<h3>{line[4:]}</h3>")
            prev = "h3"
        elif line.startswith("## "):
            lines.append(f"<h2>{line[3:]}</h2>")
            prev = "h2"
        elif line.startswith("# "):
            if not masthead:
                lines.append('<p class="masthead">The Text-me</p>')
                lines.append(f'<p class="tagline">{html.escape(tagline)}</p>')
                masthead = True
            lines.append(f"<h1>{line[2:]}</h1>")
            prev = "h1"
        elif stripped_raw.startswith("- "):
            body = html.escape(stripped_raw[2:])
            cls = "times" if re.match(r"\d{1,2}:\d{2}", stripped_raw[2:]) else ""
            attr = f' class="{cls}"' if cls else ""
            lines.append(f"<p{attr}>• {body}</p>")
            prev = "p"
        elif stripped_raw.startswith("_") and stripped_raw.endswith("_") and len(stripped_raw) > 2:
            cls = "folio" if prev == "h1" else "note"
            lines.append(f'<p class="{cls}">{html.escape(stripped_raw[1:-1])}</p>')
            prev = "p"
        elif stripped_raw.startswith("> "):
            lines.append(f'<p class="kicker">{html.escape(stripped_raw[2:])}</p>')
            prev = "p"
        elif not stripped:
            lines.append("<p></p>")
        else:
            lines.append(f"<p>{line}</p>")
            prev = "p"
    body = "\n".join(lines)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head><title>text-me</title>"
        f'<style type="text/css">{_PAPER_CSS}</style></head><body>'
        f"{body}</body></html>"
    )


def write_epub(
    path: Path,
    title: str,
    markdown: str,
    day: str,
    images: list[tuple[str, bytes, str]] | None = None,
    lang: str = "en",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    images = list(images or []) + font_files()
    manifest = "\n    ".join(
        f'<item id="img{i}" href="{html.escape(name)}" media-type="{mime}"/>'
        for i, (name, _data, mime) in enumerate(images)
    )
    xhtml = md_to_html(markdown)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr(
            "OEBPS/content.opf",
            OPF.format(title=html.escape(title), day=day, lang=html.escape(lang[:8] or "en"), images=manifest),
        )
        zf.writestr("OEBPS/toc.ncx", NCX.format(title=html.escape(title), day=day))
        zf.writestr("OEBPS/body.html", xhtml)
        for name, data, _mime in images:
            zf.writestr(f"OEBPS/{name}", data)


def as_of(when: datetime | None = None) -> datetime:
    """The edition's day is their clock, not UTC and not 'tomorrow'.

    An aware `when` already is someone's local time — keep that date.
    Naive/now fall back to their profile timezone, then the image TZ.
    """
    zone = schedule_mod.zone()
    if when is None:
        return datetime.now(zone)
    if when.tzinfo is None:
        return when.replace(tzinfo=zone)
    return when


def default_title(pt: bool, when: datetime) -> str:
    """A name the Kindle library can hold on to — not a bare date.

    One language only: Portuguese page, Portuguese title. Never "Report".
    """
    when = as_of(when)
    if pt:
        return f"Seu Reporte Diário — {when.strftime('%d/%m')}"
    return f"Your Daily Report — {when.strftime('%b %d')}"


PT_DAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
PT_MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
EN_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def folio(pt: bool, when: datetime) -> str:
    """The dateline under the masthead, like a printed front page."""
    when = as_of(when)
    if pt:
        return f"{PT_DAYS[when.weekday()]}, {when.day} de {PT_MONTHS[when.month - 1]} de {when.year} · edição da manhã"
    return f"{EN_DAYS[when.weekday()]}, {EN_MONTHS[when.month - 1]} {when.day}, {when.year} · morning edition"


def stamp_title(pt: bool, when: datetime, extra: dict | None = None) -> str:
    """Keep a custom name; the dd/mm is always the local day of `when`."""
    when = as_of(when)
    custom = ((extra or {}).get("title") or "").strip()
    if custom:
        custom = _DATE_SUFFIX.sub("", custom).strip()
        if custom:
            if pt:
                custom = re.sub(r"\bReport\b", "Reporte", custom)
                return f"{custom} — {when.strftime('%d/%m')}"
            return f"{custom} — {when.strftime('%b %d')}"
    return default_title(pt, when)


QUADRANT_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}


def first_name(state: dict) -> str:
    name = ((state.get("profile") or {}).get("name") or "").strip()
    return name.split()[0] if name else ""


def voice(text: str, state: dict, pt: bool) -> str:
    """Body copy talks to them (tu/you). Never 'the user', never their name in the third person."""
    you = "tu" if pt else "you"
    out = re.sub(r"\b(?:[ao] |d[ao] )?usuário\b", you, text or "", flags=re.I)
    out = re.sub(r"\b(?:the )?user\b", you, out, flags=re.I)
    name = first_name(state)
    if name:
        out = re.sub(rf"\b{re.escape(name)}\b", "", out, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+,", ",", out)
    return out.strip(" ,")


def _mins(hhmm: str) -> int | None:
    bits = hhmm.split(":")
    if len(bits) != 2 or not bits[0].isdigit() or not bits[1].isdigit():
        return None
    return int(bits[0]) * 60 + int(bits[1])


_SLOT = re.compile(r"^(\d{1,2}:\d{2})[–-](\d{1,2}:\d{2})\s+(.*)$")
_CLOCK = re.compile(r"\b(\d{1,2}:\d{2})\b")


def decision_due(item, pt: bool) -> str:
    if isinstance(item, dict) and (item.get("due") or "").strip():
        return item["due"].strip()
    clock = _CLOCK.search(_item_text(item))
    if clock:
        return clock.group(1)
    return "hoje" if pt else "today"


def agenda_rows(meetings: list, pt: bool) -> list[str]:
    parsed = []
    for raw in meetings or []:
        line = str(raw).strip()
        match = _SLOT.match(line)
        if not match:
            parsed.append((None, None, line))
            continue
        parsed.append((match.group(1), match.group(2), match.group(3).strip()))
    out = []
    for i, (start, end, title) in enumerate(parsed):
        tags = []
        blob = title.casefold()
        if any(w in blob for w in ("volta", "ônibus", "onibus", "desloc", "casa", "commute", "bus", "metro")):
            tags.append("deslocamento" if pt else "commute")
        if any(w in blob for w in ("estud", "prepar", "ensaio", "revis")):
            tags.append("preparo" if pt else "prep")
        if start and end:
            a0, a1 = _mins(start), _mins(end)
            if i + 1 < len(parsed) and parsed[i + 1][0]:
                b0 = _mins(parsed[i + 1][0])
                if a1 is not None and b0 is not None and b0 < a1:
                    tags.append("conflito" if pt else "conflict")
            stamp = f"{start}–{end}"
            extra = f"  · {', '.join(tags)}" if tags else ""
            out.append(f"- {stamp}  {title}{extra}")
        else:
            out.append(f"- {title}")
    return out


def overdue(task: dict, when: datetime) -> bool:
    due = (task.get("due") or "").strip()
    if not due:
        return False
    try:
        return due[:10] < when.date().isoformat()
    except (TypeError, ValueError):
        return False


def person_line(item, pt: bool) -> str | None:
    who = ""
    text = _item_text(item)
    if isinstance(item, dict):
        who = (item.get("who") or "").strip()
    if not who or any(x in who.lower() for x in ("noreply", "no-reply", "mailer")):
        return None
    action = "responder" if pt else "reply"
    summary = ""
    if isinstance(item, dict):
        summary = (item.get("summary") or "").strip()
    ctx = summary or text
    if similar(ctx, who):
        ctx = text
    return f"- {who} — {ctx} — {action}"


def delay_notes(state: dict, pt: bool) -> list[str]:
    out = []
    for key, entry in (state.get("durations") or {}).items():
        asked = [int(x) for x in (entry.get("asked") or []) if int(x) > 0]
        actual = [int(x) for x in (entry.get("actual") or []) if int(x) > 0]
        if not asked or not actual:
            continue
        if actual[-1] > asked[-1] + 10:
            if pt:
                out.append(f"- {key}: da última vez levou {actual[-1]} min, não {asked[-1]}. Bloqueia {actual[-1]}.")
            else:
                out.append(f"- {key}: last time took {actual[-1]} min, not {asked[-1]}. Block {actual[-1]}.")
        if len(out) >= 2:
            break
    return out


def word_search(words: list[str], size: int = 8) -> tuple[list[str], list[str]]:
    cleaned = []
    for word in words:
        folded = unicodedata.normalize("NFKD", word or "").encode("ascii", "ignore").decode().upper()
        token = re.sub(r"[^A-Z]", "", folded)
        if 3 <= len(token) <= size and token not in cleaned:
            cleaned.append(token)
        if len(cleaned) >= 5:
            break
    if len(cleaned) < 3:
        return [], []
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    seed = sum(ord(ch) for ch in "".join(cleaned))
    grid = [[alphabet[(seed + r * 11 + c * 17) % 26] for c in range(size)] for r in range(size)]
    for i, word in enumerate(cleaned):
        if i >= size:
            break
        for j, ch in enumerate(word):
            if j < size:
                grid[i][j] = ch
    return [" ".join(row) for row in grid], cleaned


def kicker_line(state: dict, extra: dict, active: list[dict], pt: bool) -> str:
    if extra.get("kicker"):
        return voice(str(extra["kicker"]), state, pt)
    name = first_name(state)
    q1 = next((t for t in active if t.get("quadrant") == "Q1"), None)
    meetings = extra.get("meetings") or []
    if q1:
        core = voice(q1.get("text") or "", state, pt)
    elif (state.get("goals") or {}).get("work"):
        core = voice(state["goals"]["work"], state, pt)
    elif meetings:
        core = str(meetings[0]).split("  ", 1)[-1]
    else:
        core = "o que está na mesa" if pt else "what is on the plate"
    core = core.strip()
    first = core.split()[0] if core else ""
    if first and first[0].isupper() and not first.isupper():
        core = core[0].lower() + core[1:]
    if pt:
        who = f"{name}, " if name else ""
        return f"{who}hoje o que importa é {core}."
    who = f"{name}, " if name else ""
    return f"{who}today the focus is {core}."


def unique_push(shown: list[str], text: str) -> bool:
    if not text or any(similar(text, s) for s in shown):
        return False
    shown.append(text)
    return True


def _clocks_in(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"\b\d{1,2}h\d{2}\b|\b\d{1,2}:\d{2}\b", text or ""):
        if "h" in raw.casefold() and ":" not in raw:
            h, m = raw.casefold().split("h", 1)
            stamp = f"{int(h):02d}:{m}"
        else:
            h, m = raw.split(":", 1)
            stamp = f"{int(h):02d}:{m}"
        if stamp in seen:
            continue
        seen.add(stamp)
        found.append(stamp)
    return found


def _show_clock(hhmm: str, pt: bool) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)}h{m}" if pt else hhmm


def _task_window(task: dict, meetings: list | None) -> tuple[str, str] | None:
    tokens = [w for w in re.findall(r"[a-zà-ÿ]{4,}", (task.get("text") or "").casefold())]
    for raw in meetings or []:
        match = _SLOT.match(str(raw).strip())
        if not match:
            continue
        title = match.group(3).casefold()
        if tokens and sum(1 for w in tokens if w in title) >= min(2, len(tokens)):
            return match.group(1), match.group(2)
    clocks = _clocks_in(task.get("reason") or "")
    if len(clocks) >= 2:
        return clocks[0], clocks[1]
    return None


def _due_stamp(task: dict, when: datetime | None, pt: bool) -> str:
    due = (task.get("due") or "").strip()
    if not due or when is None:
        return ""
    try:
        if due[:10] == when.date().isoformat():
            return ""
    except (TypeError, ValueError):
        pass
    return ("até " if pt else "due ") + due


def focus_lines(
    active: list[dict],
    pt: bool,
    when: datetime | None = None,
    meetings: list | None = None,
) -> list[str]:
    """What matters, in order — Q1 first. A window if we have one, never third person."""
    ranked = sorted(
        active,
        key=lambda t: (
            QUADRANT_ORDER.get(t.get("quadrant") or "", 9),
            not (t.get("due") or "").strip(),
            t.get("due") or "",
        ),
    )
    out = []
    for task in ranked[:6]:
        bits = [re.sub(r"^Q[1-4]\s+", "", (task.get("text") or "").strip())]
        window = _task_window(task, meetings)
        if window:
            start, end = _show_clock(window[0], pt), _show_clock(window[1], pt)
            bits.append(
                f"necessário: janela das {start} às {end}"
                if pt
                else f"needed: window {start}–{end}"
            )
        else:
            extra_due = _due_stamp(task, when, pt)
            if extra_due:
                bits.append(extra_due)
            reason = (task.get("reason") or "").strip()
            blob = reason.casefold()
            if (
                reason
                and len(reason) <= 80
                and not any(
                    w in blob
                    for w in ("precisa", "só tem", "so tem", "usuário", "usuario", "the user")
                )
            ):
                bits.append(reason)
        out.append(" — ".join(b for b in bits if b))
    return out


def _day_musts(meetings: list | None, pt: bool, shown: list[str]) -> list[str]:
    """The day's real commitments, minus commute and meals already on the agenda."""
    skip_w = (
        "desloc", "volta pra", "volta para", "commute", "ônibus", "onibus",
        "almoço", "almoco", "lunch", "café", "cafe da",
    )
    out = []
    for raw in meetings or []:
        match = _SLOT.match(str(raw).strip())
        if not match:
            continue
        start, end, title = match.group(1), match.group(2), match.group(3).strip()
        title = re.sub(r"\s+·\s+.*$", "", title).strip()
        if any(w in title.casefold() for w in skip_w):
            continue
        start_s, end_s = _show_clock(start, pt), _show_clock(end, pt)
        line = f"{title} — {start_s} às {end_s}" if pt else f"{title} — {start_s}–{end_s}"
        if unique_push(shown, line):
            out.append(line)
        if len(out) >= 5:
            break
    return out


def hold_line(state: dict, extra: dict | None = None, category: str = "work") -> str:
    extra = extra or {}
    key = "hold" if category == "work" else f"hold_{category}"
    if extra.get(key):
        return str(extra[key]).strip()
    if category == "work" and extra.get("hold"):
        return str(extra["hold"]).strip()
    goals = state.get("goals") or {}
    if (goals.get(category) or "").strip():
        return str(goals[category]).strip()
    active = [t for t in state.get("tasks") or [] if not t.get("done") and t.get("category") == category]
    for want in ("Q2", "Q1"):
        for task in active:
            if task.get("quadrant") == want and (task.get("text") or "").strip():
                return task["text"].strip()
    return ""


def _sig(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().casefold()
    return set(re.findall(r"[0-9a-z]{4,}", folded))


def similar(a: str, b: str) -> bool:
    """The same commitment worded twice — goal vs task vs block."""
    sa, sb = _sig(a), _sig(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / min(len(sa), len(sb)) >= 0.6


def _item_text(item) -> str:
    if not isinstance(item, dict):
        return str(item)
    text = item.get("text") or ""
    summary = (item.get("summary") or "").strip()
    if summary and summary.casefold() not in text.casefold():
        return f"{text} — {summary}"
    return text


def _item_sphere(item) -> str:
    return (item.get("sphere") or "") if isinstance(item, dict) else ""


def _by_sphere(items: list) -> dict[str, list[str]]:
    out = {"work": [], "life": [], "": []}
    for item in items or []:
        out.setdefault(_item_sphere(item), []).append(_item_text(item))
    return out


def _clip_block(item, pt: bool) -> list[str]:
    if not isinstance(item, dict):
        return [f"- {item}"]
    title = (item.get("title") or item.get("line") or "").strip()
    happened = (item.get("happened") or item.get("summary") or "").strip()
    why = (item.get("why") or "").strip()
    source = (item.get("source") or "").strip()
    if not happened and not why:
        line = title
        if source and source.casefold() not in line.casefold():
            line = f"{line} — {source}"
        return [f"- {line}"] if line else []
    if happened and len(happened) < 40:
        return []
    out = [f"### {title}"] if title else []
    if happened:
        out.append(("O que aconteceu: " if pt else "What happened: ") + happened)
    if why:
        out.append(("Porque te importa: " if pt else "Why it matters: ") + why)
    if source and source.casefold() not in (title + " " + happened).casefold():
        out.append(("Fonte: " if pt else "Source: ") + source)
    return out


def _clip_title(item) -> str:
    if isinstance(item, dict):
        return (item.get("title") or item.get("line") or item.get("text") or "").strip()
    return str(item).strip()


def day_board(extra: dict, pt: bool, limit: int = 3) -> list[str]:
    """Compact Founder-style lanes. Empty lanes stay off the page."""
    extra = extra or {}
    lanes = [
        ("handled", extra.get("handled") or extra.get("exceptions") or extra.get("changes") or [],
         "Feito" if pt else "Handled"),
        ("prepared", extra.get("prepared") or extra.get("focus") or [],
         "Preparado" if pt else "Prepared"),
        ("needs", extra.get("approvals") or extra.get("decisions") or extra.get("fires") or extra.get("needs") or [],
         "Precisa de ti" if pt else "Needs you"),
        ("watching", extra.get("watching") or extra.get("clips") or [],
         "A acompanhar" if pt else "Watching"),
    ]
    blocks: list[str] = []
    seen: list[str] = []
    for _key, items, label in lanes:
        bits = []
        for item in items:
            text = _clip_title(item) if _key == "watching" else _item_text(item)
            text = re.sub(r"^Q[1-4]\s+", "", str(text or "").strip())
            if not text or not unique_push(seen, text):
                continue
            bits.append(text)
            if len(bits) >= limit:
                break
        if bits:
            blocks.append(f"**{label}:** " + "; ".join(bits))
    if not blocks:
        return []
    heading = "## " + ("O dia" if pt else "The day")
    return [heading, *blocks, ""]


def compose(state: dict, when: datetime, extra: dict | None = None) -> str:
    extra = extra or {}
    lang = (state.get("language") or "").lower()
    pt = lang.startswith("pt")
    profile = state.get("profile") or {}
    active = [t for t in state.get("tasks") or [] if not t.get("done")]
    title = stamp_title(pt, when, extra)
    shown: list[str] = []
    lines = [f"# {title}", "", f"_{folio(pt, when)}_", ""]

    kicker = kicker_line(state, extra, active, pt)
    lines.append("## " + ("Hoje em uma frase" if pt else "Today in one sentence"))
    lines.append(f"> {kicker}")
    lines.append("")
    lines.extend(day_board(extra, pt))

    meetings = extra.get("meetings") or []
    rows = agenda_rows(meetings, pt)
    if rows:
        lines.append("## Agenda")
        lines.extend(rows)
        lines.append("")

    decisions = extra.get("approvals") or extra.get("decisions") or []
    dec_lines = []
    for item in decisions:
        text = voice(_item_text(item), state, pt)
        if not unique_push(shown, text):
            continue
        due = (" · prazo " if pt else " · due ") + decision_due(item, pt)
        dec_lines.append(f"- {text}{due}")
        if len(dec_lines) >= 3:
            break
    if dec_lines:
        lines.append("## " + ("Decisões" if pt else "Decisions"))
        lines.extend(dec_lines)
        lines.append("")

    risks = []
    for task in active:
        if not overdue(task, when):
            continue
        bit = voice(task.get("text") or "", state, pt)
        bit += (" · atrasado" if pt else " · overdue")
        if unique_push(shown, bit):
            risks.append(f"- {bit}")
    for item in extra.get("fires") or extra.get("needs") or []:
        bit = voice(_item_text(item), state, pt)
        if unique_push(shown, bit):
            why = ""
            if isinstance(item, dict) and item.get("why") == "pay":
                why = " · " + ("vencendo" if pt else "due")
            elif isinstance(item, dict) and not (item.get("who") or "").strip():
                why = " · " + ("sem dono" if pt else "no owner")
            risks.append(f"- {bit}{why}")
    if risks:
        lines.append("## " + ("Riscos e bloqueios" if pt else "Risks and blockers"))
        lines.extend(risks)
        lines.append("")

    changes = extra.get("exceptions") or extra.get("changes") or []
    if changes:
        lines.append("## " + ("Mudanças desde ontem" if pt else "What changed"))
        for item in changes:
            text = voice(str(item), state, pt)
            if unique_push(shown, text):
                lines.append(f"- {text}")
        lines.append("")

    people = extra.get("people") or []
    if not people:
        people = (extra.get("approvals") or []) + (extra.get("fires") or extra.get("needs") or [])
    people_lines = []
    people_seen: list[str] = []
    for item in people:
        row = person_line(item, pt)
        if not row:
            continue
        if unique_push(people_seen, row):
            people_lines.append(row)
    if people_lines:
        lines.append("## " + ("Pessoas" if pt else "People"))
        lines.extend(people_lines[:6])
        lines.append("")

    next_lines = []
    ranked = extra.get("focus") or focus_lines(active, pt, when, meetings)
    for item in ranked:
        text = voice(str(item), state, pt)
        text = re.sub(r"^Q[1-4]\s+", "", text)
        if unique_push(shown, text):
            next_lines.append(f"- {text}")
        if len(next_lines) >= 5:
            break
    if not extra.get("focus"):
        for line in _day_musts(meetings, pt, shown):
            next_lines.append(f"- {line}")
            if len(next_lines) >= 6:
                break
    next_lines.extend(delay_notes(state, pt))
    if next_lines:
        lines.append("## " + ("Próximas ações" if pt else "Next actions"))
        lines.extend(next_lines)
        lines.append("")

    radar = extra.get("clips") or []
    if radar:
        lines.append("## " + ("No radar" if pt else "On the radar"))
        for item in radar[:8]:
            lines.extend(_clip_block(item, pt))
        lines.append("")

    cartoon = extra.get("charge") or []
    has_picture = False
    if cartoon:
        lines.append("---")
        lines.append("## " + ("Charge do dia" if pt else "Cartoon of the day"))
        for item in cartoon:
            if isinstance(item, dict):
                caption = item.get("line") or item.get("title") or ""
                if item.get("file"):
                    has_picture = True
                    lines.append(f"![Charge]({item['file']})")
                    if caption:
                        lines.append(f"_{caption}_")
                elif caption:
                    lines.append(f"- {caption}")
            else:
                lines.append(f"- {item}")
        lines.append("")
    if not has_picture:
        grid, found = word_search(
            [t.get("text") or "" for t in active]
            + [str(m) for m in meetings]
            + [first_name(state), "matriz"],
        )
        if grid:
            lines.append("## " + ("Caça-palavras" if pt else "Word search"))
            for row in grid:
                lines.append(f"- {row}")
            lines.append("_" + ("palavras: " if pt else "words: ") + ", ".join(found) + "_")
            lines.append("")

    readings = extra.get("readings") or []
    hobbies = extra.get("hobbies") or []
    if readings:
        lines.append("## " + ("Leituras" if pt else "Readings"))
        for item in readings:
            lines.append(f"- {item}")
        lines.append("")
    if hobbies:
        lines.append("## " + ("Hobbies" if pt else "Hobbies"))
        for item in hobbies:
            lines.append(f"- {item}")
        lines.append("")
    avoid = profile.get("avoid") or []
    if avoid:
        lines.append("_" + ("Fora desta edição: " if pt else "Kept out of this edition: ") + ", ".join(avoid) + "_")
    return "\n".join(lines).rstrip() + "\n"


def _jpeg(data: bytes) -> bytes:
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(data)).convert("RGB")
    max_w, max_h = 900, 700
    scale = min(max_w / img.width, max_h / img.height, 1.0)
    if scale < 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True, progressive=False)
    return buf.getvalue()


def dump(state: dict, dest_dir: Path, when: datetime, extra: dict | None = None) -> dict:
    extra = extra or {}
    when = as_of(when)
    day = when.date().isoformat()
    dest_dir.mkdir(parents=True, exist_ok=True)
    packed: list[tuple[str, bytes, str]] = []
    charge_rows = []
    for i, item in enumerate(extra.get("charge") or []):
        if not isinstance(item, dict):
            charge_rows.append(item)
            continue
        row = dict(item)
        blob = row.pop("image", None) or b""
        if blob:
            name = f"charge-{i}.jpg"
            jpeg = _jpeg(blob)
            (dest_dir / name).write_bytes(jpeg)
            row["file"] = name
            packed.append((name, jpeg, "image/jpeg"))
        charge_rows.append(row)
    extra = {**extra, "charge": charge_rows}
    markdown = compose(state, when, extra)
    md_path = dest_dir / f"{day}.md"
    epub_path = dest_dir / f"{day}.epub"
    pdf_path = dest_dir / f"{day}.pdf"
    md_path.write_text(markdown, encoding="utf-8")
    lang = (state.get("language") or "en")[:8]
    pt = lang.lower().startswith("pt")
    title = stamp_title(pt, when, extra)
    write_epub(epub_path, title, markdown, day, packed, lang=lang or "en")
    pdf_mod.write_pdf(pdf_path, markdown, images={name: data for name, data, _mime in packed})
    return {
        "day": day,
        "title": title,
        "markdown": str(md_path),
        "epub": str(epub_path),
        "pdf": str(pdf_path),
        "delivery": (state.get("profile") or {}).get("delivery") or "message",
        "bytes": epub_path.stat().st_size,
        "pdf_bytes": pdf_path.stat().st_size,
    }
