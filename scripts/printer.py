#!/usr/bin/env python3
"""Print a PDF over IPP (no CUPS). Same LAN as the printer.

URI examples: ipp://192.168.1.50/ipp/print
              ipp://printer.local:631/ipp/print
Email-to-print is the default path (gmail.py); this is the extra when the
agent host can actually see the printer.
"""
from __future__ import annotations

import argparse
import os
import struct
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

S6 = Path("/run/s6/container_environment")


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        return (S6 / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def uri() -> str:
    return env("PRINTER_URI")


def http_url(ipp_uri: str) -> str:
    parsed = urlparse(ipp_uri)
    scheme = "https" if parsed.scheme == "ipps" else "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 631)
    path = parsed.path or "/ipp/print"
    return f"{scheme}://{host}:{port}{path}"


def _attr(tag: int, name: str, value: bytes) -> bytes:
    nb, vb = name.encode("ascii"), value
    return bytes([tag]) + struct.pack(">H", len(nb)) + nb + struct.pack(">H", len(vb)) + vb


def _request(operation: int, printer_uri: str, document: bytes | None = None) -> bytes:
    body = bytearray(struct.pack(">BBHI", 1, 1, operation, 1))
    body.append(0x01)  # operation-attributes-tag
    body.extend(_attr(0x47, "attributes-charset", b"utf-8"))
    body.extend(_attr(0x48, "attributes-natural-language", b"en"))
    body.extend(_attr(0x45, "printer-uri", printer_uri.encode("ascii")))
    body.extend(_attr(0x42, "requesting-user-name", b"text-me"))
    if document is not None:
        body.extend(_attr(0x49, "document-format", b"application/pdf"))
    body.append(0x03)  # end-of-attributes
    if document is not None:
        body.extend(document)
    return bytes(body)


def call(ipp_uri: str, operation: int, document: bytes | None = None, timeout: int = 12) -> bytes:
    request = urllib.request.Request(
        http_url(ipp_uri),
        data=_request(operation, ipp_uri, document),
        method="POST",
        headers={"Content-Type": "application/ipp", "Accept": "application/ipp"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:200]
        raise SystemExit(f"ipp HTTP {exc.code}: {detail!r}") from exc
    except OSError as exc:
        raise SystemExit(f"ipp unreachable: {exc}") from exc


def probe(ipp_uri: str | None = None) -> dict:
    target = ipp_uri or uri()
    if not target:
        return {"ok": False, "reason": "no PRINTER_URI"}
    try:
        raw = call(target, 0x000B)  # Get-Printer-Attributes
    except SystemExit as exc:
        return {"ok": False, "uri": target, "reason": str(exc)}
    status = struct.unpack(">H", raw[2:4])[0] if len(raw) >= 4 else 0
    return {"ok": status < 0x0400, "uri": target, "status": status}


def send(pdf: Path, ipp_uri: str | None = None) -> dict:
    target = ipp_uri or uri()
    if not target:
        raise SystemExit("no PRINTER_URI")
    raw = call(target, 0x0002, pdf.read_bytes())  # Print-Job
    status = struct.unpack(">H", raw[2:4])[0] if len(raw) >= 4 else 0
    if status >= 0x0400:
        raise SystemExit(f"ipp Print-Job status 0x{status:04x}")
    return {"ok": True, "uri": target, "status": status}


def main() -> int:
    import json

    parser = argparse.ArgumentParser(description="IPP print without CUPS.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    pr = sub.add_parser("send")
    pr.add_argument("pdf")
    args = parser.parse_args()
    if args.cmd == "probe":
        print(json.dumps(probe(), ensure_ascii=False))
        return 0
    print(json.dumps(send(Path(args.pdf)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
