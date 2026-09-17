#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import dates as dates_mod  # noqa: E402
import day as day_mod  # noqa: E402
import duration as duration_mod  # noqa: E402
import edition as edition_mod  # noqa: E402
import gcal as gcal_mod  # noqa: E402
import gmail as gmail_mod  # noqa: E402
import overnight as overnight_mod  # noqa: E402
import printer as printer_mod  # noqa: E402
import research as research_mod  # noqa: E402

CATS = ("work", "life")
LANES = ("work", "life", "reading", "hobby")
QS = ("Q1", "Q2", "Q3", "Q4")
DELIVERIES = ("kindle", "printer", "message", "email")


def home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))


def path() -> Path:
    return home() / ".matriz" / "state.json"


def blank_profile() -> dict:
    return {
        "setup_done": False,
        "name": "",
        "routine": "",
        "interests": [],
        "avoid": [],
        "delivery": "",
        "kindle_email": "",
        "printer_email": "",
        "printer_uri": "",
        "work_about": [],
        "life_about": [],
        "edition_hour": 7,
        "timezone": "",
        "charge": False,
    }


def blank() -> dict:
    return {
        "goals": {"work": "", "life": ""},
        "tasks": [],
        "language": "",
        "profile": blank_profile(),
        "durations": {},
        "blocks": [],
        "commitments": [],
        "known": {lane: [] for lane in LANES},
        "slots": [],
    }


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return blank()
    if "goals" not in data:
        data["goals"] = {"work": data.pop("goal", ""), "life": ""}
    data.setdefault("language", "")
    data.setdefault("profile", blank_profile())
    data["profile"] = {**blank_profile(), **data["profile"]}
    data.setdefault("durations", {})
    data.setdefault("blocks", [])
    data.setdefault("commitments", [])
    data.setdefault("slots", [])
    data.setdefault("known", {lane: [] for lane in LANES})
    for lane in LANES:
        data["known"].setdefault(lane, [])
    for task in data.setdefault("tasks", []):
        task.setdefault("category", "work")
        task.setdefault("due", "")
    return data


def save(data: dict) -> None:
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(target)


def yn(value: str) -> bool:
    return {"yes": True, "no": False}[value]


def quad(important: bool, urgent: bool) -> str:
    if important and urgent:
        return "Q1"
    if important:
        return "Q2"
    if urgent:
        return "Q3"
    return "Q4"


def public(task: dict) -> dict:
    keys = ("id", "text", "category", "quadrant", "reason", "done", "due")
    return {key: task.get(key, "") if key != "done" else task.get(key, False) for key in keys}


def grouped(tasks: list) -> dict:
    return {
        cat: {
            q: [public(t) for t in tasks if t.get("category") == cat and t.get("quadrant") == q]
            for q in QS
        }
        for cat in CATS
    }


def find(items: list, item_id: str) -> dict:
    match = next((item for item in items if item.get("id") == item_id), None)
    if not match:
        raise SystemExit("not found")
    return match


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def _aware(stamp: str) -> datetime:
    stamp = stamp.strip()
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _stamp_key(value: str) -> str:
    try:
        return _aware(value).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return (value or "")[:16]


def add_slot(data: dict, text: str, start: str, end: str, kind: str = "commitment") -> dict:
    """Put a named interval on the calendar: class, physio, the free window — all of them."""
    text = text.strip()
    start_dt = _aware(start)
    end_dt = _aware(end)
    if end_dt <= start_dt:
        raise SystemExit("end must be after start")
    data.setdefault("slots", [])
    key = (_stamp_key(start_dt.isoformat()), text.casefold())
    for existing in list(data["slots"]) + list(data.get("blocks") or []):
        when = existing.get("start") or existing.get("when") or ""
        if (_stamp_key(str(when)), str(existing.get("text") or "").casefold()) == key:
            return {"skipped": "duplicate", "existing": existing}
    item = {
        "id": new_id(),
        "text": text,
        "kind": kind or "commitment",
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "status": "open",
        "calendar": None,
    }
    if gcal_mod.token():
        try:
            created = gcal_mod.create(
                text,
                start_dt.isoformat(),
                end_dt.isoformat(),
                description="text-me",
            )
            item["calendar"] = created.get("data") or created
        except SystemExit as exc:
            item["calendar_error"] = str(exc)
    data["slots"].append(item)
    return {"created": item}


