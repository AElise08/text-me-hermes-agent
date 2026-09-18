"""Persistent reminders evaluated by the morning check or an explicit chat check."""
from datetime import datetime
from uuid import uuid4


def add(state, text, at="", after_task=""):
    if not text.strip() or bool(at) == bool(after_task):
        raise SystemExit("provide text and exactly one of --at or --after-task")
    if at:
        try:
            stamp = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            raise SystemExit("--at needs an ISO date/time with timezone")
        if stamp.tzinfo is None:
            raise SystemExit("--at needs a timezone offset")
        at = stamp.isoformat()
    if after_task and not any(t["id"] == after_task for t in state.get("tasks", [])):
        raise SystemExit("unknown task id")
    item = {"id": uuid4().hex[:12], "text": text.strip(), "at": at,
            "after_task": after_task, "status": "pending"}
    state.setdefault("triggers", []).append(item)
    return item


def ready(state, now):
    completed = {t["id"] for t in state.get("tasks", []) if t.get("done")}
    return [t for t in state.get("triggers", []) if t["status"] == "pending" and (
        (t.get("after_task") and t["after_task"] in completed) or
        (t.get("at") and datetime.fromisoformat(t["at"]) <= now)
    )]
