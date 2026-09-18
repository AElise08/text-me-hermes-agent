import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("accounts", ROOT / "scripts" / "accounts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AccountTests(unittest.TestCase):
    def test_default_route_and_audit_are_per_account(self):
        with tempfile.TemporaryDirectory() as home:
            state = {
                "profile": {
                    "google": {
                        "accounts": [
                            {"account": "me@example.com", "label": "Personal", "calendar_id": "personal"},
                            {"account": "school@example.edu", "label": "School", "calendar_id": "primary"},
                        ],
                        "default_account": "me@example.com",
                        "default_calendar_id": "personal",
                    }
                }
            }
            target = Path(home) / ".matriz"
            target.mkdir()
            (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
            with patch.dict(os.environ, {"HERMES_HOME": home}, clear=False):
                accounts = load()
                self.assertEqual(accounts.route(), ("me@example.com", "personal"))
                accounts.record("calendar", "create", "school@example.edu", "primary", "evt1")
                row = accounts.audit("school@example.edu")[0]
        self.assertEqual(row["account_label"], "School")
        self.assertEqual(row["resource_id"], "evt1")

    def test_routes_a_friendly_account_label_to_its_calendar(self):
        with tempfile.TemporaryDirectory() as home:
            state = Path(home) / ".matriz" / "state.json"
            state.parent.mkdir()
            state.write_text(
                json.dumps(
                    {
                        "profile": {
                            "google": {
                                "accounts": [
                                    {
                                        "account": "school@example.edu",
                                        "label": "Faculty",
                                        "calendar_id": "classes",
                                    }
                                ]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"HERMES_HOME": home}, clear=False):
                accounts = load()
                self.assertEqual(accounts.route("Faculty"), ("school@example.edu", "classes"))

    def test_named_default_account_uses_default_calendar_not_stale_primary(self):
        with tempfile.TemporaryDirectory() as home:
            state = Path(home) / ".matriz" / "state.json"
            state.parent.mkdir()
            state.write_text(
                json.dumps(
                    {
                        "profile": {
                            "google": {
                                "accounts": [
                                    {
                                        "account": "me@example.com",
                                        "label": "Pessoal",
                                        "calendar_id": "primary",
                                    },
                                    {
                                        "account": "school@example.edu",
                                        "label": "Faculty",
                                        "calendar_id": "classes",
                                    },
                                ],
                                "default_account": "me@example.com",
                                "default_calendar_id": "personal",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"HERMES_HOME": home}, clear=False):
                accounts = load()
                self.assertEqual(accounts.route(), ("me@example.com", "personal"))
                self.assertEqual(accounts.route("Pessoal"), ("me@example.com", "personal"))
                self.assertEqual(accounts.route("me@example.com"), ("me@example.com", "personal"))
                self.assertEqual(accounts.route("Faculty"), ("school@example.edu", "classes"))
                self.assertEqual(accounts.route("school@example.edu"), ("school@example.edu", "classes"))
                self.assertEqual(accounts.route("other@example.com"), ("other@example.com", "primary"))
                self.assertEqual(
                    accounts.route("Pessoal", "explicit-cal"),
                    ("me@example.com", "explicit-cal"),
                )
                with self.assertRaises(SystemExit):
                    accounts.route("Unknown")

    def test_google_default_cli_keeps_row_calendar_unless_explicit(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HERMES_HOME": home}
            cli = [sys.executable, str(ROOT / "scripts" / "matriz.py")]
            subprocess.check_output(
                [*cli, "google", "add", "--account", "school@example.edu", "--label", "Faculty", "--calendar-id", "classes"],
                env=env,
            )
            omitted = json.loads(subprocess.check_output(
                [*cli, "google", "default", "--account", "Faculty"],
                env=env, text=True,
            ))["google"]
            self.assertEqual(omitted["default_calendar_id"], "classes")
            self.assertEqual(omitted["accounts"][0]["calendar_id"], "classes")
            explicit = json.loads(subprocess.check_output(
                [*cli, "google", "default", "--account", "Faculty", "--calendar-id", "personal"],
                env=env, text=True,
            ))["google"]
            self.assertEqual(explicit["default_calendar_id"], "personal")
            self.assertEqual(explicit["accounts"][0]["calendar_id"], "personal")
