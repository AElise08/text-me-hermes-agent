#!/usr/bin/env python3
"""Google Calendar through Plow's REST connectors — no Latch, no Mac.

Uses the account token (plow-agents login), not the agent token. Connect
Google once at https://app.plow.co → Connectors.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

S6 = Path("/run/s6/container_environment")
TOKEN_FILES = (
    Path("/var/lib/plow/account.token"),
)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import accounts as accounts_mod  # noqa: E402


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        return (S6 / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def token() -> str:
    """Account token first; on Plow Cloud the line's agent token is enough.

    Google linked at app.plow.co → Connectors belongs to the same account as
    the chat line. PLOW_CONNECTOR_TOKEN is only needed when Google lives on a
    *different* Plow account. Latch is never this path.
    """
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
    for name in ("PLOW_AGENT_TOKEN", "PLOW_CHAT_TOKEN"):
        value = env(name)
        if value:
            return value
    return ""


def base() -> str:
    return (env("PLOW_API_BASE") or "https://api.plow.co").rstrip("/")


def call(action: str, body: dict | None = None, method: str | None = None) -> dict:
    tok = token()
    if not tok:
        raise SystemExit(
            "no Plow token for connectors — connect Google at https://app.plow.co → Connectors"
        )
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


def events_on(when: datetime | None = None, calendar_id: str = "", account: str = "") -> list[dict]:
    time_min, time_max = day_window(when)
    account, calendar_id = accounts_mod.route(account, calendar_id)
    payload = call(
        "calendar.events.list",
        {
            "time_min": time_min,
            "time_max": time_max,
            "max_results": 50,
            "calendar_id": calendar_id,
            "account": account,
        },
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
                "calendar_id": item.get("calendar_id") or item.get("calendarId") or calendar_id,
                "account": item.get("account") or account,
                "hangout": meet_link(item),
                "attendees": [
                    (person.get("email") or "").strip()
                    for person in (item.get("attendees") or [])
                    if isinstance(person, dict) and (person.get("email") or "").strip()
                ],
            }
        )
    out.sort(key=lambda item: str(item.get("start") or ""))
    return out


def clock(stamp: str) -> str:
    if not stamp:
        return ""
    if "T" in stamp:
        return stamp.split("T", 1)[1][:5]
    return ""


def line(event: dict) -> str:
    """One calendar row: 07:30–09:20 Aula — the morning page opener."""
    start, end = clock(event.get("start") or ""), clock(event.get("end") or "")
    title = (event.get("summary") or "").strip()
    if start and end:
        return f"{start}–{end}  {title}".strip()
    if start:
        return f"{start}  {title}".strip()
    return title


def day_lines(when: datetime | None = None, calendar_id: str = "", account: str = "") -> list[str]:
    return [line(event) for event in events_on(when, calendar_id, account) if line(event)]


def events_today(calendar_id: str = "", account: str = "") -> list[dict]:
    return events_on(calendar_id=calendar_id, account=account)


def event_by_id(event_id: str, calendar_id: str = "", account: str = "") -> dict:
    account, calendar_id = accounts_mod.route(account, calendar_id)
    payload = call(
        "calendar.events.get",
        {"event_id": event_id, "calendar_id": calendar_id or "primary", "account": account or ""},
    )
    item = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(item, dict) or not item.get("id"):
        raise SystemExit("could not retrieve event details")
    return {
        "id": item["id"],
        "attendees": [
            (person.get("email") or "").strip()
            for person in (item.get("attendees") or [])
            if isinstance(person, dict) and (person.get("email") or "").strip()
        ],
    }


EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def emails_in(text: str) -> list[str]:
    seen: list[str] = []
    for hit in EMAIL.findall(text or ""):
        addr = hit.strip().casefold()
        if addr and addr not in seen:
            seen.append(addr)
    return seen


def wants_meet(text: str) -> bool:
    """True only when they asked for a room URL, not a phone call."""
    blob = (text or "").casefold()
    needles = (
        "google meet",
        "hangout",
        "hangoutsmeet",
        "meet.google",
        "link da call",
        "link de call",
        "link pra call",
        "link para call",
        "call link",
        "video call",
        "videocall",
        "videochamada",
        "vídeo chamada",
        "video chamada",
        "chamada de vídeo",
        "chamada de video",
        "cria o meet",
        "criar o meet",
        "com meet",
        "with meet",
        "zoom.us",
        "zoom.com",
    )
    if any(n in blob for n in needles):
        return True
    return bool(re.search(r"(?<![a-zà-ÿ])meet(?![a-zà-ÿ])", blob))


def meet_link(payload: dict | None) -> str:
    """Google Meet URL from a create/list payload. Empty if none yet."""
    if not isinstance(payload, dict):
        return ""
    event = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(event, dict):
        return ""
    for key in ("hangoutLink", "hangout_link", "htmlLink", "html_link"):
        uri = (event.get(key) or "").strip()
        if "meet.google.com" in uri:
            return uri
    conference = event.get("conferenceData") or event.get("conference_data") or {}
    if not isinstance(conference, dict):
        conference = {}
    for point in conference.get("entryPoints") or conference.get("entry_points") or []:
        if not isinstance(point, dict):
            continue
        uri = (point.get("uri") or "").strip()
        kind = (point.get("entryPointType") or point.get("entry_point_type") or "").lower()
        if uri and (kind == "video" or "meet.google.com" in uri):
            return uri
    return ""


def _conference() -> dict:
    return {
        "createRequest": {
            "requestId": uuid.uuid4().hex,
            "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }
    }


def _notify(body: dict) -> dict:
    body["sendUpdates"] = "all"
    body["send_updates"] = "all"
    return body


def _stamp(raw: str) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def create(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    meet: bool = False,
    attendees: list[str] | None = None,
    recurrence: list[str] | None = None,
    calendar_id: str = "",
    account: str = "",
) -> dict:
    account, calendar_id = accounts_mod.route(account, calendar_id)
    body = {
        "summary": summary,
        "start": start,
        "end": end,
        "time_zone": str(zone()),
        "calendar_id": calendar_id,
        "account": account,
    }
    if description:
        body["description"] = description
    if meet:
        conference = _conference()
        body["conferenceDataVersion"] = 1
        body["conference_data_version"] = 1
        body["conferenceData"] = conference
        body["conference_data"] = conference
    people = [addr for addr in (attendees or []) if addr]
    if people:
        body["attendees"] = [{"email": addr} for addr in people]
        _notify(body)
    rules = [rule for rule in (recurrence or []) if rule]
    if rules:
        body["recurrence"] = rules
    payload = call("calendar.events.create", body)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    accounts_mod.record("calendar", "create", account, calendar_id, str((data or {}).get("id") or ""))
    if meet:
        payload["hangout"] = meet_link(payload)
    return payload


def update(event_id: str, calendar_id: str, account: str, **fields) -> dict:
    account, calendar_id = accounts_mod.route(account, calendar_id)
    body = {"event_id": event_id, "calendar_id": calendar_id, "account": account}
    body.update(fields)
    payload = call("calendar.events.update", body)
    accounts_mod.record("calendar", "update", account, calendar_id, event_id)
    return payload


def move(
    event_id: str,
    start: str,
    end: str = "",
    calendar_id: str = "",
    account: str = "",
    when: datetime | None = None,
) -> dict:
    if not end:
        found = next((item for item in events_on(when, calendar_id, account) if item.get("id") == event_id), None)
        if not found or not found.get("start") or not found.get("end"):
            raise SystemExit("move needs --end (event not on that day)")
        end = (_stamp(start) + (_stamp(found["end"]) - _stamp(found["start"]))).isoformat()
    return update(event_id, calendar_id, account, start=start, end=end, **_notify({}))


def cancel(event_id: str, calendar_id: str = "", account: str = "") -> dict:
    account, calendar_id = accounts_mod.route(account, calendar_id)
    payload = call(
        "calendar.events.delete",
        _notify(
            {
                "event_id": event_id,
                "calendar_id": calendar_id,
                "account": account,
            }
        ),
    )
    accounts_mod.record("calendar", "cancel", account, calendar_id, event_id)
    return payload


def invite(
    event_id: str,
    attendees: list[str],
    calendar_id: str = "",
    account: str = "",
    meet: bool = False,
    when: datetime | None = None,
) -> dict:
    people = [addr for addr in attendees if addr]
    if not people:
        raise SystemExit("invite needs at least one email")
    found = event_by_id(event_id, calendar_id, account)
    have = {addr.casefold() for addr in people}
    for addr in found["attendees"]:
        mail = addr.casefold()
        if mail not in have:
            people.append(mail)
            have.add(mail)
    fields: dict = _notify({"attendees": [{"email": addr} for addr in people]})
    if meet:
        conference = _conference()
        fields["conferenceDataVersion"] = 1
        fields["conference_data_version"] = 1
        fields["conferenceData"] = conference
        fields["conference_data"] = conference
    payload = update(event_id, calendar_id, account, **fields)
    payload["hangout"] = meet_link(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Plow Calendar over REST (no Latch).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    today = sub.add_parser("today")
    today.add_argument("--calendar-id", default="")
    today.add_argument("--account", default="")
    on = sub.add_parser("on")
    on.add_argument("--date", required=True, help="YYYY-MM-DD")
    on.add_argument("--calendar-id", default="")
    on.add_argument("--account", default="")
    make = sub.add_parser("create")
    make.add_argument("--summary", required=True)
    make.add_argument("--start", required=True)
    make.add_argument("--end", required=True)
    make.add_argument("--description", default="")
    make.add_argument("--meet", action="store_true", help="attach a Google Meet link")
    make.add_argument("--to", action="append", default=[], help="invitee email (repeatable)")
    make.add_argument("--calendar-id", default="")
    make.add_argument("--account", default="")
    shift = sub.add_parser("move")
    shift.add_argument("--id", required=True)
    shift.add_argument("--start", required=True)
    shift.add_argument("--end", default="")
    shift.add_argument("--calendar-id", default="")
    shift.add_argument("--account", default="")
    shift.add_argument("--date", default="")
    drop = sub.add_parser("cancel")
    drop.add_argument("--id", required=True)
    drop.add_argument("--calendar-id", default="")
    drop.add_argument("--account", default="")
    guest = sub.add_parser("invite")
    guest.add_argument("--id", required=True)
    guest.add_argument("--to", action="append", default=[], help="invitee email (repeatable)")
    guest.add_argument("--meet", action="store_true")
    guest.add_argument("--calendar-id", default="")
    guest.add_argument("--account", default="")
    guest.add_argument("--date", default="")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(call("status"), ensure_ascii=False))
        return 0
    if args.cmd == "today":
        print(json.dumps({"events": events_today(args.calendar_id, args.account)}, ensure_ascii=False))
        return 0
    if args.cmd == "on":
        when = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=zone())
        print(json.dumps({"date": args.date, "events": events_on(when, args.calendar_id, args.account)}, ensure_ascii=False))
        return 0
    if args.cmd == "move":
        when = None
        if args.date:
            when = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=zone())
        print(
            json.dumps(
                move(args.id, args.start, args.end, args.calendar_id, args.account, when=when),
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "cancel":
        print(json.dumps(cancel(args.id, args.calendar_id, args.account), ensure_ascii=False))
        return 0
    if args.cmd == "invite":
        people = emails_in(" ".join(args.to))
        when = None
        if args.date:
            when = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=zone())
        print(
            json.dumps(
                invite(args.id, people, args.calendar_id, args.account, meet=args.meet, when=when),
                ensure_ascii=False,
            )
        )
        return 0
    people = emails_in(" ".join(args.to))
    print(
        json.dumps(
            create(
                args.summary,
                args.start,
                args.end,
                args.description,
                meet=args.meet,
                attendees=people,
                calendar_id=args.calendar_id,
                account=args.account,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
