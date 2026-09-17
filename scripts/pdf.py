#!/usr/bin/env python3
"""Render the daily edition as a printable A4 PDF. No extra packages.

Uses PIL (already in the image) + Playfair Display for the masthead, then
wraps each page as a JPEG inside a tiny PDF. Email-to-print (HP ePrint,
Epson, Brother, …) wants PDF, not EPUB.
"""
from __future__ import annotations

import argparse
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A4 = (1240, 1754)  # 150 dpi
MARGIN = 72
HERE = Path(__file__).resolve().parent
FONT_DIRS = (
    HERE.parent / "fonts",
    Path("/opt/matriz/fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
)


def _first(*names: str) -> Path | None:
    for folder in FONT_DIRS:
        for name in names:
            path = folder / name
            if path.exists():
                return path
    return None


def _load(size: int, bold: bool = False, display: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if display:
        path = _first("PlayfairDisplay-Bold.ttf" if bold else "PlayfairDisplay-Regular.ttf")
        if path is None:
            path = _first("PlayfairDisplay-Bold.ttf", "PlayfairDisplay-Regular.ttf")
        if path is not None:
            return ImageFont.truetype(str(path), size)
    if bold:
        path = _first("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSerif-Bold.ttf")
    else:
        path = _first(
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "DejaVuSerif.ttf",
            "LiberationSerif-Regular.ttf",
        )
    if path is not None:
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    text = text.replace("\t", " ")
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=font) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        if draw.textlength(word, font=font) <= width:
            current = word
        else:
            chunk = ""
            for ch in word:
                if draw.textlength(chunk + ch, font=font) <= width:
                    chunk += ch
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk
    if current:
        lines.append(current)
    return lines or [""]


_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _has_ink(img: Image.Image, paper: tuple[int, int, int]) -> bool:
    sample = img.resize((60, 84), Image.BOX)
    return any(px != paper for px in sample.getdata())


def pages_from_markdown(markdown: str, images: dict[str, bytes] | None = None) -> list[Image.Image]:
    images = images or {}
    body_font = _load(26)
    h1 = _load(50, bold=True, display=True)
    h2 = _load(22, bold=True, display=True)
    h3 = _load(28, bold=True, display=False)
    italic = _load(24)
    width = A4[0] - 2 * MARGIN
    paper = (247, 243, 234)
    ink = (26, 22, 18)
    rule = (90, 82, 72)
    pages: list[Image.Image] = []
    leading = 12

    def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        img = Image.new("RGB", A4, paper)
        return img, ImageDraw.Draw(img), MARGIN

    def keep(page: Image.Image) -> None:
        if _has_ink(page, paper):
            pages.append(page)

    img, draw, y = new_page()
    prev_h1 = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.strip() == "---":
            keep(img)
            img, draw, y = new_page()
            prev_h1 = False
            continue
        pictured = _IMG.search(line)
        if pictured:
            key = pictured.group(2)
            blob = images.get(key) or images.get(Path(key).name)
            if blob:
                if y > MARGIN + 200:
                    keep(img)
                    img, draw, y = new_page()
                try:
                    pic = Image.open(BytesIO(blob)).convert("RGB")
                except (OSError, ValueError):
                    pic = None
                if pic is not None:
                    max_w = width
                    max_h = A4[1] - 2 * MARGIN - 140
                    scale = min(max_w / max(1, pic.width), max_h / max(1, pic.height))
                    size = (max(1, int(pic.width * scale)), max(1, int(pic.height * scale)))
                    pic = pic.resize(size, Image.LANCZOS)
                    x0 = max(MARGIN, int((A4[0] - size[0]) / 2))
                    img.paste(pic, (x0, y))
                    draw.rectangle(
                        (x0 - 4, y - 4, x0 + size[0] + 4, y + size[1] + 4),
                        outline=ink,
                        width=2,
                    )
                    y += size[1] + 18
                prev_h1 = False
                continue
        align = "left"
        folio_line = False
        if line.startswith("# "):
            font, text, gap, align = h1, line[2:], 6, "center"
        elif line.startswith("## "):
            font, text, gap, align = h2, line[3:].upper(), 14, "center"
        elif line.startswith("### "):
            font, text, gap = h3, line[4:], 12
        elif line.startswith("> "):
            font, text, gap, align = italic, line[2:], 12, "center"
        elif line.startswith("- "):
            font, text, gap = body_font, "• " + line[2:], 10
        elif line.startswith("_") and line.endswith("_") and len(line) > 2:
            if prev_h1:
                font, text, gap, align = h2, line[1:-1].upper(), 16, "center"
                folio_line = True
            else:
                font, text, gap, align = italic, line[1:-1], 10, "center"
        elif not line.strip():
            y += 18
            continue
        else:
            font, text, gap = body_font, line, 10
        wrapped = _wrap(draw, text, font, width)
        needed = len(wrapped) * (getattr(font, "size", 14) + leading) + gap
        if y + needed > A4[1] - MARGIN:
            keep(img)
            img, draw, y = new_page()
        if line.startswith("# "):
            draw.line((MARGIN, y - 10, A4[0] - MARGIN, y - 10), fill=ink, width=3)
            draw.line((MARGIN, y - 6, A4[0] - MARGIN, y - 6), fill=ink, width=1)
        elif line.startswith("## "):
            draw.line((MARGIN, y - 4, A4[0] - MARGIN, y - 4), fill=ink, width=2)
        for row in wrapped:
            x = MARGIN
            if align == "center":
                x = max(MARGIN, int((A4[0] - draw.textlength(row, font=font)) / 2))
            draw.text((x, y), row, fill=ink, font=font)
            y += getattr(font, "size", 14) + leading
        if line.startswith("# "):
            draw.line((MARGIN, y + 2, A4[0] - MARGIN, y + 2), fill=rule, width=1)
            y += 8
        elif folio_line:
            draw.line((MARGIN, y + 2, A4[0] - MARGIN, y + 2), fill=ink, width=1)
            draw.line((MARGIN, y + 6, A4[0] - MARGIN, y + 6), fill=ink, width=3)
            y += 12
        elif line.startswith("## "):
            draw.line((MARGIN, y, A4[0] - MARGIN, y), fill=rule, width=1)
            y += 6
        prev_h1 = line.startswith("# ")
        y += gap
    keep(img)
    return pages or [Image.new("RGB", A4, paper)]


def _jpeg(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=False, progressive=False)
    return buf.getvalue()


def _pdf_from_jpegs(jpegs: list[bytes], size: tuple[int, int]) -> bytes:
    w, h = 595, 842  # A4 points
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    def obj(n: int, body: bytes) -> None:
        offsets.append(len(out))
        out.extend(f"{n} 0 obj\n".encode("ascii"))
        out.extend(body)
        if not body.endswith(b"\n"):
            out.extend(b"\n")
        out.extend(b"endobj\n")

    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(jpegs)))
    obj(1, f"<< /Type /Catalog /Pages 2 0 R >>".encode("ascii"))
    obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(jpegs)} >>".encode("ascii"))
    n = 3
    for jpeg in jpegs:
        content = f"q {w} 0 0 {h} 0 0 cm /Im1 Do Q".encode("ascii")
        obj(
            n,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] "
                f"/Contents {n + 1} 0 R /Resources << /XObject << /Im1 {n + 2} 0 R >> >> >>"
            ).encode("ascii"),
        )
        obj(n + 1, f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream")
        obj(
            n + 2,
            (
                f"<< /Type /XObject /Subtype /Image /Width {size[0]} /Height {size[1]} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg)} >>\nstream\n"
            ).encode("ascii")
            + jpeg
            + b"\nendstream",
        )
        n += 3
    xref_at = len(out)
    out.extend(f"xref\n0 {n}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii"))
    return bytes(out)


def write_pdf(path: Path, markdown: str, images: dict[str, bytes] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pages = pages_from_markdown(markdown, images)
    pdf = _pdf_from_jpegs([_jpeg(p) for p in pages], A4)
    path.write_bytes(pdf)


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown → A4 PDF for printers.")
    parser.add_argument("markdown")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    write_pdf(Path(args.out), Path(args.markdown).read_text(encoding="utf-8"))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
