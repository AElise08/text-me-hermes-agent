#!/usr/bin/env python3
"""Google Calendar and Gmail without Latch.

REST /v1/connectors/gmail/* . On Plow Cloud the line token
(PLOW_AGENT_TOKEN) is enough when Google is linked on that same account.
PLOW_CONNECTOR_TOKEN is only for a different Plow account. Latch is optional
and is never how we decide if Gmail works.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

S6 = Path("/run/s6/container_environment")


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        return (S6 / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def rest_status() -> dict:
    try:
        import gcal
    except ImportError:
        here = Path(__file__).resolve().parent
        if str(here) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(here))
        import gcal
    if not gcal.token():
        return {
            "ok": False,
            "path": "rest",
            "reason": "no Plow token for connectors",
        }
    try:
        body = gcal.call("status")
    except SystemExit as exc:
        return {"ok": False, "path": "rest", "reason": str(exc)}
    connected = bool(body.get("connected"))
    return {"ok": connected, "path": "rest", "gmail": body}


def latch_status() -> dict:
    url, token = env("PLOW_MCP_URL"), env("PLOW_AGENT_TOKEN")
    if not url or not token:
        return {
            "ok": False,
            "path": "latch",
            "reason": "no PLOW_MCP_URL — Latch is not wired into this container",
        }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "text-me-connectors", "version": "1.0"},
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        return {"ok": True, "path": "latch", "reason": "relay answered"}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        return {"ok": False, "path": "latch", "reason": f"HTTP {exc.code}: {detail}"}
    except OSError as exc:
        return {"ok": False, "path": "latch", "reason": str(exc)}


def probe() -> dict:
    rest, latch = rest_status(), latch_status()
    google = rest["ok"]
    try:
        import printer as printer_mod
    except ImportError:
        here = Path(__file__).resolve().parent
        if str(here) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(here))
        import printer as printer_mod
    ipp = printer_mod.probe()
    return {
        "calendar": google,
        "gmail_read": google,
        "gmail_send": google,
        "printer_email": google,
        "printer_ipp": ipp.get("ok", False),
        "rest": rest,
        "latch": latch,
        "ipp": ipp,
        "advice": _advice(rest, latch, ipp),
    }


def _advice(rest: dict, latch: dict, ipp: dict) -> str:
    bits = []
    if rest["ok"]:
        bits.append(
            "Calendar and Gmail (read + send) are up on Plow Connectors. "
            "No Latch, no Mac. Printer PDF goes to the printer's email "
            "(HP ePrint / Epson / Brother) the same way Kindle gets EPUB."
        )
    else:
        reason = rest.get("reason") or "not connected"
        bits.append(
            "Google is not reachable via Plow Connectors "
            f"({reason}). Connect Gmail and Calendar at "
            "https://app.plow.co → Connectors on the same account as this chat. "
            "Do not use Latch for this. Do not open the site in a browser to check — "
            "this probe is the check."
        )
    if ipp.get("ok"):
        bits.append(f"IPP printer reachable at {ipp.get('uri')}.")
    elif ipp.get("reason") and ipp.get("reason") != "no PRINTER_URI":
        bits.append(f"IPP not reachable: {ipp['reason']}")
    return " ".join(bits)


def main() -> int:
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
