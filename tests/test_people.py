import unittest

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("people", ROOT / "scripts" / "people.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PeopleTests(unittest.TestCase):
    def test_upsert_and_find_by_name(self):
        people_mod = load()
        book = []
        person = people_mod.upsert(book, "Ana", "Ana@X.com")
        self.assertEqual(person["email"], "ana@x.com")
        self.assertEqual(len(book), 1)
        people_mod.upsert(book, "Ana", "ana@x.com", alias="Aninha")
        self.assertEqual(len(book), 1)
        self.assertIn("Aninha", book[0]["aliases"])
        hits = people_mod.find(book, "ana")
        self.assertEqual(hits[0]["email"], "ana@x.com")

    def test_emails_for_uses_saved_name(self):
        people_mod = load()
        book = [{"name": "Ana", "email": "ana@x.com", "aliases": []}]
        self.assertEqual(people_mod.emails_for("call with Ana at 15h", book), ["ana@x.com"])
        self.assertEqual(people_mod.emails_for("gym", book), [])
        self.assertEqual(
            people_mod.emails_for("manda para Ana <Ana@X.com>", book),
            ["ana@x.com"],
        )


if __name__ == "__main__":
    unittest.main()
