#!/usr/bin/env python3
"""Build the daily edition: markdown, Kindle EPUB, and a printer PDF."""
from __future__ import annotations

import html
import json
import re
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
    <dc:language>en</dc:language>
    <dc:identifier id="BookId">text-me-{day}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="body" href="body.html" media-type="application/xhtml+xml"/>
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


def md_to_html(md: str) -> str:
    lines = []
    for raw in md.splitlines():
        line = html.escape(raw)
        if line.startswith("### "):
            lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            lines.append(f"<p>• {line[2:]}</p>")
        elif not line.strip():
            lines.append("<p></p>")
        else:
            lines.append(f"<p>{line}</p>")
    body = "\n".join(lines)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        f"<head><title>text-me</title></head><body>{body}</body></html>"
    )


def write_epub(path: Path, title: str, markdown: str, day: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xhtml = md_to_html(markdown)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", OPF.format(title=html.escape(title), day=day))
        zf.writestr("OEBPS/toc.ncx", NCX.format(title=html.escape(title), day=day))
        zf.writestr("OEBPS/body.html", xhtml)


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
    """A name the Kindle library can hold on to — not a bare date."""
    when = as_of(when)
    if pt:
        return f"Seu Report Diário — {when.strftime('%d/%m')}"
    return f"Your Daily Report — {when.strftime('%b %d')}"


def stamp_title(pt: bool, when: datetime, extra: dict | None = None) -> str:
    """Keep a custom name; the dd/mm is always the local day of `when`."""
    when = as_of(when)
    custom = ((extra or {}).get("title") or "").strip()
    if custom:
        custom = _DATE_SUFFIX.sub("", custom).strip()
        if custom:
            if pt:
                return f"{custom} — {when.strftime('%d/%m')}"
            return f"{custom} — {when.strftime('%b %d')}"
    return default_title(pt, when)


QUADRANT_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}


def focus_lines(active: list[dict], pt: bool) -> list[str]:
    """What matters, in order of what matters — Q1 first, never by clock."""
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
        bits = [f"{task.get('quadrant', '')} {task.get('text', '')}".strip()]
        if (task.get("due") or "").strip():
            bits.append(("até " if pt else "due ") + task["due"].strip())
        if (task.get("reason") or "").strip():
            bits.append(task["reason"].strip())
        out.append(" — ".join(bits))
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


def compose(state: dict, when: datetime, extra: dict | None = None) -> str:
    extra = extra or {}
    lang = (state.get("language") or "").lower()
    pt = lang.startswith("pt")
    profile = state.get("profile") or {}
    goals = state.get("goals") or {}
    active = [t for t in state.get("tasks") or [] if not t.get("done")]
    open_blocks = [b for b in state.get("blocks") or [] if b.get("status") != "done"]
    title = stamp_title(pt, when, extra)
    lines = [f"# {title}", ""]
    fires = extra.get("fires") or extra.get("needs") or []
    split = _by_sphere(fires)
    lines.append("## " + ("O que precisa de ti hoje" if pt else "What needs you today"))
    work_l = "Trabalho" if pt else "Work"
    life_l = "Vida" if pt else "Life"
    if split["work"] or split["life"]:
        for text in split["work"]:
            lines.append(f"- {work_l}: {text}")
        for text in split["life"]:
            lines.append(f"- {life_l}: {text}")
        for text in split.get("", []) :
            lines.append(f"- {text}")
    else:
        lines.append(
            "- "
            + (
                "Nada na caixa bate com o que tu marcaste como trabalho ou vida."
                if pt
                else "Nothing in the inbox matches what you marked as work or life."
            )
        )
    lines.append("")
    exceptions = extra.get("exceptions") or []
    lines.append("## " + ("Agenda que mudou" if pt else "Calendar that moved"))
    if exceptions:
        for item in exceptions:
            lines.append(f"- {item}")
    else:
        lines.append("- " + ("Nenhuma mudança na agenda." if pt else "No calendar changes."))
    lines.append("")
    approvals = extra.get("approvals") or []
    lines.append("## " + ("Sim que chegou no e-mail" if pt else "A yes waiting in email"))
    split_yes = _by_sphere(approvals)
    if split_yes["work"] or split_yes["life"] or split_yes.get(""):
        for text in split_yes["work"]:
            lines.append(f"- {work_l}: {text}")
        for text in split_yes["life"]:
            lines.append(f"- {life_l}: {text}")
        for text in split_yes.get("", []):
            lines.append(f"- {text}")
    else:
        lines.append("- " + ("Ninguém esperando um sim na caixa." if pt else "Nobody waiting on a yes in the inbox."))
    lines.append("")
    hold_work = hold_line(state, extra, "work")
    hold_life = hold_line(state, extra, "life")
    lines.append("## " + ("Não larga hoje" if pt else "Do not drop today"))
    if hold_work:
        lines.append(f"- {work_l}: {hold_work}")
    if hold_life:
        lines.append(f"- {life_l}: {hold_life}")
    if not hold_work and not hold_life:
        lines.append(
            "- "
            + (
                "Ainda não tem. Diz a meta de trabalho e a de vida."
                if pt
                else "None yet. Set a work goal and a life goal."
            )
        )
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
    meetings = extra.get("meetings") or []
    lines.append("## " + ("Hoje na agenda" if pt else "On the calendar"))
    if meetings:
        for item in meetings:
            lines.append(f"- {item}")
    else:
        lines.append("- " + ("Nada lido da agenda ainda — manda os horários no chat se o Google não estiver ligado." if pt else "No calendar read yet — text the times if Google is not connected."))
    lines.append("")
    lines.append("## " + ("O que importa hoje" if pt else "What matters today"))
    focus = extra.get("focus") or []
    if not focus:
        focus = focus_lines(active, pt)
    if not focus:
        if goals.get("work"):
            focus.append(("Trabalho: " if pt else "Work: ") + goals["work"])
        if goals.get("life"):
            focus.append(("Vida: " if pt else "Life: ") + goals["life"])
    for item in focus or ["—" ]:
        lines.append(f"- {item}")
    lines.append("")
    if open_blocks:
        lines.append("## " + ("Blocos em andamento" if pt else "Open blocks"))
        for block in open_blocks:
            extra_min = sum(int(x) for x in block.get("extensions") or [])
            lines.append(
                f"- {block.get('text')} · "
                f"{block.get('planned_minutes')} min"
                + (f" +{extra_min}" if extra_min else "")
            )
        lines.append("")
    interests = extra.get("clips") or []
    if interests:
        lines.append("## " + ("Pra começar o dia" if pt else "To start the day"))
        for item in interests:
            lines.append(f"- {item}")
        lines.append("")
    avoid = profile.get("avoid") or []
    if avoid:
        lines.append("_" + ("Fora desta edição: " if pt else "Kept out of this edition: ") + ", ".join(avoid) + "_")
    return "\n".join(lines).rstrip() + "\n"


def dump(state: dict, dest_dir: Path, when: datetime, extra: dict | None = None) -> dict:
    extra = extra or {}
    when = as_of(when)
    day = when.date().isoformat()
    markdown = compose(state, when, extra)
    dest_dir.mkdir(parents=True, exist_ok=True)
    md_path = dest_dir / f"{day}.md"
    epub_path = dest_dir / f"{day}.epub"
    pdf_path = dest_dir / f"{day}.pdf"
    md_path.write_text(markdown, encoding="utf-8")
    pt = (state.get("language") or "").lower().startswith("pt")
    title = stamp_title(pt, when, extra)
    write_epub(epub_path, title, markdown, day)
    pdf_mod.write_pdf(pdf_path, markdown)
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
