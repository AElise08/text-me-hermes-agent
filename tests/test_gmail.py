import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class GmailTests(unittest.TestCase):
    def test_build_raw_includes_to_and_epub(self):
        gmail = load("gmail_mod", "scripts/gmail.py")
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "day.epub"
            epub.write_bytes(b"PK\x03\x04fake")
            raw = gmail.build_raw(
                "me@gmail.com",
                "name@kindle.com",
                "Edition for Sep 17",
                "body",
                files=[epub],
            )
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", "replace")
        self.assertIn("To: name@kindle.com", decoded)
        self.assertIn("From: me@gmail.com", decoded)
        self.assertIn("filename=\"day.epub\"", decoded)
        self.assertIn("application/epub+zip", decoded)

    def test_reply_stays_in_thread(self):
        gmail = load("gmail_reply", "scripts/gmail.py")
        calls = []

        def fake_api(method, path, body=None, token=None):
            calls.append((method, path, body))
            if path == "/profile":
                return {"emailAddress": "me@gmail.com"}
            if method == "GET":
                return {
                    "id": "m1",
                    "threadId": "t1",
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "From", "value": "Ana <ana@x.com>"},
                            {"name": "To", "value": "me@gmail.com"},
                            {"name": "Subject", "value": "vídeo"},
                            {"name": "Message-ID", "value": "<abc@x>"},
                        ],
                        "body": {"data": base64.urlsafe_b64encode(b"oi").decode().rstrip("=")},
                    },
                }
            return {"id": "sent1"}

        with patch.object(gmail, "mint_google_token", return_value="tok"):
            with patch.object(gmail, "gmail_api", fake_api):
                gmail.reply("m1", "sim, às 15h")
        send = next(item for item in calls if item[1] == "/messages/send")
        self.assertEqual(send[2]["threadId"], "t1")
        decoded = base64.urlsafe_b64decode(send[2]["raw"] + "=" * (-len(send[2]["raw"]) % 4)).decode(
            "utf-8", "replace"
        )
        self.assertIn("In-Reply-To: <abc@x>", decoded)
        self.assertIn("To: ana@x.com", decoded)
        self.assertIn("Re:", decoded)
        self.assertNotIn("To: me@gmail.com", decoded)

    def test_draft_reply_does_not_send(self):
        gmail = load("gmail_draft", "scripts/gmail.py")
        calls = []

        def fake_api(method, path, body=None, token=None):
            calls.append((method, path, body))
            if path == "/profile":
                return {"emailAddress": "me@gmail.com"}
            if method == "GET":
                return {
                    "id": "m1",
                    "threadId": "t1",
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "From", "value": "Ana <ana@x.com>"},
                            {"name": "To", "value": "me@gmail.com"},
                            {"name": "Subject", "value": "vídeo"},
                            {"name": "Message-ID", "value": "<abc@x>"},
                        ],
                        "body": {"data": base64.urlsafe_b64encode(b"oi").decode().rstrip("=")},
                    },
                }
            return {"id": "r-99"}

        with patch.object(gmail, "mint_google_token", return_value="tok"):
            with patch.object(gmail, "gmail_api", fake_api):
                out = gmail.draft_reply("m1", "sim, às 15h")
        self.assertEqual(out["id"], "r-99")
        self.assertTrue(any(item[1] == "/drafts" for item in calls))
        self.assertFalse(any("/messages/send" in (item[1] or "") for item in calls))
        self.assertFalse(any(item[1] == "/drafts/send" for item in calls))

    def test_send_draft_posts_id(self):
        gmail = load("gmail_send_draft", "scripts/gmail.py")
        captured = {}

        def fake_api(method, path, body=None, token=None):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {"id": "msg-sent"}

        with patch.object(gmail, "gmail_api", fake_api), patch.object(gmail, "mint_google_token", return_value="tok"):
            gmail.send_draft("r-99")
        self.assertEqual(captured["path"], "/drafts/send")
        self.assertEqual(captured["body"]["id"], "r-99")

    def test_list_refuses_an_account_the_plow_gmail_api_cannot_select(self):
        gmail = load("gmail_account", "scripts/gmail.py")
        with self.assertRaisesRegex(SystemExit, "default mailbox"):
            gmail.list_messages(account="school@example.edu")

    def test_inbox_clips_skips_avoid_and_keeps_interests(self):
        gmail = load("gmail_mod2", "scripts/gmail.py")
        messages = [
            {"subject": "Crime blotter", "snippet": "local violence", "from": "news@x"},
            {"subject": "New films this week", "snippet": "cinema", "from": "arts@x"},
            {"subject": "Nvoip report", "snippet": "atendimentos", "from": "noreply@nvoip.com.br"},
        ]
        with patch.object(gmail, "list_messages", return_value=messages):
            clips = gmail.inbox_clips(interests=["film"], avoid=["violence", "crime"])
        self.assertEqual(len(clips), 1)
        self.assertIn("films", clips[0].lower())

    def test_connectors_marks_gmail_send_when_rest_is_up(self):
        connectors = load("connectors_mod", "scripts/connectors.py")
        with patch.object(connectors, "rest_status", return_value={"ok": True, "path": "rest"}):
            with patch.object(connectors, "latch_status", return_value={"ok": False, "path": "latch"}):
                probe = connectors.probe()
        self.assertTrue(probe["gmail_send"])
        self.assertTrue(probe["gmail_read"])
        self.assertTrue(probe["calendar"])
        self.assertIn("No Latch, no Mac", probe["advice"])

    def test_connectors_ignore_latch_for_gmail(self):
        connectors = load("connectors_mod2", "scripts/connectors.py")
        with patch.object(
            connectors, "rest_status",
            return_value={"ok": False, "path": "rest", "reason": "not connected"},
        ):
            with patch.object(
                connectors, "latch_status",
                return_value={"ok": True, "path": "latch", "reason": "relay answered"},
            ):
                probe = connectors.probe()
        self.assertFalse(probe["gmail_send"])
        self.assertFalse(probe["calendar"])
        self.assertNotIn("Latch is up", probe["advice"])
