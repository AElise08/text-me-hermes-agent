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


def zone(profile: dict | None = None) -> ZoneInfo:
    """Their clock: profile timezone first, image TZ second, UTC last.

    The person tells the agent their city in chat; the agent saves the IANA
    name with `profile set --timezone`. Nobody should have to edit compose
    to get the report on their own morning.
    """
    profile = profile if profile is not None else load_profile()
    name = (profile.get("timezone") or "").strip() or os.environ.get("TZ") or "UTC"
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
        stamp = json.loads(stamp_path().read_text(encoding="utf-8"))
        # Old stamps had only `day`; keep them as successful deliveries.
        if stamp.get("status", "sent") == "sent":
            return stamp.get("day") or ""
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def dispatch_state() -> dict:
    try:
        return json.loads(stamp_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def mark_sent(day: str) -> None:
    path = stamp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"day": day, "status": "sent", "sent_at": datetime.now(zone()).isoformat()}) + "\n",
        encoding="utf-8",
    )


def mark_retry(day: str, now: datetime | None = None) -> dict:
    """Persist retry timing so a transient connector error is not a lost day."""
    now = now or datetime.now(zone())
    prior = dispatch_state()
    attempts = int(prior.get("attempts") or 0) + 1 if prior.get("day") == day else 1
    delay = min(60, 5 * (2 ** (attempts - 1)))
    retry_at = now + timedelta(minutes=delay)
    state = {
        "day": day,
        "status": "retry",
        "attempts": attempts,
        "retry_at": retry_at.isoformat(),
    }
    target = stamp_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(state) + "\n", encoding="utf-8")
    temp.replace(target)
    return state


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
    retry = dispatch_state()
    if retry.get("day") == today and retry.get("status") == "retry":
        try:
            retry_at = datetime.fromisoformat(retry["retry_at"])
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=now.tzinfo)
            if retry_at > now:
                return retry_at
        except (KeyError, TypeError, ValueError):
            pass
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
