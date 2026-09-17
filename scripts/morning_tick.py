#!/usr/bin/env python3
"""Once-a-day tick: mail the edition at dispatch time, chat only if needed.

Kindle/printer success → no SMS (the artifact is the page, not the phone).
Send failure → one SMS. Chat destination → the short nudge.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import schedule as schedule_mod  # noqa: E402

home = Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
script = home / "scripts" / "matriz.py"
if not script.exists():
    script = HERE / "matriz.py"


def main() -> int:
    now = datetime.now(schedule_mod.zone())
    profile = schedule_mod.load_profile()
    today = now.date().isoformat()
    if schedule_mod.stamped_day() == today:
        print("[SILENT]")
        return 0
    try:
        built = json.loads(subprocess.check_output(["python3", str(script), "edition"], text=True))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        built = {"sent": False, "send_error": "edition failed"}
    dest = (profile.get("delivery") or built.get("delivery") or "message").strip()
    sent = bool(built.get("sent"))
    lang = ""
    try:
        state = json.loads((home / ".matriz" / "state.json").read_text(encoding="utf-8"))
        lang = (state.get("language") or "").lower()
    except (OSError, json.JSONDecodeError):
        pass
    pt = lang.startswith("pt")
    if dest in ("kindle", "printer") and sent:
        schedule_mod.mark_sent(today)
        print("[SILENT]")
        return 0
    if dest in ("kindle", "printer", "email") and not sent:
        retry = schedule_mod.mark_retry(today, now)
        err = built.get("send_error") or built.get("ipp_error") or "not sent"
        if retry["attempts"] > 1:
            print("[SILENT]")
            return 0
        if pt:
            print(f"A edição das {schedule_mod.hour(profile):02d}h não chegou no {dest}. Vou tentar de novo em {retry['retry_at'][11:16]}. {err}")
        else:
            print(f"Today's {dest} edition did not land. I will retry at {retry['retry_at'][11:16]}. {err}")
        return 0
    # Message has no provider receipt, but the edition was built successfully.
    # Email already has a successful provider send at this point.
    schedule_mod.mark_sent(today)
    env = {**os.environ, "TEXT_ME_SKIP_EDITION": "1"}
    sys.stdout.write(subprocess.check_output(["python3", str(HERE / "morning_nudge.py")], env=env, text=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
