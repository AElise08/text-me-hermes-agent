import json
import os
import unittest
from unittest.mock import patch
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load_gcal():
    spec = importlib.util.spec_from_file_location("gcal", ROOT / "scripts" / "gcal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class GcalTests(unittest.TestCase):
    def test_token_from_env_only(self):
        gcal = load_gcal()
        with patch.dict(os.environ, {"PLOW_CONNECTOR_TOKEN": "acct-test"}, clear=False):
            self.assertEqual(gcal.token(), "acct-test")

    def test_token_falls_back_to_agent(self):
        gcal = load_gcal()
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "PLOW_CONNECTOR_TOKEN",
                "PLOW_CONNECTOR_TOKEN_FILE",
                "PLOW_AGENT_TOKEN",
                "PLOW_CHAT_TOKEN",
            }
        }
        env["PLOW_AGENT_TOKEN"] = "agt-cloud"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(gcal.token(), "agt-cloud")

    def test_token_ignores_home_file(self):
        gcal = load_gcal()
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "PLOW_CONNECTOR_TOKEN",
                "PLOW_CONNECTOR_TOKEN_FILE",
                "PLOW_AGENT_TOKEN",
                "PLOW_CHAT_TOKEN",
            }
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(gcal.token(), "")

    def test_create_posts_summary_start_end(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["action"] = action
            captured["body"] = body
            return {"status": "ok", "data": {"id": "evt1"}}

        with patch.object(gcal, "call", fake_call):
            out = gcal.create("edit video", "2026-09-17T10:00:00-03:00", "2026-09-17T10:45:00-03:00")
        self.assertEqual(captured["action"], "calendar.events.create")
        self.assertEqual(captured["body"]["summary"], "edit video")
        self.assertNotIn("conferenceData", captured["body"])
        self.assertEqual(out["data"]["id"], "evt1")

    def test_create_meet_asks_google_for_hangouts(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["body"] = body
            return {
                "status": "ok",
                "data": {
                    "id": "evt2",
                    "hangoutLink": "https://meet.google.com/aaa-bbbb-ccc",
                },
            }

        with patch.object(gcal, "call", fake_call):
            out = gcal.create(
                "standup",
                "2026-09-18T15:00:00-03:00",
                "2026-09-18T15:30:00-03:00",
                meet=True,
            )
        self.assertEqual(captured["body"]["conferenceDataVersion"], 1)
        key = captured["body"]["conferenceData"]["createRequest"]["conferenceSolutionKey"]
        self.assertEqual(key["type"], "hangoutsMeet")
        self.assertEqual(out["hangout"], "https://meet.google.com/aaa-bbbb-ccc")

    def test_meet_link_from_entry_points(self):
        gcal = load_gcal()
        url = gcal.meet_link({
            "conferenceData": {
                "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/xyz-abcd-efg"}],
            }
        })
        self.assertEqual(url, "https://meet.google.com/xyz-abcd-efg")
        self.assertEqual(gcal.meet_link({"htmlLink": "https://calendar.google.com/event?eid=1"}), "")

    def test_wants_meet_only_when_they_asked_for_a_room(self):
        gcal = load_gcal()
        self.assertTrue(gcal.wants_meet("reunião com meet 15h"))
        self.assertTrue(gcal.wants_meet("link da call com a Ana"))
        self.assertFalse(gcal.wants_meet("ligar para a mãe"))
        self.assertFalse(gcal.wants_meet("team meeting"))
        self.assertFalse(gcal.wants_meet("gym"))

    def test_line_is_clock_then_title(self):
        gcal = load_gcal()
        text = gcal.line({
            "summary": "Aula",
            "start": "2026-09-17T07:30:00-03:00",
            "end": "2026-09-17T09:20:00-03:00",
        })
        self.assertEqual(text, "07:30–09:20  Aula")

    def test_create_invite_sends_updates(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["body"] = body
            return {"status": "ok", "data": {"id": "evt3"}}

        with patch.object(gcal, "call", fake_call):
            gcal.create(
                "call",
                "2026-09-18T15:00:00-03:00",
                "2026-09-18T15:30:00-03:00",
                meet=True,
                attendees=["ana@x.com"],
            )
        self.assertEqual(captured["body"]["attendees"], [{"email": "ana@x.com"}])
        self.assertEqual(captured["body"]["sendUpdates"], "all")

    def test_create_recurrence_weekly(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["body"] = body
            return {"status": "ok", "data": {"id": "evt4"}}

        with patch.object(gcal, "call", fake_call):
            gcal.create(
                "aula",
                "2026-09-22T07:30:00-03:00",
                "2026-09-22T09:20:00-03:00",
                recurrence=["RRULE:FREQ=WEEKLY;BYDAY=TU"],
            )
        self.assertEqual(captured["body"]["recurrence"], ["RRULE:FREQ=WEEKLY;BYDAY=TU"])

    def test_move_keeps_duration_when_end_omitted(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["action"] = action
            captured["body"] = body
            return {"status": "ok"}

        def fake_events(when=None):
            return [
                {
                    "id": "evt1",
                    "start": "2026-09-17T10:00:00-03:00",
                    "end": "2026-09-17T10:45:00-03:00",
                }
            ]

        with patch.object(gcal, "call", fake_call), patch.object(gcal, "events_on", fake_events):
            gcal.move("evt1", "2026-09-17T11:00:00-03:00")
        self.assertEqual(captured["action"], "calendar.events.update")
        self.assertEqual(captured["body"]["start"], "2026-09-17T11:00:00-03:00")
        self.assertEqual(captured["body"]["end"], "2026-09-17T11:45:00-03:00")
        self.assertEqual(captured["body"]["sendUpdates"], "all")

    def test_cancel_deletes(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["action"] = action
            captured["body"] = body
            return {"status": "ok"}

        with patch.object(gcal, "call", fake_call):
            gcal.cancel("evt1")
        self.assertEqual(captured["action"], "calendar.events.delete")
        self.assertEqual(captured["body"]["event_id"], "evt1")
        self.assertEqual(captured["body"]["sendUpdates"], "all")

    def test_invite_existing_event(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["action"] = action
            captured["body"] = body
            return {"status": "ok", "data": {"hangoutLink": "https://meet.google.com/aaa-bbbb-ccc"}}

        with patch.object(gcal, "call", fake_call), patch.object(gcal, "events_on", lambda when=None: []):
            out = gcal.invite("evt1", ["ana@x.com"], meet=True)
        self.assertEqual(captured["action"], "calendar.events.update")
        self.assertEqual(captured["body"]["attendees"], [{"email": "ana@x.com"}])
        self.assertEqual(out["hangout"], "https://meet.google.com/aaa-bbbb-ccc")

    def test_invite_keeps_existing_attendees(self):
        gcal = load_gcal()
        captured = {}

        def fake_call(action, body=None, method=None):
            captured["body"] = body
            return {"status": "ok", "data": {}}

        def fake_events(when=None):
            return [{"id": "evt1", "attendees": ["joao@x.com"]}]

        with patch.object(gcal, "call", fake_call), patch.object(gcal, "events_on", fake_events):
            gcal.invite("evt1", ["ana@x.com"])
        mails = [p["email"] for p in captured["body"]["attendees"]]
        self.assertEqual(mails, ["ana@x.com", "joao@x.com"])

    def test_emails_in_dedupes(self):
        gcal = load_gcal()
        self.assertEqual(gcal.emails_in("Ana <Ana@X.com> e ana@x.com"), ["ana@x.com"])
