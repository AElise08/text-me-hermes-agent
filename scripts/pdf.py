#!/usr/bin/env python3
"""Print-first newspaper renderer for the text-me daily report.

Masthead in blackletter, warm paper, one language on the whole sheet.
The right rail answers what they need to do today — their work, not a
textbook matrix. Agenda and news fill the remaining columns.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A4 = (1240, 1754)
M = 52
BOTTOM = 78
PAPER = (246, 242, 230)
INK = (27, 25, 21)
MUTED = (85, 80, 70)
RULE = (55, 51, 43)
HERE = Path(__file__).resolve().parent
FONT_DIRS = (
    HERE.parent / "fonts",
    Path("/opt/matriz/fonts"),
    Path("/usr/share/fonts/opentype/urw-base35"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
)
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
SLOT = re.compile(r"^(\d{1,2}:\d{2})[–-](\d{1,2}:\d{2})\s+(.*)$")

PT = {
    "tagline": "Teus planos no papel, pra não ter que guardar na cabeça.",
    "masthead": "The Text-me",
    "vol": "ANO 1",
    "page": "PÁG.",
    "footer": "THE TEXT-ME",
    "todo": "O que preciso fazer hoje",
    "cartoon": "A charge do dia",
    "lead": "Hoje em uma frase",
}
EN = {
    "tagline": "Your plans on paper, so you don't have to keep them in your head.",
    "masthead": "The Text-me",
    "vol": "VOL. 1",
    "page": "PAGE",
    "footer": "THE TEXT-ME",
    "todo": "What I need to do today",
    "cartoon": "Cartoon of the day",
    "lead": "Today in one sentence",
}


def _first(*names):
    for folder in FONT_DIRS:
        for name in names:
            path = folder / name
            if path.exists():
                return path
    return None


def _font(size, *names):
    path = _first(*names)
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default()


MAST = _font(64, "UnifrakturCook-Bold.ttf", "PlayfairDisplay-Bold.ttf")
DEK = _font(40, "PlayfairDisplay-Bold.ttf", "DejaVuSerif-Bold.ttf")
HED = _font(28, "PlayfairDisplay-Bold.ttf", "DejaVuSerif-Bold.ttf")
BODY = _font(22, "PlayfairDisplay-Regular.ttf", "NimbusRoman-Regular.otf", "DejaVuSerif.ttf")
BODY_BOLD = _font(22, "PlayfairDisplay-Bold.ttf", "NimbusRoman-Bold.otf", "DejaVuSerif-Bold.ttf")
ITALIC = _font(17, "NimbusRoman-Italic.otf", "DejaVuSerif-Italic.ttf", "LiberationSerif-Italic.ttf")
SMALL = _font(19, "PlayfairDisplay-Regular.ttf", "NimbusRoman-Regular.otf", "DejaVuSerif.ttf")
LABEL = _font(13, "NimbusSansNarrow-Bold.otf", "DejaVuSansCondensed-Bold.ttf", "LiberationSans-Bold.ttf")
TIME = _font(24, "NimbusRoman-Bold.otf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf")
ACTION = _font(26, "PlayfairDisplay-Regular.ttf", "NimbusRoman-Regular.otf", "DejaVuSerif.ttf")
ACTION_BOLD = _font(26, "PlayfairDisplay-Bold.ttf", "NimbusRoman-Bold.otf", "DejaVuSerif-Bold.ttf")


class Block:
    def __init__(self, kind, text, image=None):
        self.kind = kind
        self.text = text
        self.image = image


def chrome(markdown: str) -> dict:
    blob = markdown.casefold()
    if any(
        bit in blob
        for bit in (
            "reporte",
            "edição",
            "hoje em uma frase",
            "próximas",
            "charge do dia",
            "porque te importa",
        )
    ):
        return PT
    return EN


def _wrap(draw, text, font, width):
    out = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=font) <= width:
                line = trial
            else:
                if line:
                    out.append(line)
                line = word
        if line:
            out.append(line)
        if not paragraph.strip():
            out.append("")
    return out or [""]


def _rule(d, x1, y, x2, width=1):
    d.line((x1, y, x2, y), fill=RULE, width=width)


def _label(d, x, y, text, width):
    d.text((x, y), str(text).upper(), font=LABEL, fill=MUTED)
    _rule(d, x, y + 19, x + width)
    return y + 28


def _header(d, page, title, folio, copy):
    tagline = copy["tagline"]
    d.text(((A4[0] - d.textlength(tagline, font=ITALIC)) / 2, 16), tagline, font=ITALIC, fill=MUTED)
    mast = copy["masthead"]
    d.text(((A4[0] - d.textlength(mast, font=MAST)) / 2, 38), mast, font=MAST, fill=INK)
    _rule(d, M, 128, A4[0] - M, 3)
    meta = (folio or "").strip(" _") or datetime.now().strftime("%A, %B %-d, %Y")
    meta = f"{copy['vol']}  —  {meta}  —  {copy['page']} {page}"
    if d.textlength(meta, font=LABEL) > A4[0] - 2 * M:
        meta = f"{copy['vol']}  —  {title[:50]}  —  {copy['page']} {page}"
    d.text(((A4[0] - d.textlength(meta, font=LABEL)) / 2, 140), meta, font=LABEL, fill=MUTED)
    _rule(d, M, 163, A4[0] - M)
    return 176


def _footer(d, page, copy):
    y = A4[1] - 43
    _rule(d, M, y, A4[0] - M)
    text = f"{copy['footer']} — {page}"
    d.text(((A4[0] - d.textlength(text, font=LABEL)) / 2, y + 11), text, font=LABEL, fill=MUTED)


def _parse(markdown, images):
    images = images or {}
    title = "Daily Report"
    folio = ""
    blocks = []
    for raw in markdown.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("# "):
            title = s[2:].strip()
            continue
        pictured = IMG_RE.fullmatch(s)
        if pictured:
            blob = images.get(pictured.group(2)) or images.get(Path(pictured.group(2)).name)
            blocks.append(Block("image", pictured.group(1) or "Editorial image", blob))
            continue
        if s == "---":
            blocks.append(Block("break", ""))
            continue
        if s.startswith("## "):
            blocks.append(Block("section", s[3:].strip()))
            continue
        if s.startswith("### "):
            blocks.append(Block("headline", s[4:].strip()))
            continue
        if s.startswith("> "):
            blocks.append(Block("quote", s[2:].strip()))
            continue
        if s.startswith("- "):
            blocks.append(Block("item", s[2:].strip()))
            continue
        if s.startswith("_") and s.endswith("_"):
            text = s[1:-1].strip()
            if not folio and ("·" in text or re.search(r"\d{1,2}/\d{1,2}", text)):
                folio = text
            else:
                blocks.append(Block("caption", text))
            continue
        blocks.append(Block("body", s))
    return title, folio, blocks


def _sections(blocks):
    sections = []
    name = ""
    bucket = []
    for block in blocks:
        if block.kind in ("break", "image"):
            continue
        if block.kind == "section":
            if name or bucket:
                sections.append((name, bucket))
            name, bucket = block.text, []
        else:
            bucket.append(block)
    if name or bucket:
        sections.append((name, bucket))
    return sections


def _named(sections, *keys):
    keys = tuple(k.casefold() for k in keys)
    for name, items in sections:
        if any(key in name.casefold() for key in keys):
            return name, items
    return "", []


def _items(blocks):
    return [b.text.strip() for b in blocks if b.kind == "item" and b.text.strip()]


def _strip_kicker(text):
    raw = text or ""
    for sep in ("o que importa é ", "the focus is ", "pende para ", "hangs on "):
        at = raw.casefold().find(sep)
        if at >= 0:
            raw = raw[at + len(sep) :]
            break
    return raw.strip(" .")


def _todo_items(sections, title="", folio=""):
    found = []
    for keys in (
        ("próximas ações", "next actions"),
        ("decisões", "decisions"),
        ("riscos e bloqueios", "risks and blockers", "riscos"),
    ):
        _, rows = _named(sections, *keys)
        found.extend(_items(rows))
    if not found:
        _, agenda = _named(sections, "agenda")
        for line in _items(agenda):
            match = SLOT.match(line)
            title = match.group(3) if match else line
            title = re.sub(r"\s+·\s+.*$", "", title).strip()
            blob = title.casefold()
            if any(w in blob for w in ("desloc", "volta pra", "commute", "ônibus", "onibus")):
                continue
            found.append(title)
    seen = set()
    out = []
    for text in found:
        head, note = _short_todo(text, title, folio)
        key = re.sub(r"\W+", " ", head.casefold())[:70].strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((head, note))
        if len(out) >= 6:
            break
    if not out:
        _, lead = _named(sections, "hoje em uma frase", "today in one sentence")
        for block in lead:
            if block.kind == "quote" and block.text.strip():
                out.append((_strip_kicker(block.text), ""))
                break
    return out


def _edition_day(title, folio):
    stamp = f"{title} {folio}"
    match = re.search(r"(\d{1,2})/(\d{1,2})", stamp)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d{1,2}) de ", stamp)
    if match:
        months = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()
        day = int(match.group(1))
        blob = stamp.casefold()
        for i, name in enumerate(months, 1):
            if name in blob:
                return day, i
    return None


def _short_todo(text, title="", folio=""):
    parts = [p.strip() for p in re.split(r"\s+[—–-]\s+", text or "") if p.strip()]
    if not parts:
        return text, ""
    head = parts[0]
    rest = " ".join(parts[1:])
    clocks = re.findall(r"\b(\d{1,2}h\d{2}|\d{1,2}:\d{2})\b", rest)
    if len(clocks) >= 2:
        return head, f"{clocks[0]}–{clocks[1]}"
    if clocks:
        return head, clocks[0]
    due = next((p for p in parts[1:] if p.casefold().startswith(("até", "due"))), "")
    if not due:
        return head, ""
    due = re.sub(r"^(até|due)\s+", "", due, flags=re.I)
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", due)
    if iso:
        day, month = int(iso.group(3)), int(iso.group(2))
        today = _edition_day(title, folio)
        if today and today == (day, month):
            return head, ""
        return head, f"{day:02d}/{month:02d}"
    return head, ""


def _height(d, block, width):
    if block.kind == "section":
        return 34
    if block.kind == "headline":
        return len(_wrap(d, block.text, HED, width)) * 32 + 8
    if block.kind == "quote":
        return len(_wrap(d, block.text, DEK, width)) * 42 + 12
    if block.kind == "caption":
        return len(_wrap(d, block.text, ITALIC, width)) * 20 + 8
    font = SMALL if block.kind == "item" else BODY
    prefix = "•  " if block.kind == "item" else ""
    return len(_wrap(d, prefix + block.text, font, width)) * 26 + 8


def _draw_block(d, block, x, y, width):
    if block.kind == "section":
        return _label(d, x, y, block.text, width)
    if block.kind == "headline":
        for line in _wrap(d, block.text, HED, width):
            d.text((x, y), line, font=HED, fill=INK)
            y += 32
        return y + 6
    if block.kind == "quote":
        for line in _wrap(d, block.text, DEK, width):
            d.text((x, y), line, font=DEK, fill=INK)
            y += 42
        return y + 10
    if block.kind == "caption":
        for line in _wrap(d, block.text, ITALIC, width):
            d.text((x, y), line, font=ITALIC, fill=MUTED)
            y += 20
        return y + 6
    font = SMALL if block.kind == "item" else BODY
    text = ("•  " if block.kind == "item" else "") + block.text
    for line in _wrap(d, text, font, width):
        d.text((x, y), line, font=font, fill=INK)
        y += 28
    return y + 10


def _new_page(number, title, folio, copy):
    im = Image.new("RGB", A4, PAPER)
    d = ImageDraw.Draw(im)
    y = _header(d, number, title, folio, copy)
    return im, d, y


def _draw_todo(d, x, y, width, items, copy):
    y = _label(d, x, y, copy["todo"], width)
    if not items:
        for line in _wrap(d, copy["lead"], SMALL, width):
            d.text((x, y), line, font=SMALL, fill=MUTED)
            y += 24
        return y
    for i, item in enumerate(items, 1):
        head, note = item if isinstance(item, tuple) else (item, "")
        d.text((x, y), f"{i}.", font=BODY_BOLD, fill=INK)
        inner = x + 32
        for line in _wrap(d, head, BODY, width - 32):
            d.text((inner, y), line, font=BODY, fill=INK)
            y += 26
        if note:
            d.text((inner, y), note, font=SMALL, fill=MUTED)
            y += 22
        y += 10
    return y


def _draw_agenda(d, x, y, width, items, name, cols=3):
    y = _label(d, x, y, name or "Agenda", width)
    if not items:
        return y
    gap = 18
    cols = max(1, min(cols, len(items)))
    col_w = (width - gap * (cols - 1)) // cols
    xs = [x + i * (col_w + gap) for i in range(cols)]
    col_y = [y] * cols
    for i, line in enumerate(items):
        c = i % cols
        match = SLOT.match(line)
        if match:
            stamp = f"{match.group(1)}–{match.group(2)}"
            title = match.group(3)
        else:
            stamp, title = "", line
        yy = col_y[c]
        if stamp:
            d.text((xs[c], yy), stamp, font=TIME, fill=INK)
            yy += 28
        for row in _wrap(d, title, BODY, col_w):
            d.text((xs[c], yy), row, font=BODY, fill=INK)
            yy += 26
        yy += 14
        col_y[c] = yy
    return max(col_y) + 8


def _draw_next(d, x, y, width, items, name):
    y = _label(d, x, y, name or "Próximas ações", width)
    if not items:
        return y
    for i, line in enumerate(items, 1):
        d.text((x, y), f"{i}.", font=ACTION_BOLD, fill=INK)
        inner = x + 40
        for row in _wrap(d, line, ACTION, width - 40):
            d.text((inner, y), row, font=ACTION, fill=INK)
            y += 34
        y += 12
    return y + 6


def _content_pages(title, folio, blocks, copy):
    pages = []
    number = 1
    im, d, y = _new_page(number, title, folio, copy)
    gap = 22
    rail_w = 318
    main_w = A4[0] - 2 * M - gap - rail_w
    rail_x = M + main_w + gap
    sections = _sections(blocks)

    lead_name, lead_blocks = _named(sections, "hoje em uma frase", "today in one sentence")
    quote = next((b.text for b in lead_blocks if b.kind == "quote"), title)
    y = _label(d, M, y, lead_name or copy["lead"], main_w)
    for line in _wrap(d, quote, DEK, main_w):
        d.text((M, y), line, font=DEK, fill=INK)
        y += 44
    dek_bottom = y + 12

    todo_bottom = _draw_todo(d, rail_x, 176, rail_w, _todo_items(sections, title, folio), copy)

    y = max(dek_bottom, todo_bottom) + 8
    agenda_name, agenda_blocks = _named(sections, "agenda")
    agenda_items = _items(agenda_blocks)
    if agenda_items:
        y = _draw_agenda(d, M, y, A4[0] - 2 * M, agenda_items, agenda_name, cols=3)
        _rule(d, M, y, A4[0] - M)
        y += 14

    next_name, next_blocks = _named(sections, "próximas ações", "next actions")
    next_items = _items(next_blocks)
    if next_items:
        y = _draw_next(d, M, y, A4[0] - 2 * M, next_items, next_name)
        _rule(d, M, y, A4[0] - M)
        y += 14

    skip = {
        (lead_name or "").casefold(),
        (agenda_name or "").casefold(),
        (next_name or "").casefold(),
        "próximas ações",
        "next actions",
    }
    rest = []
    for name, items in sections:
        if name.casefold() in skip:
            continue
        rest.append(Block("section", name))
        rest.extend(items)

    if rest and rest[0].kind == "section":
        y = _label(d, M, y, rest[0].text, A4[0] - 2 * M)
        rest = rest[1:]

    units = []
    current = []
    for block in rest:
        if block.kind in ("section", "headline") and current:
            units.append(current)
            current = [block]
        else:
            current.append(block)
    if current:
        units.append(current)

    n_cols = 2
    col_w = (A4[0] - 2 * M - gap * (n_cols - 1)) // n_cols
    xs = [M + i * (col_w + gap) for i in range(n_cols)]
    sim = [y] * n_cols
    for unit in units:
        h = sum(_height(d, block, col_w) for block in unit)
        i = min(range(n_cols), key=lambda c: sim[c])
        sim[i] += h + 16
    leftover = (A4[1] - BOTTOM) - max(sim)
    extra = min(36, max(0, leftover // max(1, len(units) + 1))) if units else 0
    col_y = [y] * n_cols
    top = y
    for unit in units:
        h = sum(_height(d, block, col_w) for block in unit)
        i = min(range(n_cols), key=lambda c: col_y[c])
        if col_y[i] + h > A4[1] - BOTTOM:
            if min(col_y) + h > A4[1] - BOTTOM:
                _footer(d, number, copy)
                pages.append(im)
                number += 1
                im, d, y = _new_page(number, title, folio, copy)
                col_y = [y] * n_cols
                extra = 0
                i = 0
            else:
                i = min(range(n_cols), key=lambda c: col_y[c])
        for block in unit:
            col_y[i] = _draw_block(d, block, xs[i], col_y[i], col_w)
        col_y[i] += 16 + extra
    if max(col_y) > top + 20:
        for c in range(1, n_cols):
            mid = xs[c] - gap // 2
            d.line((mid, top, mid, max(col_y)), fill=RULE, width=1)
    _footer(d, number, copy)
    pages.append(im)
    return pages


def _closing_page(number, title, folio, blocks, copy):
    im, d, y = _new_page(number, title, folio, copy)
    y = _label(d, M, y, copy["cartoon"], A4[0] - 2 * M)
    heading = next((b.text for b in blocks if b.kind == "section"), "")
    if heading and heading.casefold() not in copy["cartoon"].casefold():
        for line in _wrap(d, heading, DEK, A4[0] - 2 * M):
            d.text((M, y), line, font=DEK, fill=INK)
            y += 42
        y += 8
    image = next((b for b in blocks if b.kind == "image" and b.image), None)
    rest = [b for b in blocks if b.kind not in ("image", "break", "section")]
    caption_h = sum(_height(d, b, A4[0] - 2 * M) for b in rest) + 24
    if image:
        try:
            pic = Image.open(BytesIO(image.image)).convert("RGB")
        except (OSError, ValueError):
            pic = None
        if pic:
            max_w = A4[0] - 2 * M
            max_h = max(420, A4[1] - y - BOTTOM - caption_h)
            scale = min(max_w / max(1, pic.width), max_h / max(1, pic.height))
            pic = pic.resize((max(1, int(pic.width * scale)), max(1, int(pic.height * scale))), Image.LANCZOS)
            im.paste(pic, ((A4[0] - pic.width) // 2, y))
            y += pic.height + 14
    _rule(d, M, y, A4[0] - M)
    y += 12
    for block in rest:
        y = _draw_block(d, block, M, y, A4[0] - 2 * M)
    _footer(d, number, copy)
    return im


def pages_from_markdown(markdown, images=None):
    copy = chrome(markdown)
    title, folio, blocks = _parse(markdown, images or {})
    close_at = next(
        (
            i
            for i, b in enumerate(blocks)
            if b.kind == "section" and any(k in b.text.casefold() for k in ("charge", "cartoon"))
        ),
        None,
    )
    if close_at is None:
        main, closing = blocks, []
    else:
        main = blocks[:close_at]
        if main and main[-1].kind == "break":
            main = main[:-1]
        closing = blocks[close_at:]
    pages = _content_pages(title, folio, list(main), copy)
    if closing:
        pages.append(_closing_page(len(pages) + 1, title, folio, closing, copy))
    return pages


def _jpeg(im):
    buf = BytesIO()
    im.save(buf, "JPEG", quality=88, subsampling=0, progressive=False)
    return buf.getvalue()


def _pdf_from_jpegs(jpegs, size):
    w, h = 595, 842
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    def obj(n, body):
        offsets.append(len(out))
        out.extend(f"{n} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    kids = " ".join(f"{3 + i * 3} 0 R" for i in range(len(jpegs)))
    obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(jpegs)} >>".encode())
    n = 3
    for jpeg in jpegs:
        content = f"q {w} 0 0 {h} 0 0 cm /Im1 Do Q".encode()
        obj(
            n,
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Contents {n + 1} 0 R /Resources << /XObject << /Im1 {n + 2} 0 R >> >> >>".encode(),
        )
        obj(n + 1, f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
        obj(
            n + 2,
            f"<< /Type /XObject /Subtype /Image /Width {size[0]} /Height {size[1]} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpeg)} >>\nstream\n".encode()
            + jpeg
            + b"\nendstream",
        )
        n += 3
    xref = len(out)
    out.extend(f"xref\n0 {n}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def write_pdf(path, markdown, images=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pages = pages_from_markdown(markdown, images)
    path.write_bytes(_pdf_from_jpegs([_jpeg(p) for p in pages], A4))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    write_pdf(Path(args.out), Path(args.markdown).read_text(encoding="utf-8"))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
