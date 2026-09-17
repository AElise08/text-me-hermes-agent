import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("schedule", ROOT / "scripts" / "schedule.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScheduleTests(unittest.TestCase):
    def test_kindle_six_sends_at_five_fifty_five(self):
        schedule = load()
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 9, 17, 4, 0, tzinfo=tz)
        profile = {"delivery": "kindle", "edition_hour": 6}
        self.assertEqual(schedule.dispatch_at(now, profile).strftime("%H:%M"), "05:55")
        self.assertEqual(schedule.hand_at(now, profile).strftime("%H:%M"), "06:00")
        self.assertFalse(schedule.wants_morning_chat(profile, sent=True))
        self.assertTrue(schedule.wants_morning_chat(profile, sent=False))

    def test_zone_comes_from_their_profile_before_the_image_tz(self):
        schedule = load()
        with patch.object(schedule, "load_profile", return_value={"timezone": "Europe/Lisbon"}):
            self.assertEqual(str(schedule.zone()), "Europe/Lisbon")
        with patch.dict("os.environ", {"TZ": "America/Belem"}):
            with patch.object(schedule, "load_profile", return_value={}):
                self.assertEqual(str(schedule.zone()), "America/Belem")
        self.assertEqual(str(schedule.zone({"timezone": "garbage/zone"})), "UTC")

    def test_already_sent_sleeps_until_tomorrow(self):
        schedule = load()
        tz = ZoneInfo("UTC")
        now = datetime(2026, 9, 17, 8, 0, tzinfo=tz)
        profile = {"delivery": "message", "edition_hour": 7}
        wake = schedule.next_wake(now, profile, already="2026-09-17")
        self.assertEqual(wake.date().isoformat(), "2026-09-18")


class OvernightTests(unittest.TestCase):
    def test_keeps_reply_drops_newsletter(self):
        spec = importlib.util.spec_from_file_location("gmail_ov", ROOT / "scripts" / "gmail.py")
        gmail = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gmail)
        messages = [
            {"subject": "Re: vídeo do hackathon", "snippet": "consegues hoje?", "from": "Ana <ana@x>"},
            {"subject": "Weekly newsletter", "snippet": "unsubscribe here", "from": "news@x"},
            {"subject": "Standup moved to 11", "snippet": "meeting updated", "from": "cal@x"},
        ]
        with patch.object(gmail, "list_messages", return_value=messages):
            out = gmail.overnight()
        self.assertIn("Re: vídeo do hackathon", out)
        self.assertIn("Standup moved to 11", out)
        self.assertTrue(all("newsletter" not in x.lower() for x in out))
