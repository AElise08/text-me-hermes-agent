#!/usr/bin/env python3
"""Render the daily edition as a printable A4 PDF. No extra packages.

Uses PIL (already in the image) + DejaVu, then wraps each page as a JPEG
inside a tiny PDF. Email-to-print (HP ePrint, Epson, Brother, …) wants PDF,
not EPUB.
"""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A4 = (1240, 1754)  # 150 dpi
MARGIN = 72
FONTS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    regular, bold_path = FONTS[0], FONTS[1]
    path = bold_path if bold and bold_path.exists() else regular
    if path.exists():
        return ImageFont.truetype(str(path), size)
    for candidate in FONTS:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
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


def pages_from_markdown(markdown: str) -> list[Image.Image]:
    body_font = _font(28)
    h1, h2 = _font(44, bold=True), _font(34, bold=True)
    italic = _font(24)
    width = A4[0] - 2 * MARGIN
    pages: list[Image.Image] = []

    def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        img = Image.new("RGB", A4, "white")
        return img, ImageDraw.Draw(img), MARGIN

    img, draw, y = new_page()
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            font, text, gap = h1, line[2:], 18
        elif line.startswith("## "):
            font, text, gap = h2, line[3:], 14
        elif line.startswith("- "):
            font, text, gap = body_font, "• " + line[2:], 8
        elif line.startswith("_") and line.endswith("_") and len(line) > 2:
            font, text, gap = italic, line[1:-1], 8
        elif not line.strip():
            y += 16
            continue
        else:
            font, text, gap = body_font, line, 8
        wrapped = _wrap(draw, text, font, width)
        needed = len(wrapped) * (getattr(font, "size", 14) + 8) + gap
        if y + needed > A4[1] - MARGIN:
            pages.append(img)
            img, draw, y = new_page()
        for row in wrapped:
            draw.text((MARGIN, y), row, fill="black", font=font)
            y += getattr(font, "size", 14) + 8
        y += gap
    pages.append(img)
    return pages


def _jpeg(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
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


def write_pdf(path: Path, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pages = pages_from_markdown(markdown)
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
