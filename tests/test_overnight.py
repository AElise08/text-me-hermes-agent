import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("overnight", ROOT / "scripts" / "overnight.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OvernightApplyTests(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.tz = ZoneInfo("America/Sao_Paulo")
        self.now = datetime(2026, 9, 17, 5, 55, tzinfo=self.tz)
        self.event = {
            "id": "evt1",
            "summary": "editar video",
            "start": "2026-09-17T10:00:00-03:00",
            "end": "2026-09-17T10:45:00-03:00",
            "calendar_id": "primary",
            "account": "me@x",
        }

    def test_plain_email_move_requires_approval(self):
        messages = [
            {
                "subject": "vídeo mudou para as 11h",
                "snippet": "a reunião do vídeo mudou para as 11h",
                "from": "Ana <ana@x>",
            }
        ]
        with patch.object(self.mod.gcal_mod, "update", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no update"))):
            report = self.mod.run(
                apply=True,
                messages=messages,
                events=[dict(self.event)],
                now=self.now,
            )
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["approvals"][0]["text"], "vídeo mudou para as 11h")
        self.assertTrue(report["approvals"][0]["proposed_when"].startswith("2026-09-17T11:00"))
        self.assertEqual(report["approvals"][0]["event_id"], "evt1")
        self.assertEqual(report["approvals"][0]["action"], "move")

    def test_question_stays_approval(self):
        messages = [
            {
                "subject": "podemos remarcar o vídeo pra 11?",
                "snippet": "consegues hoje?",
                "from": "Ana <ana@x>",
            }
        ]
        with patch.object(self.mod.gcal_mod, "update", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no update"))):
            report = self.mod.run(
                apply=True,
                messages=messages,
                events=[dict(self.event)],
                now=self.now,
            )
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["approvals"][0]["text"], "podemos remarcar o vídeo pra 11?")

    def test_later_integer_is_not_proposed_when(self):
        cases = [
            ("vídeo mudou para as 11h, sala 2", "a reunião do vídeo mudou para as 11h, sala 2", "2026-09-17T11:00"),
            ("mudou para as 11h dia 17/09", "a reunião mudou para as 11h dia 17/09", "2026-09-17T11:00"),
            ("passou para 14h no dia 18", "a reunião passou para 14h no dia 18", "2026-09-17T14:00"),
            ("moved to 3pm in room 4", "the video moved to 3pm in room 4", "2026-09-17T15:00"),
        ]
        for subject, snippet, when in cases:
            with self.subTest(subject=subject):
                messages = [{"subject": subject, "snippet": snippet, "from": "Ana <ana@x>"}]
                with patch.object(self.mod.gcal_mod, "move", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no move"))):
                    report = self.mod.run(
                        apply=True,
                        messages=messages,
                        events=[dict(self.event)],
                        now=self.now,
                    )
                self.assertEqual(report["applied"], [])
                self.assertEqual(report["approvals"][0]["action"], "move")
                self.assertTrue(report["approvals"][0]["proposed_when"].startswith(when), report["approvals"][0])

    def test_url_query_does_not_drop_move_time(self):
        messages = [
            {
                "subject": "vídeo mudou para as 11h",
                "snippet": "https://x.com/a?b=1",
                "from": "Ana <ana@x>",
            }
        ]
        with patch.object(self.mod.gcal_mod, "move", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no move"))):
            report = self.mod.run(
                apply=True,
                messages=messages,
                events=[dict(self.event)],
                now=self.now,
            )
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["approvals"][0]["action"], "move")
        self.assertTrue(report["approvals"][0]["proposed_when"].startswith("2026-09-17T11:00"))

    def test_trailing_question_keeps_move_time(self):
        messages = [
            {
                "subject": "vídeo mudou para as 11h?",
                "snippet": "a reunião do vídeo mudou para as 11h?",
                "from": "Ana <ana@x>",
            }
        ]
        with patch.object(self.mod.gcal_mod, "move", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no move"))):
            report = self.mod.run(
                apply=True,
                messages=messages,
                events=[dict(self.event)],
                now=self.now,
            )
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["approvals"][0]["action"], "move")
        self.assertTrue(report["approvals"][0]["proposed_when"].startswith("2026-09-17T11:00"))

    def test_cli_does_not_apply_unless_flag(self):
        with patch.object(self.mod, "run", return_value={}) as mocked:
            with patch.object(sys, "argv", ["overnight.py"]):
                with patch("builtins.print"):
                    self.mod.main()
            self.assertEqual(mocked.call_args.kwargs["apply"], False)
        with patch.object(self.mod, "run", return_value={}) as mocked:
            with patch.object(sys, "argv", ["overnight.py", "--apply"]):
                with patch("builtins.print"):
                    self.mod.main()
            self.assertEqual(mocked.call_args.kwargs["apply"], True)

    def test_cancel_mail_is_approval_with_event(self):
        messages = [
            {
                "subject": "aula cancelada",
                "snippet": "a aula de hoje foi cancelada",
                "from": "escola@x",
            }
        ]
        event = dict(self.event)
        event["id"] = "aula1"
        event["summary"] = "Aula"
        with patch.object(self.mod.gcal_mod, "cancel", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no cancel"))):
            report = self.mod.run(
                apply=True,
                messages=messages,
                events=[event],
                now=self.now,
            )
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["approvals"][0]["action"], "cancel")
        self.assertEqual(report["approvals"][0]["event_id"], "aula1")

    def test_unmatched_cancel_does_not_target_the_only_event(self):
        report = self.mod.run(
            apply=True,
            messages=[{"subject": "aula cancelada", "snippet": "a aula de hoje foi cancelada", "from": "escola@x"}],
            events=[dict(self.event, summary="Consulta médica")],
            now=self.now,
        )
        self.assertEqual(report["approvals"][0]["action"], "cancel")
        self.assertEqual(report["approvals"][0]["event_id"], "")

    def test_inbox_follows_their_work_and_life_words(self):
        state = {
            "goals": {"work": "hackathon video", "life": "church choir"},
            "tasks": [],
            "profile": {},
        }
        work_mail = {
            "subject": "Re: hackathon deadline",
            "snippet": "waiting on the video",
            "from": "ana@x",
        }
        life_mail = {
            "subject": "Re: choir practice",
            "snippet": "church tonight",
            "from": "jo@x",
        }
        noise = {
            "subject": "Follow-up from the investor",
            "snippet": "time to talk plow demo",
            "from": "a@x",
        }
        report = self.mod.run(
            apply=False,
            messages=[work_mail, life_mail, noise],
            events=[],
            now=self.now,
            state=state,
        )
        texts = [x["text"] for x in report["needs"]]
        self.assertIn("Re: hackathon deadline", texts)
        self.assertIn("Re: choir practice", texts)
        self.assertTrue(all("investor" not in x.lower() for x in texts))
        spheres = {x["text"]: x["sphere"] for x in report["needs"]}
        self.assertEqual(spheres["Re: hackathon deadline"], "work")
        self.assertEqual(spheres["Re: choir practice"], "life")

    def test_learned_investor_followup_is_work(self):
        state = {
            "goals": {"work": "", "life": ""},
            "tasks": [],
            "profile": {},
            "known": {"work": [{"text": "follow-up of an investor"}], "life": []},
        }
        messages = [
            {
                "subject": "Follow-up from the investor",
                "snippet": "waiting on a reply",
                "from": "a@x",
            }
        ]
        report = self.mod.run(
            apply=False, messages=messages, events=[], now=self.now, state=state
        )
        self.assertEqual(report["needs"][0]["sphere"], "work")
        self.assertIn("investor", report["needs"][0]["text"].lower())

    def test_payment_mail_is_a_reminder_even_from_noreply(self):
        messages = [
            {
                "subject": "Lembrete de pagamento — fatura de luz",
                "snippet": "pague até 20/09",
                "from": "noreply@enel.com",
            }
        ]
        report = self.mod.run(
            apply=False, messages=messages, events=[], now=self.now, state={}
        )
        self.assertEqual(report["needs"][0]["sphere"], "life")
        self.assertTrue(report["needs"][0]["important"])
        self.assertIn("fatura", report["needs"][0]["text"].lower())

    def test_hobby_newsletter_is_not_a_fire(self):
        state = {
            "goals": {"work": "", "life": ""},
            "tasks": [],
            "profile": {"interests": ["films"]},
            "known": {"work": [], "life": [], "reading": [], "hobby": [{"text": "piano"}]},
        }
        messages = [
            {
                "subject": "New films this week",
                "snippet": "cinema digest",
                "from": "arts@x",
            },
            {
                "subject": "Piano recitals in town",
                "snippet": "this weekend",
                "from": "events@x",
            },
        ]
        report = self.mod.run(
            apply=False, messages=messages, events=[], now=self.now, state=state
        )
        self.assertEqual(report["needs"], [])
        self.assertTrue(any("films" in x.lower() for x in report["hobbies"]))
        self.assertTrue(any("piano" in x.lower() for x in report["hobbies"]))

    def test_reading_list_stays_on_the_page(self):
        state = {
            "known": {
                "work": [],
                "life": [],
                "reading": [{"text": "lista de livros"}],
                "hobby": [],
            }
        }
        report = self.mod.run(
            apply=False, messages=[], events=[], now=self.now, state=state
        )
        self.assertIn("lista de livros", report["readings"])

    def test_meeting_and_acceleration_mail_is_a_work_fire(self):
        messages = [
            {
                "subject": "Reunião do processo de aceleração",
                "snippet": "a banca confirma amanhã às 11h",
                "from": "programa@x",
            }
        ]
        report = self.mod.run(
            apply=False, messages=messages, events=[], now=self.now, state={}
        )
        self.assertEqual(report["needs"][0]["sphere"], "work")
        self.assertIn("aceleração", report["needs"][0]["text"].lower())