def _known_text(item) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "").strip()
    return str(item).strip()


def learn(data: dict, sphere: str, text: str, source: str = "chat") -> dict:
    """Save what we discovered for this person: investor → work, book → reading."""
    if sphere not in LANES:
        raise SystemExit("sphere must be work, life, reading or hobby")
    text = text.strip()
    if not text:
        raise SystemExit("nothing to learn")
    data.setdefault("known", {lane: [] for lane in LANES})
    for other in LANES:
        if other == sphere:
            continue
        data["known"][other] = [
            item for item in data["known"].get(other) or [] if _known_text(item).casefold() != text.casefold()
        ]
    bucket = data["known"].setdefault(sphere, [])
    if not any(_known_text(item).casefold() == text.casefold() for item in bucket):
        bucket.append({"text": text, "source": source})
    return {"known": data["known"], "learned": {"sphere": sphere, "text": text}}


def dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def delivery_address(profile: dict) -> str:
    delivery = profile.get("delivery") or ""
    if delivery == "kindle":
        return (os.environ.get("KINDLE_EMAIL") or profile.get("kindle_email") or "").strip()
    if delivery == "printer":
        return (os.environ.get("PRINTER_EMAIL") or profile.get("printer_email") or "").strip()
    if delivery == "email":
        if gcal_mod.token():
            try:
                return (gmail_mod.profile().get("emailAddress") or "").strip()
            except SystemExit:
                return ""
        return ""
    return ""


