#!/usr/bin/env python3
"""Google Calendar through Plow's REST connectors — no Latch, no Mac.

Uses the account token (plow-agents login), not the agent token. Connect
Google once at https://app.plow.co → Connectors.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

S6 = Path("/run/s6/container_environment")
TOKEN_FILES = (
    Path("/var/lib/plow/account.token"),
)


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        return (S6 / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def token() -> str:
    value = env("PLOW_CONNECTOR_TOKEN")
    if value:
        return value
    path = env("PLOW_CONNECTOR_TOKEN_FILE")
    files = [Path(path)] if path else []
    files.extend(TOKEN_FILES)
    for candidate in files:
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text.splitlines()[0].strip()
    return ""


def base() -> str:
    return (env("PLOW_API_BASE") or "https://api.plow.co").rstrip("/")


def call(action: str, body: dict | None = None, method: str | None = None) -> dict:
    tok = token()
    if not tok:
        raise SystemExit("no PLOW_CONNECTOR_TOKEN — run plow-agents login and mount ~/.config/plow/token")
    verb = method or ("GET" if action == "status" else "POST")
    url = f"{base()}/v1/connectors/gmail/{action}"
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    data = None
    if verb == "POST":
        data = json.dumps(body or {}).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=verb)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"calendar {action} HTTP {exc.code}: {detail}") from exc


def zone() -> ZoneInfo:
    """Their clock, same rule as schedule.py: profile timezone, then TZ."""
    name = ""
    try:
        state = json.loads(
            (Path(os.environ.get("HERMES_HOME", "/var/lib/hermes")) / ".matriz" / "state.json")
            .read_text(encoding="utf-8")
        )
        name = ((state.get("profile") or {}).get("timezone") or "").strip()
    except (OSError, json.JSONDecodeError):
        pass
    name = name or env("TZ") or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def day_window(when: datetime | None = None) -> tuple[str, str]:
    now = when or datetime.now(zone())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def events_on(when: datetime | None = None) -> list[dict]:
    time_min, time_max = day_window(when)
    payload = call(
        "calendar.events.list",
        {"time_min": time_min, "time_max": time_max, "max_results": 50},
    )
    data = payload.get("data")
    if isinstance(data, dict):
        items = data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    out = []
    for item in items:
        start = item.get("start") or {}
        if isinstance(start, dict):
            start = start.get("dateTime") or start.get("date_time") or start.get("date") or ""
        end = item.get("end") or {}
        if isinstance(end, dict):
            end = end.get("dateTime") or end.get("date_time") or end.get("date") or ""
        out.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary") or "(no title)",
                "start": start,
                "end": end,
                "calendar_id": item.get("calendar_id") or item.get("calendarId"),
                "account": item.get("account"),
            }
        )
    return out


def events_today() -> list[dict]:
    return events_on()


def create(summary: str, start: str, end: str, description: str = "") -> dict:
    body = {
        "summary": summary,
        "start": start,
        "end": end,
        "time_zone": str(zone()),
    }
    if description:
        body["description"] = description
    return call("calendar.events.create", body)


def update(event_id: str, calendar_id: str, account: str, **fields) -> dict:
    body = {"event_id": event_id, "calendar_id": calendar_id, "account": account}
    body.update(fields)
    return call("calendar.events.update", body)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Plow Calendar over REST (no Latch).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("today")
    on = sub.add_parser("on")
    on.add_argument("--date", required=True, help="YYYY-MM-DD")
    make = sub.add_parser("create")
    make.add_argument("--summary", required=True)
    make.add_argument("--start", required=True)
    make.add_argument("--end", required=True)
    make.add_argument("--description", default="")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(call("status"), ensure_ascii=False))
        return 0
    if args.cmd == "today":
        print(json.dumps({"events": events_today()}, ensure_ascii=False))
        return 0
    if args.cmd == "on":
        when = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=zone())
        print(json.dumps({"date": args.date, "events": events_on(when)}, ensure_ascii=False))
        return 0
    print(json.dumps(create(args.summary, args.start, args.end, args.description), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
