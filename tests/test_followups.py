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

    def test_overlaps_naive_local_against_offset_stamp(self):
        self.assertTrue(
            day.overlaps(
                {"start": "2026-09-20T09:00:00", "end": "2026-09-20T10:00:00"},
                {"start": "2026-09-20T09:30:00-03:00", "end": "2026-09-20T10:30:00-03:00"},
            )
        )

    def test_dump_keeps_overlapping_same_title_as_conflict(self):
        when = datetime(2026, 9, 17)
        pt = day.parse("aula das 8h às 10h e aula das 9h às 11h", when)
        self.assertEqual([row["text"] for row in pt], ["Aula", "Aula"])
        self.assertTrue(day.conflicts(pt))
        unlabeled = day.parse("das 8h às 10h e das 9h às 11h", when)
        self.assertTrue(all(row["text"] == "Busy" for row in unlabeled))
        self.assertTrue(day.conflicts(unlabeled))
        en = day.parse("Gym from 9 to 11 and gym from 10 to 12", when)
        self.assertEqual([row["text"] for row in en], ["Gym", "Gym"])
        self.assertTrue(day.conflicts(en))

    def test_calendar_duplicate_compares_utc_instant_not_wall_clock(self):
        planned = [
            {
                "text": "Aula",
                "start": "2026-09-20T09:00:00-03:00",
                "end": "2026-09-20T15:00:00-03:00",
            }
        ]
        same_instant = [
            {"summary": "Aula", "start": "2026-09-20T12:00:00Z", "end": "2026-09-20T18:00:00Z"}
        ]
        self.assertEqual(day.conflicts(planned, same_instant), [])
        same_wall = [
            {"summary": "Aula", "start": "2026-09-20T09:00:00Z", "end": "2026-09-20T15:00:00Z"}
        ]
        clashes = day.conflicts(planned, same_wall)
        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0]["kind"], "calendar")

    def test_all_day_bounds_use_sao_paulo_and_missing_end_is_next_day(self):
        local = {
            "start": "2026-09-17T09:00:00-03:00",
            "end": "2026-09-17T10:00:00-03:00",
        }
        utc_early = {
            "start": "2026-09-17T00:30:00+00:00",
            "end": "2026-09-17T01:00:00+00:00",
        }
        spanned = {"start": "2026-09-17", "end": "2026-09-18"}
        self.assertTrue(day.overlaps(local, spanned))
        self.assertFalse(day.overlaps(utc_early, spanned))
        self.assertTrue(day.overlaps(local, {"start": "2026-09-17"}))
