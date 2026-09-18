import unittest

from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("people", ROOT / "scripts" / "people.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_edition():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("edition", ROOT / "scripts" / "edition.py")
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

    def test_find_skips_name_substrings_and_email_domains(self):
        people_mod = load()
        book = []
        people_mod.upsert(book, "Mariana", "mariana@gmail.com")
        people_mod.upsert(book, "Joana Silva", "joana@x.com")
        people_mod.upsert(book, "Ana", "ana@x.com")
        hits = people_mod.find(book, "Ana")
        self.assertEqual([h["email"] for h in hits], ["ana@x.com"])
        self.assertEqual(people_mod.find(book, "a"), [])
        self.assertEqual(people_mod.find(book, "com"), [])
        self.assertEqual(people_mod.find(book, "gmail"), [])

    def test_find_first_token_and_email_local_part(self):
        people_mod = load()
        book = []
        people_mod.upsert(book, "Ana Silva", "ana@gmail.com")
        self.assertEqual(people_mod.find(book, "ana")[0]["email"], "ana@gmail.com")
        self.assertEqual(people_mod.find(book, "silva"), [])
        self.assertEqual(people_mod.find(book, "gmail"), [])
        self.assertEqual(people_mod.find(book, "com"), [])
        people_mod.upsert(book, "Pat", "bruno.costa@x.com")
        self.assertEqual(people_mod.find(book, "bruno.costa")[0]["email"], "bruno.costa@x.com")
        self.assertEqual(people_mod.find(book, "bruno")[0]["email"], "bruno.costa@x.com")
        people_mod.upsert(book, "Anastasia", "anastasia@x.com")
        self.assertEqual([h["email"] for h in people_mod.find(book, "Ana")], ["ana@gmail.com"])
        self.assertEqual(people_mod.find(book, "@gmail.com"), [])
        self.assertEqual(people_mod.find(book, "bru"), [])

    def test_emails_for_first_name_not_city_or_stop_words(self):
        people_mod = load()
        book = [
            {"name": "Ana Silva", "email": "ana@x.com", "aliases": []},
            {"name": "Rio", "email": "rio@x.com", "aliases": []},
        ]
        self.assertEqual(people_mod.emails_for("call with Ana", book), ["ana@x.com"])
        self.assertEqual(
            people_mod.emails_for("trip to rio de janeiro with Ana", book),
            ["ana@x.com"],
        )
        self.assertEqual(people_mod.emails_for("gym com Mariana", book), [])

    def test_emails_for_two_anas_and_same_person_once(self):
        people_mod = load()
        distinct = [
            {"name": "Ana Silva", "email": "silva@x.com", "aliases": []},
            {"name": "Ana", "email": "ana@x.com", "aliases": []},
        ]
        self.assertEqual(
            sorted(people_mod.emails_for("reunião com Ana Silva", distinct)),
            ["ana@x.com", "silva@x.com"],
        )
        same = [
            {"name": "Ana Silva", "email": "ana@x.com", "aliases": []},
            {"name": "Ana", "email": "ana@x.com", "aliases": []},
        ]
        self.assertEqual(people_mod.emails_for("reunião com Ana Silva", same), ["ana@x.com"])


class AgendaRowsTests(unittest.TestCase):
    def test_unsorted_overlap_tags_both_and_skips_nonoverlap(self):
        edition = load_edition()
        rows = edition.agenda_rows(
            ["14:00–15:00  Gym", "10:00–12:00  Aula", "11:00–12:00  Mentoria"],
            False,
        )
        gym = next(r for r in rows if "Gym" in r)
        aula = next(r for r in rows if "Aula" in r)
        mentoria = next(r for r in rows if "Mentoria" in r)
        self.assertNotIn("conflict", gym)
        self.assertIn("conflict", aula)
        self.assertIn("conflict", mentoria)
        self.assertTrue(aula.startswith("- 10:00–12:00"))
        self.assertTrue(mentoria.startswith("- 11:00–12:00"))

    def test_conflict_keeps_commute_and_unparsed(self):
        edition = load_edition()
        rows = edition.agenda_rows(
            ["note without a clock", "10:00-12:00  ônibus casa", "11:00–12:00  Mentoria"],
            True,
        )
        self.assertEqual(rows[0], "- note without a clock")
        self.assertIn("deslocamento", rows[1])
        self.assertIn("conflito", rows[1])
        self.assertIn("conflito", rows[2])
        self.assertNotIn("conflict", rows[1])


if __name__ == "__main__":
    unittest.main()
