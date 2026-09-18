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
        self.assertEqual(out["data"]["id"], "evt1")

    def test_line_is_clock_then_title(self):
        gcal = load_gcal()
        text = gcal.line({
            "summary": "Aula",
            "start": "2026-09-17T07:30:00-03:00",
            "end": "2026-09-17T09:20:00-03:00",
        })
        self.assertEqual(text, "07:30–09:20  Aula")
