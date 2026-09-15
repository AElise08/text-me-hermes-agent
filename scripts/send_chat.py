#!/usr/bin/env python3
"""Send one Plow Chat message without the live gateway adapter.

Hermes `--deliver plow_chat:...` fails out-of-process (no standalone_sender).
This posts to the same API the life-assistant nudge uses.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def s6_value(name: str) -> str:
    path = Path("/run/s6/container_environment") / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def chat_id_from_config() -> str:
    path = hermes_home() / "config.yaml"
    if not path.exists():
        return ""
    in_home = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("home_channel:"):
            in_home = True
            continue
        if in_home and stripped.startswith("chat_id:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if in_home and stripped and not stripped.startswith("#") and not stripped.startswith("chat_id") and not stripped.startswith("platform"):
            in_home = False
    return ""


def credentials() -> tuple[str, str, str]:
    env: dict[str, str] = {}
    home = hermes_home()
    for path in (
        home / ".saved" / "plow.env",
        home / ".env",
        Path("/var/lib/plow/credentials"),
    ):
        env.update(load_dotenv(path))
    base = (
        os.environ.get("PLOW_API_BASE")
        or env.get("PLOW_API_BASE")
        or s6_value("PLOW_API_BASE")
    ).rstrip("/")
    token = (
        os.environ.get("PLOW_AGENT_TOKEN")
        or env.get("PLOW_AGENT_TOKEN")
        or s6_value("PLOW_AGENT_TOKEN")
    )
    uid = (
        os.environ.get("PLOW_HOME_CHANNEL")
        or env.get("PLOW_HOME_CHANNEL")
        or s6_value("PLOW_HOME_CHANNEL")
        or chat_id_from_config()
    )
    missing = [name for name, value in (("PLOW_API_BASE", base), ("PLOW_AGENT_TOKEN", token), ("PLOW_HOME_CHANNEL", uid)) if not value]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)} — cannot send Plow Chat")
    return base, token, uid


def send(text: str) -> None:
    text = (text or "").strip()
    if not text or text == "[SILENT]":
        return
    base, token, uid = credentials()
    url = f"{base}/v1/chats/{uid}/messages"
    body = json.dumps({"body": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Plow Chat HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Plow Chat network error: {exc.reason}") from exc


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Send a message to the owner's Plow Chat.")
    p.add_argument("text", nargs="?", default="", help="Message body")
    p.add_argument("--file", help="Read body from a file, or - for stdin")
    return p


def main() -> int:
    args = parser().parse_args()
    if args.file:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text or sys.stdin.read()
    send(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
