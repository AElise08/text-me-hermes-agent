#!/usr/bin/env python3
"""Show the Plow tools available to this agent — including calendar, if the
owner has connected their Google account.

Why this exists
---------------
Optional: list tools the Latch *relay* is offering. text-me does **not** use
this for Gmail or Calendar — those are REST via connectors.py / gcal.py /
gmail.py. A missing relay is normal and not a failure of Google.

Usage:
  python3 plow_tools.py            # list every tool
  python3 plow_tools.py --calendar # only calendar-related tools

Exit code is 0 when the relay answered, 1 when it did not (device offline,
no relay URL, no token) — so a caller can branch on it without parsing prose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

S6 = Path("/run/s6/container_environment")


def value(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        return (S6 / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def rpc(url: str, token: str, payload: dict) -> tuple[int, object]:
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
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
    except OSError as error:
        return 0, str(error)
    # Streamable HTTP may answer as SSE; take the last data: line as JSON.
    if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
        for line in reversed(raw.splitlines()):
            if line.startswith("data:"):
                raw = line[len("data:"):].strip()
                break
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calendar", action="store_true",
                        help="only show calendar-related tools")
    args = parser.parse_args()

    url = value("PLOW_MCP_URL")
    token = value("PLOW_AGENT_TOKEN")
    if not url or not token:
        print("no PLOW_MCP_URL / PLOW_AGENT_TOKEN in the environment — "
              "this lists Latch relay tools, which text-me does not need "
              "for Gmail or Calendar. Use connectors.py instead.", file=sys.stderr)
        return 1

    status, body = rpc(url, token, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "plow-tools", "version": "1.0"}},
    })
    if status // 100 != 2:
        detail = body.get("detail") if isinstance(body, dict) else body
        print(f"relay not reachable ({status}): {detail}", file=sys.stderr)
        print("Latch relay did not answer. Gmail and Calendar still go through "
              "connectors.py — Latch is not required.", file=sys.stderr)
        return 1

    status, body = rpc(url, token,
                       {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    if status // 100 != 2 or not isinstance(body, dict):
        print(f"tools/list answered {status}: {body}", file=sys.stderr)
        return 1

    tools = body.get("result", {}).get("tools") or []
    names = sorted(str(t.get("name", "")) for t in tools)
    if args.calendar:
        names = [n for n in names if "calendar" in n.lower()]
    if not names:
        print("no tools" + (" matching calendar" if args.calendar else "") +
              " — connect Google in Plow (https://app.plow.co → Connectors).")
        return 0
    for name in names:
        print(name)
    print(f"\n{len(names)} tool(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