def deliver_edition(profile: dict, files: dict, title: str) -> dict:
    delivery = profile.get("delivery") or ""
    out: dict = {"sent": False}
    to = delivery_address(profile)
    attach = Path(files["epub"] if delivery == "kindle" else files.get("pdf") or files["epub"])
    if to and gcal_mod.token():
        try:
            if delivery == "kindle":
                result = gmail_mod.send_kindle(to, attach, title)
            else:
                result = gmail_mod.send(
                    to,
                    title,
                    "Daily edition from text-me.",
                    files=[attach],
                )
            out.update({"sent": True, "to": to, "gmail": result, "file": str(attach)})
        except SystemExit as exc:
            out["send_error"] = str(exc)
    ipp = (os.environ.get("PRINTER_URI") or profile.get("printer_uri") or "").strip()
    if delivery == "printer" and ipp:
        try:
            out["ipp"] = printer_mod.send(Path(files["pdf"]), ipp)
            out["sent"] = True
        except SystemExit as exc:
            out["ipp_error"] = str(exc)
    return out


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    goal = sub.add_parser("goal")
    goal_sub = goal.add_subparsers(dest="action", required=True)
    show_goal = goal_sub.add_parser("show")
    show_goal.add_argument("--category", choices=CATS)
    set_goal = goal_sub.add_parser("set")
    set_goal.add_argument("--category", choices=CATS, required=True)
    set_goal.add_argument("--text", required=True)

    lang = sub.add_parser("language")
    lang_sub = lang.add_subparsers(dest="action", required=True)
    lang_sub.add_parser("show")
    set_lang = lang_sub.add_parser("set")
    set_lang.add_argument("value")

    add = sub.add_parser("add")
    add.add_argument("--text", required=True)
    add.add_argument("--category", choices=CATS, required=True)
    add.add_argument("--important", choices=["yes", "no"], required=True)
    add.add_argument("--urgent", choices=["yes", "no"], required=True)
    add.add_argument("--reason", default="")
    add.add_argument("--due", default="")

    show = sub.add_parser("show")
    show.add_argument("--include-done", action="store_true")
    sub.add_parser("morning")

    done = sub.add_parser("done")
    done.add_argument("id")

    update = sub.add_parser("update")
    update.add_argument("id")
    update.add_argument("--category", choices=CATS)
    update.add_argument("--important", choices=["yes", "no"])
    update.add_argument("--urgent", choices=["yes", "no"])
    update.add_argument("--reason")
    update.add_argument("--text")
    update.add_argument("--due")

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="action", required=True)
    profile_sub.add_parser("show")
    set_profile = profile_sub.add_parser("set")
    set_profile.add_argument("--name")
    set_profile.add_argument("--routine")
    set_profile.add_argument("--delivery", choices=DELIVERIES)
    set_profile.add_argument("--kindle-email")
    set_profile.add_argument("--printer-email")
    set_profile.add_argument("--printer-uri")
    set_profile.add_argument("--interests")
    set_profile.add_argument("--avoid")
    set_profile.add_argument("--work-about")
    set_profile.add_argument("--life-about")
    set_profile.add_argument("--edition-hour", type=int)
    set_profile.add_argument("--timezone", help="IANA name, e.g. America/Belem")
    set_profile.add_argument("--charge", choices=["yes", "no"], help="editorial cartoon on the morning page")
    set_profile.add_argument("--done", action="store_true")

    known = sub.add_parser("learn")
    known_sub = known.add_subparsers(dest="action", required=True)
    add_k = known_sub.add_parser("add")
    add_k.add_argument("--sphere", choices=LANES, required=True)
    add_k.add_argument("--text", required=True)
    add_k.add_argument("--source", default="chat")
    known_sub.add_parser("show")

    dur = sub.add_parser("duration")
    dur_sub = dur.add_subparsers(dest="action", required=True)
    suggest = dur_sub.add_parser("suggest")
    suggest.add_argument("--activity", required=True)
    suggest.add_argument("--asked", type=int, required=True)
    record = dur_sub.add_parser("record")
    record.add_argument("--activity", required=True)
    record.add_argument("--asked", type=int, required=True)
    record.add_argument("--actual", type=int, required=True)

    block = sub.add_parser("block")
    block_sub = block.add_subparsers(dest="action", required=True)
    start = block_sub.add_parser("start")
    start.add_argument("--text", required=True)
    start.add_argument("--minutes", type=int, required=True)
    start.add_argument("--when", default="")
    extend = block_sub.add_parser("extend")
    extend.add_argument("id")
    extend.add_argument("--minutes", type=int, required=True)
    close = block_sub.add_parser("close")
    close.add_argument("id")
    block_sub.add_parser("list")

    commit = sub.add_parser("commit")
    commit_sub = commit.add_subparsers(dest="action", required=True)
    add_c = commit_sub.add_parser("add")
    add_c.add_argument("--text", required=True)
    add_c.add_argument("--after-task")
    add_c.add_argument("--after-url")
    add_c.add_argument("--html")
    add_c.add_argument("--probable", action="store_true")
    commit_sub.add_parser("list")
    close_c = commit_sub.add_parser("close")
    close_c.add_argument("id")

    slot = sub.add_parser("slot")
    slot_sub = slot.add_subparsers(dest="action", required=True)
    add_s = slot_sub.add_parser("add")
    add_s.add_argument("--text", required=True)
    add_s.add_argument("--start", required=True)
    add_s.add_argument("--end", required=True)
    add_s.add_argument("--kind", default="commitment")
    slot_sub.add_parser("list")

    day_p = sub.add_parser("day")
    day_p.add_argument("--text", required=True, help="The person's dump of the day, with clock times")
    day_p.add_argument("--date", default="", help="YYYY-MM-DD, default tomorrow if they said amanhã")

    edition = sub.add_parser("edition")
    edition.add_argument("--title", default="")
    edition.add_argument("--no-send", action="store_true")
    edition.add_argument(
        "--extra-file",
        default="",
        help="JSON with researched material: clips, focus, readings, hobbies, title",
    )

    return parser.parse_args()


