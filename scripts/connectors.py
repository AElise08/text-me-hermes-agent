#!/usr/bin/env python3
"""Google Calendar and Gmail without Latch.

Primary path: REST /v1/connectors/gmail/* with the plow-agents *account*
token (PLOW_CONNECTOR_TOKEN). Agent tokens 403. Latch is optional.
Gmail send/read mint a short-lived Google token (gmail.modify).
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
            "reason": "no account token (PLOW_CONNECTOR_TOKEN / ~/.config/plow/token)",
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
    google = rest["ok"] or latch["ok"]
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
            "REST Calendar and Gmail (read + send) are up. "
            "Printer PDF goes to the printer's email (HP ePrint / Epson / Brother) "
            "the same way Kindle gets EPUB. No Mac required."
        )
    elif latch["ok"]:
        bits.append("Latch is up. Calendar and Gmail via the owner's computer.")
    else:
        bits.append(
            "Google is not reachable. Connect Google at "
            "https://app.plow.co → Connectors, then mount the plow-agents login "
            "token (~/.config/plow/token) as PLOW_CONNECTOR_TOKEN."
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
