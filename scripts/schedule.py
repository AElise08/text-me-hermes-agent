#!/usr/bin/env python3
"""When the edition should be *in their hand* vs when we actually send.

edition_hour is arrival, not send. Kindle takes a few minutes to sync, so
we mail at 5:55 if they asked for 6:00.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LEAD_MINUTES = {
    "kindle": 5,
    "printer": 10,
    "email": 2,
    "message": 0,
}


def home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))


def stamp_path() -> Path:
    return home() / ".matriz" / "dispatch.json"


def zone() -> ZoneInfo:
    name = os.environ.get("TZ") or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def load_profile() -> dict:
    path = home() / ".matriz" / "state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("profile") or {}


def stamped_day() -> str:
    try:
        return json.loads(stamp_path().read_text(encoding="utf-8")).get("day") or ""
    except (OSError, json.JSONDecodeError):
        return ""


def mark_sent(day: str) -> None:
    path = stamp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"day": day}) + "\n", encoding="utf-8")


def hour(profile: dict | None = None) -> int:
    profile = profile if profile is not None else load_profile()
    try:
        value = int(profile.get("edition_hour") or 7)
    except (TypeError, ValueError):
        value = 7
    return min(23, max(0, value))


def delivery(profile: dict | None = None) -> str:
    profile = profile if profile is not None else load_profile()
    return (profile.get("delivery") or "message").strip() or "message"


def lead_minutes(profile: dict | None = None) -> int:
    return LEAD_MINUTES.get(delivery(profile), 0)


def hand_at(now: datetime, profile: dict | None = None) -> datetime:
    local = now.astimezone(now.tzinfo or zone())
    return local.replace(hour=hour(profile), minute=0, second=0, microsecond=0)


def dispatch_at(now: datetime, profile: dict | None = None) -> datetime:
    return hand_at(now, profile) - timedelta(minutes=lead_minutes(profile))


def next_wake(now: datetime, profile: dict | None = None, already: str | None = None) -> datetime:
    profile = profile if profile is not None else load_profile()
    target = dispatch_at(now, profile)
    today = now.astimezone(now.tzinfo or zone()).date().isoformat()
    if (already if already is not None else stamped_day()) == today:
        return target + timedelta(days=1)
    if now >= target:
        return now
    return target


def sleep_seconds(now: datetime | None = None, profile: dict | None = None) -> int:
    now = now or datetime.now(zone())
    wake = next_wake(now, profile)
    return max(1, int((wake - now).total_seconds()))


def wants_morning_chat(profile: dict | None, sent: bool) -> bool:
    dest = delivery(profile)
    if dest in ("kindle", "printer") and sent:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Edition send clock (arrival hour minus lead).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sleep-seconds")
    sub.add_parser("next")
    args = parser.parse_args()
    now = datetime.now(zone())
    profile = load_profile()
    if args.cmd == "sleep-seconds":
        print(sleep_seconds(now, profile))
        return 0
    print(
        json.dumps(
            {
                "edition_hour": hour(profile),
                "delivery": delivery(profile),
                "lead_minutes": lead_minutes(profile),
                "hand_at": hand_at(now, profile).isoformat(),
                "dispatch_at": dispatch_at(now, profile).isoformat(),
                "sleep_seconds": sleep_seconds(now, profile),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
