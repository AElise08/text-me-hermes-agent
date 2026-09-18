import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import accounts
import day
import triggers


class FollowupTests(unittest.TestCase):
    def test_reminder_cli_persists_and_acknowledges(self):
        with tempfile.TemporaryDirectory() as home:
            def cli(*args):
                return json.loads(subprocess.check_output(
                    [sys.executable, str(SCRIPTS / "matriz.py"), *args],
                    env={**os.environ, "HERMES_HOME": home}, text=True))
            item = cli("trigger", "add", "--text", "Check registration", "--at", "2020-01-01T09:00:00-05:00")["created"]
            self.assertEqual(cli("trigger", "check")["triggers"], [item])
            self.assertEqual(cli("morning")["triggers"], [item])
            cli("trigger", "done", item["id"])
            self.assertEqual(cli("trigger", "check")["triggers"], [])

    def test_task_and_timed_reminders_wait_and_can_be_closed(self):
        state = {"tasks": [{"id": "review", "done": False}]}
        task = triggers.add(state, "Send the paper", after_task="review")
        timed = triggers.add(state, "Check email", at="2026-09-20T09:00:00-04:00")
        now = datetime.fromisoformat("2026-09-20T12:59:00+00:00")
        self.assertEqual(triggers.ready(state, now), [])
        state["tasks"][0]["done"] = True
        self.assertEqual(triggers.ready(state, now), [task])
        task["status"] = "done"
        self.assertEqual(triggers.ready(state, datetime.fromisoformat("2026-09-20T13:00:00+00:00")), [timed])

    def test_invalid_trigger_is_not_saved(self):
        state = {}
        for args in ({"at": "2026-09-20T09:00:00"}, {"after_task": "missing"}):
            with self.assertRaises(SystemExit):
                triggers.add(state, "Reminder", **args)
        self.assertNotIn("triggers", state)

    def test_conflict_options_avoid_all_busy_events(self):
        target = {"start": "2026-09-20T09:00:00-03:00", "end": "2026-09-20T10:00:00-03:00"}
        busy = [{"start": "2026-09-20T08:00:00-03:00", "end": "2026-09-20T09:20:00-03:00"}]
        options = day.resolution_options(target, busy)
        self.assertEqual([x["action"] for x in options], ["move", "shorten"])
        self.assertEqual(options[0]["end"], "2026-09-20T10:20:00-03:00")
        self.assertEqual(options[1]["end"], target["end"])
        self.assertTrue(all(x["requires_confirmation"] and not day.overlaps(x, busy[0]) for x in options))

    def test_account_override_does_not_inherit_another_calendar(self):
        with patch.object(accounts, "settings", return_value={"accounts": [], "default_account": "a@example.com", "default_calendar_id": "private"}):
            self.assertEqual(accounts.route("b@example.com"), ("b@example.com", "primary"))
            with self.assertRaises(SystemExit):
                accounts.route("Unknown")

    def test_english_and_portuguese_tomorrow_match(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HERMES_HOME": home}
            results = []
            for text in ("tomorrow class at 9:00 until 10:00", "amanhã aula às 9:00 até 10:00"):
                result = subprocess.check_output([sys.executable, str(SCRIPTS / "matriz.py"), "day", "--text", text], env=env, text=True)
                results.append(json.loads(result)["date"])
            self.assertEqual(results[0], results[1])