def main() -> None:
    args = parse()
    data = load()

    if args.cmd == "goal":
        if args.action == "set":
            data["goals"][args.category] = args.text.strip()
            save(data)
        if getattr(args, "category", None):
            dump({"category": args.category, "goal": data["goals"][args.category]})
        else:
            dump({"goals": data["goals"]})
        return

    if args.cmd == "language":
        if args.action == "set":
            data["language"] = args.value.strip().lower()
            save(data)
        dump({"language": data["language"]})
        return

    if args.cmd == "add":
        important, urgent = yn(args.important), yn(args.urgent)
        task = {
            "id": new_id(),
            "text": args.text.strip(),
            "category": args.category,
            "important": important,
            "urgent": urgent,
            "quadrant": quad(important, urgent),
            "reason": args.reason.strip(),
            "due": args.due.strip(),
            "done": False,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        data["tasks"].append(task)
        save(data)
        dump({"created": public(task)})
        return

    if args.cmd in ("done", "update"):
        task = find(data["tasks"], args.id)
        if args.cmd == "done":
            task["done"] = True
        else:
            for key in ("category", "reason", "text", "due"):
                value = getattr(args, key, None)
                if value is not None:
                    task[key] = value.strip()
            if args.important:
                task["important"] = yn(args.important)
            if args.urgent:
                task["urgent"] = yn(args.urgent)
            task["quadrant"] = quad(task["important"], task["urgent"])
        save(data)
        dump({"updated": public(task)})
        return

    if args.cmd == "profile":
        profile = data["profile"]
        if args.action == "set":
            if args.name is not None:
                profile["name"] = args.name.strip()
            if args.routine is not None:
                profile["routine"] = args.routine.strip()
            if args.delivery:
                profile["delivery"] = args.delivery
            if args.kindle_email is not None:
                profile["kindle_email"] = args.kindle_email.strip()
            if args.printer_email is not None:
                profile["printer_email"] = args.printer_email.strip()
            if args.printer_uri is not None:
                profile["printer_uri"] = args.printer_uri.strip()
            if args.interests is not None:
                profile["interests"] = [x.strip() for x in args.interests.split(",") if x.strip()]
            if args.avoid is not None:
                profile["avoid"] = [x.strip() for x in args.avoid.split(",") if x.strip()]
            if args.work_about is not None:
                profile["work_about"] = [x.strip() for x in args.work_about.split(",") if x.strip()]
            if args.life_about is not None:
                profile["life_about"] = [x.strip() for x in args.life_about.split(",") if x.strip()]
            if args.edition_hour is not None:
                profile["edition_hour"] = args.edition_hour
            if args.timezone is not None:
                from zoneinfo import ZoneInfo
                name = args.timezone.strip()
                try:
                    ZoneInfo(name)
                except Exception:
                    sys.exit(f"unknown timezone: {name} (use an IANA name, e.g. America/Belem)")
                profile["timezone"] = name
            if args.charge is not None:
                profile["charge"] = args.charge == "yes"
            if args.done:
                profile["setup_done"] = True
            save(data)
        dump({"profile": profile})
        return

    if args.cmd == "learn":
        if args.action == "add":
            out = learn(data, args.sphere, args.text, args.source)
            save(data)
            dump(out)
            return
        dump({"known": data.get("known") or {lane: [] for lane in LANES}})
        return

    if args.cmd == "duration":
        key = duration_mod.key(args.activity)
        entry = data["durations"].get(key) or {}
        if args.action == "suggest":
            minutes = duration_mod.suggested(entry, args.asked)
            dump({"activity": key, "asked": args.asked, "suggested_minutes": minutes, "samples": len(entry.get("actual") or [])})
            return
        data["durations"][key] = duration_mod.record(entry, args.asked, args.actual)
        save(data)
        dump({"activity": key, "duration": data["durations"][key]})
        return

    if args.cmd == "block":
        if args.action == "list":
            dump({"blocks": data["blocks"]})
            return
        if args.action == "start":
            key = duration_mod.key(args.text)
            entry = data["durations"].get(key) or {}
            planned = duration_mod.suggested(entry, args.minutes)
            block = {
                "id": new_id(),
                "text": args.text.strip(),
                "asked_minutes": args.minutes,
                "planned_minutes": planned,
                "extensions": [],
                "status": "open",
                "when": args.when.strip(),
                "created_at": datetime.now().astimezone().isoformat(),
                "calendar": None,
            }
            if gcal_mod.token():
                start = datetime.fromisoformat(args.when) if args.when.strip() else datetime.now().astimezone()
                end = start + timedelta(minutes=planned)
                try:
                    created = gcal_mod.create(
                        args.text.strip(),
                        start.isoformat(),
                        end.isoformat(),
                        description="text-me focus block",
                    )
                    block["calendar"] = created.get("data") or created
                except SystemExit as exc:
                    block["calendar_error"] = str(exc)
            data["blocks"].append(block)
            save(data)
            dump({"created": block, "used_learned_duration": planned != args.minutes})
            return
        block = find(data["blocks"], args.id)
        if args.action == "extend":
            block.setdefault("extensions", []).append(args.minutes)
        else:
            block["status"] = "done"
            actual = int(block.get("asked_minutes") or 0) + sum(int(x) for x in block.get("extensions") or [])
            if actual <= 0:
                actual = int(block.get("planned_minutes") or 0)
            key = duration_mod.key(block["text"])
            data["durations"][key] = duration_mod.record(
                data["durations"].get(key) or {},
                int(block.get("asked_minutes") or block.get("planned_minutes") or actual),
                actual,
            )
            block["actual_minutes"] = actual
        save(data)
        dump({"updated": block, "durations": data["durations"].get(duration_mod.key(block["text"]))})
        return

    if args.cmd == "commit":
        if args.action == "list":
            dump({"commitments": data["commitments"]})
            return
        if args.action == "close":
            item = find(data["commitments"], args.id)
            item["status"] = "done"
            save(data)
            dump({"updated": item})
            return
        item = {
            "id": new_id(),
            "text": args.text.strip(),
            "status": "open",
            "mode": "probable" if args.probable else "after",
            "after_task": args.after_task or "",
            "after_url": args.after_url or "",
            "after_when": "",
            "dates": [],
        }
        html = args.html or ""
        if html:
            item["dates"] = dates_mod.parse_html(html)
            latest = dates_mod.latest(item["dates"])
            if latest:
                item["after_when"] = latest["iso"]
                item["mode"] = "after_url"
        elif args.after_task:
            item["mode"] = "after_close"
        data["commitments"].append(item)
        save(data)
        dump({"created": item})
        return

    if args.cmd == "slot":
        if args.action == "list":
            dump({"slots": data.get("slots") or []})
            return
        out = add_slot(data, args.text, args.start, args.end, args.kind)
        save(data)
        dump(out)
        return

    if args.cmd == "day":
        # "amanhã" flips at midnight on THEIR clock, not the container's.
        now = edition_mod.as_of()
        blob = args.text.casefold()
        if args.date:
            day = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=now.tzinfo)
        elif re.search(r"\bamanh[ãa]\b", blob):
            day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        planned = day_mod.parse(args.text, day)
        created, skipped = [], []
        for item in planned:
            row = add_slot(data, item["text"], item["start"], item["end"])
            if row.get("created"):
                created.append(row["created"])
            else:
                skipped.append(row)
        save(data)
        dump({"date": day.date().isoformat(), "planned": planned, "created": created, "skipped": skipped})
        return

    if args.cmd == "edition":
        extra = {"title": args.title} if args.title else {}
        profile = data.get("profile") or {}
        lang = data.get("language") or ""
        if gcal_mod.token():
            try:
                report = overnight_mod.run(
                    avoid=profile.get("avoid") or [],
                    apply=not args.no_send,
                    state=data,
                )
            except SystemExit:
                report = {"applied": [], "approvals": [], "fires": [], "already": [], "meetings": []}
            extra["fires"] = report.get("fires") or []
            extra["approvals"] = report.get("approvals") or []
            extra["readings"] = report.get("readings") or []
            extra["hobbies"] = report.get("hobbies") or []
            extra["exceptions"] = overnight_mod.lines(
                {"applied": report.get("applied") or [], "already": report.get("already") or []},
                pt=(data.get("language") or "").lower().startswith("pt"),
            )
            extra["meetings"] = report.get("meetings") or extra.get("meetings") or []
            extra["people"] = [
                item
                for item in list(report.get("approvals") or []) + list(report.get("fires") or [])
                if isinstance(item, dict) and (item.get("who") or "").strip()
            ]
            extra["hold"] = edition_mod.hold_line(data, extra)
            inbox = gmail_mod.inbox_clips(
                profile.get("interests") or [],
                profile.get("avoid") or [],
            )
        else:
            inbox = []
        if not extra.get("meetings"):
            try:
                extra["meetings"] = gcal_mod.day_lines(edition_mod.as_of()) if gcal_mod.token() else []
            except SystemExit:
                extra["meetings"] = extra.get("meetings") or []
        used = " ".join((extra.get("readings") or []) + (extra.get("hobbies") or [])).lower()
        web = research_mod.clips(
            profile.get("interests") or [],
            profile.get("avoid") or [],
            lang,
            goals=data.get("goals") or {},
        )
        merged = []
        seen = set()
        for item in list(web) + list(inbox):
            if isinstance(item, dict):
                key = (item.get("title") or item.get("line") or "").strip().lower()
            else:
                key = str(item).split(" — ")[0].strip().lower()
                item = {
                    "title": str(item).split(" — ")[0].strip(),
                    "happened": str(item).split(" — ", 1)[1].strip() if " — " in str(item) else "",
                    "why": "",
                    "source": "",
                }
            if not key or key in seen or key in used:
                continue
            seen.add(key)
            merged.append(item)
        extra["clips"] = merged[:6]
        if profile.get("charge"):
            extra["charge"] = research_mod.charge(lang)
        if args.extra_file:
            researched = json.loads(Path(args.extra_file).read_text(encoding="utf-8"))
            for key in ("title", "focus", "clips", "readings", "hobbies", "charge", "meetings", "people", "kicker", "approvals", "decisions", "exceptions"):
                if researched.get(key):
                    extra[key] = researched[key]
        dest = home() / ".matriz" / "editions"
        out = edition_mod.dump(data, dest, edition_mod.as_of(), extra)
        if not args.no_send:
            out.update(deliver_edition(profile, out, out["title"]))
        dump(out)
        return

    active = [t for t in data["tasks"] if not t.get("done")]
    if args.cmd == "show":
        tasks = data["tasks"] if args.include_done else active
        dump({"goals": data["goals"], "categories": grouped(tasks), "profile": data["profile"]})
        return

    dump(
        {
            "goals": data["goals"],
            "categories": {
                "work": {
                    "do_now": [public(t) for t in active if t["category"] == "work" and t["quadrant"] == "Q1"][:3],
                    "protect_next": [public(t) for t in active if t["category"] == "work" and t["quadrant"] == "Q2"][:3],
                },
                "life": {
                    "do_now": [public(t) for t in active if t["category"] == "life" and t["quadrant"] == "Q1"][:3],
                    "protect_next": [public(t) for t in active if t["category"] == "life" and t["quadrant"] == "Q2"][:3],
                },
            },
            "active_count": len(active),
            "language": data["language"],
            "profile": data["profile"],
        }
    )


if __name__ == "__main__":
    main()
