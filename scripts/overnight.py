#!/usr/bin/env python3
"""Overnight mail → calendar already updated, or a yes sitting on the Kindle.

Clear time change ("mudou para as 11h") updates Google before the edition
mails. A question ("podemos remarcar?") does not — it lands under
"needs your yes today". WhatsApp/iMessage to a personal number is invisible;
Gmail and Calendar invites are not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gcal as gcal_mod  # noqa: E402
import gmail as gmail_mod  # noqa: E402

STOP = {
    "reuniao", "meeting", "hoje", "today", "para", "that", "this", "with",
    "from", "your", "voce", "sobre", "about", "como", "gmail", "calendar",
    "updated", "invitation", "convite", "email", "mensagem",
}
ASK = re.compile(
    r"(\?|\bpodemos\b|\bpode\b|\bconsegues?\b|\bcan we\b|\bcould we\b|\bwould you\b|\bok if\b)",
    re.I,
)
MOVED = re.compile(
    r"\b(mudou|mudei|mudar|passou|passar|adiad[oa]|moved?|reschedul\w*|updated?|atualizad[oa])\b",
    re.I,
)
CANCEL = re.compile(r"\b(cancelou|cancelad[oa]|canceled|cancelled)\b", re.I)
TIME = re.compile(
    r"\b(?:às?|as|at|pra|para as|para às)?\s*(\d{1,2})(?:[:hH](\d{2}))?\s*(h|hrs?|am|pm)?\b",
    re.I,
)
WAITING = re.compile(
    r"\b(re:|fwd:|urgente|prazo|deadline|esperando|waiting|responda|please reply)\b",
    re.I,
)
PAY = re.compile(
    r"(lembrete de pagamento|pagamento (pendente|em atraso|vencid)|"
    r"\b(boleto|fatura|cobran[cç]a|vencimento|pagamento)\b|"
    r"\b(pague|pagar|pay now|payment due|amount due|invoice due|"
    r"bill due|overdue)\b)",
    re.I,
)
GOOGLE_CAL = ("calendar-notification", "calendar.google.com", "google calendar")
LANES = ("work", "life", "reading", "hobby")


def _tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z0-9]+", folded) if len(t) > 3 and t not in STOP}


def _blob(msg: dict) -> str:
    return " ".join(
        str(msg.get(k) or "") for k in ("subject", "snippet", "plain", "from")
    )


def _parse_time(text: str, day: datetime) -> datetime | None:
    hits = []
    for match in TIME.finditer(text or ""):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        suffix = (match.group(3) or "").lower()
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            continue
        hits.append(day.replace(hour=hour, minute=minute, second=0, microsecond=0))
    if not hits:
        return None
    return hits[-1]


def _start(event: dict) -> datetime | None:
    raw = event.get("start") or ""
    if isinstance(raw, dict):
        raw = raw.get("dateTime") or raw.get("dateTime") or raw.get("date") or ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _end(event: dict, start: datetime) -> datetime:
    raw = event.get("end") or ""
    if isinstance(raw, dict):
        raw = raw.get("dateTime") or raw.get("date") or ""
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            pass
    return start + timedelta(minutes=60)


def _known_bits(state: dict, lane: str) -> list[str]:
    out = []
    for item in (state.get("known") or {}).get(lane) or []:
        text = item.get("text") if isinstance(item, dict) else str(item)
        if str(text).strip():
            out.append(str(text).strip())
    return out


def sphere_tokens(state: dict | None) -> dict[str, set[str]]:
    """Vocabulary this person already gave — not a global keyword list."""
    state = state or {}
    profile = state.get("profile") or {}
    goals = state.get("goals") or {}
    out: dict[str, set[str]] = {lane: set() for lane in LANES}
    for cat in ("work", "life"):
        about = profile.get(f"{cat}_about") or []
        if isinstance(about, str):
            about = [about]
        bits = [goals.get(cat) or "", " ".join(str(x) for x in about), *_known_bits(state, cat)]
        for task in state.get("tasks") or []:
            if task.get("category") == cat and not task.get("done"):
                bits.append(str(task.get("text") or ""))
        out[cat] = _tokens(" ".join(bits))
    out["reading"] = _tokens(" ".join(_known_bits(state, "reading")))
    hobby_bits = _known_bits(state, "hobby") + [str(x) for x in (profile.get("interests") or [])]
    out["hobby"] = _tokens(" ".join(hobby_bits))
    return out


def guess_lane(text: str, spheres: dict[str, set[str]]) -> str:
    blob = _tokens(text)
    scores = {lane: len(blob & (spheres.get(lane) or set())) for lane in LANES}
    best = max(scores.values()) if scores else 0
    if not best:
        return ""
    tied = [lane for lane, score in scores.items() if score == best]
    for prefer in LANES:
        if prefer in tied:
            return prefer
    return tied[0]


def guess_sphere(text: str, spheres: dict[str, set[str]]) -> str:
    lane = guess_lane(text, spheres)
    return lane if lane in ("work", "life") else ""


def match_event(text: str, events: list[dict]) -> dict | None:
    tokens = _tokens(text)
    scored: list[tuple[int, dict]] = []
    for event in events:
        overlap = len(tokens & _tokens(str(event.get("summary") or "")))
        if overlap:
            scored.append((overlap, event))
    if not scored:
        return events[0] if len(events) == 1 else None
    scored.sort(key=lambda item: -item[0])
    if len(scored) == 1 or scored[0][0] > scored[1][0]:
        return scored[0][1]
    return None


def classify(msg: dict, events: list[dict], day: datetime, spheres: dict | None = None) -> dict:
    blob = _blob(msg)
    subject = (msg.get("subject") or "").strip()
    sender = (msg.get("from") or "").lower()
    line = subject or (msg.get("snippet") or "")[:120]
    spheres = spheres or {}
    lane = guess_lane(blob, spheres)
    sphere = lane if lane in ("work", "life") else ""
    base = {"text": line, "msg": msg, "sphere": sphere, "lane": lane, "important": False}
    if any(tag in sender or tag in blob.lower() for tag in GOOGLE_CAL):
        return {**base, "kind": "already"}
    if PAY.search(blob):
        return {
            **base,
            "kind": "need",
            "important": True,
            "sphere": sphere or "life",
            "why": "pay",
        }
    if ASK.search(blob):
        return {**base, "kind": "approval", "important": True}
    when = _parse_time(blob, day)
    if CANCEL.search(blob) and not when:
        return {**base, "kind": "approval", "important": True}
    if when and MOVED.search(blob):
        event = match_event(blob, events)
        if event:
            if not sphere:
                sphere = guess_sphere(str(event.get("summary") or ""), spheres)
            return {**base, "kind": "move", "event": event, "when": when, "sphere": sphere, "important": True}
        return {**base, "kind": "approval", "important": True}
    if MOVED.search(blob) or CANCEL.search(blob):
        return {**base, "kind": "approval", "important": True}
    waiting = WAITING.search(blob) or any(k in blob.lower() for k in ("re:", "fwd:"))
    if waiting and (sphere or lane in ("reading", "hobby")):
        return {
            **base,
            "kind": "need",
            "important": True,
            "sphere": sphere or "life",
        }
    if lane == "reading":
        return {**base, "kind": "reading"}
    if lane == "hobby":
        return {**base, "kind": "hobby"}
    return {**base, "kind": "skip"}


def apply_move(event: dict, when: datetime) -> dict:
    start = _start(event) or when
    duration = _end(event, start) - start
    new_end = when + duration
    calendar_id = event.get("calendar_id") or "primary"
    account = event.get("account") or ""
    gcal_mod.update(
        event["id"],
        calendar_id,
        account,
        start=when.isoformat(),
        end=new_end.isoformat(),
    )
    event["start"] = when.isoformat()
    event["end"] = new_end.isoformat()
    return {
        "text": f"{event.get('summary')} → {when.strftime('%H:%M')}",
        "event_id": event.get("id"),
    }


def run(
    avoid: list[str] | None = None,
    apply: bool = True,
    messages: list[dict] | None = None,
    events: list[dict] | None = None,
    now: datetime | None = None,
    state: dict | None = None,
) -> dict:
    now = now or datetime.now().astimezone()
    avoid = [a.lower() for a in (avoid or []) if a]
    spheres = sphere_tokens(state)
    if events is None:
        try:
            events = gcal_mod.events_today()
        except SystemExit:
            events = []
    if messages is None:
        try:
            messages = gmail_mod.list_messages(max_results=15)
        except SystemExit:
            messages = []
    applied, approvals, needs, already, readings, hobbies = [], [], [], [], [], []
    for msg in messages:
        blob = _blob(msg).lower()
        if any(term in blob for term in avoid):
            continue
        noisy = any(term in blob for term in gmail_mod.NOISE)
        item = classify(msg, events, now, spheres)
        if noisy and item["kind"] == "skip":
            continue
        snippet = (msg.get("snippet") or msg.get("plain") or "").strip()
        row = {
            "text": item["text"],
            "summary": snippet[:160] if snippet.casefold() != item["text"].casefold() else "",
            "sphere": item.get("sphere") or "",
            "important": bool(item.get("important")),
            "why": item.get("why") or "",
        }
        if item["kind"] == "move" and apply:
            try:
                applied.append({**apply_move(item["event"], item["when"]), "sphere": row["sphere"]})
            except (SystemExit, KeyError) as exc:
                approvals.append({**row, "reason": str(exc)})
        elif item["kind"] == "move":
            applied.append(
                {
                    "text": f"{item['event'].get('summary')} → {item['when'].strftime('%H:%M')}",
                    "sphere": row["sphere"],
                }
            )
        elif item["kind"] == "approval":
            approvals.append(row)
        elif item["kind"] == "need":
            needs.append(row)
        elif item["kind"] == "already":
            already.append(row)
        elif item["kind"] == "reading":
            readings.append(row)
        elif item["kind"] == "hobby":
            hobbies.append(row)
    return {
        "applied": applied[:8],
        "approvals": approvals[:8],
        "fires": needs[:6],
        "needs": needs[:6],
        "already": already[:6],
        "readings": _unique_lines(_known_bits(state or {}, "reading"), readings),
        "hobbies": _unique_lines(_known_bits(state or {}, "hobby"), hobbies),
        "meetings": [
            f"{(e.get('start') or '')} {e.get('summary')}" for e in events
        ],
        "spheres": {k: sorted(v) for k, v in spheres.items()},
    }


def _unique_lines(known: list[str], items: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for text in list(known) + [item.get("text") or "" for item in items]:
        key = text.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text.strip())
    return out[:8]


def lines(report: dict, pt: bool = False) -> list[str]:
    out: list[str] = []
    for item in report.get("applied") or []:
        prefix = "Agenda atualizada: " if pt else "Calendar updated: "
        out.append(prefix + item["text"])
    for item in report.get("already") or []:
        prefix = "Convite já na agenda: " if pt else "Invite already on the calendar: "
        out.append(prefix + item["text"])
    for item in report.get("approvals") or []:
        prefix = "Precisa do teu sim: " if pt else "Needs your yes: "
        out.append(prefix + item["text"])
    for item in report.get("fires") or []:
        prefix = "Precisa de ti: " if pt else "Needs you: "
        out.append(prefix + item["text"])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply overnight mail to calendar / list approvals.")
    parser.add_argument("--no-apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=not args.no_apply), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
