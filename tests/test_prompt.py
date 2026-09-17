import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PromptTests(unittest.TestCase):
    def test_first_contact_is_bilingual_and_does_not_assume_portuguese(self):
        soul = (ROOT / "runtime" / "SOUL.md").read_text(encoding="utf-8")
        self.assertIn("Hi! Send me everything on your plate", soul)
        self.assertIn("Oi! Me manda tudo que está na tua lista", soul)
        self.assertIn("Reply in the language the person actually wrote in", soul)
        self.assertIn("from their very first message", soul)
        self.assertIn("Only when the first message carries no words at all", soul)

    def test_proposal_first_survives(self):
        soul = (ROOT / "runtime" / "SOUL.md").read_text(encoding="utf-8")
        self.assertIn("Chegue propondo, não entrevistando", soul)
        self.assertIn("Só pergunte quando falta um fato que realmente mudaria a ordem", soul)


class SeparationAndNudgeTests(unittest.TestCase):
    def test_life_work_and_nudge_rules(self):
        soul = (ROOT / "runtime" / "SOUL.md").read_text(encoding="utf-8")
        self.assertIn("life", soul)
        self.assertIn("work", soul)
        self.assertIn("Vida e Trabalho separadamente", soul)
        self.assertIn("Toda manhã", soul)

    def test_ok_books_the_block_and_kindle_is_a_destination(self):
        soul = (ROOT / "runtime" / "SOUL.md").read_text(encoding="utf-8")
        self.assertIn("tá bom", soul)
        self.assertIn("Do not ask a second time", soul)
        self.assertIn("Kindle", soul)
        self.assertIn("printer", soul)
        self.assertIn("public-domain", soul)
        self.assertIn("do **not** fetch or pirate", soul)
        self.assertIn("Latch is not required", soul)
        self.assertIn("gmail.py list", soul)
        self.assertIn("gmail.py kindle", soul)
        self.assertIn("printer.py", soul)
        self.assertIn("hpeprint", soul)
        self.assertIn("5:55", soul)
        self.assertIn("What needs you today", soul)
        self.assertIn("Do not drop today", soul)
        self.assertIn("Work and life stay separate", soul)
        self.assertIn("learn add", soul)
        self.assertIn("follow-up of an investor", soul)
        self.assertIn("payment", soul)
        self.assertIn("Readings", soul)
        self.assertIn("Hobbies", soul)
        self.assertIn("matriz.py day", soul)
        self.assertIn("Latch is not required", soul)
        self.assertIn("never one study block", soul)
        self.assertIn("Seu Report Diário", soul)
        self.assertIn("ordered by importance", soul)
        self.assertIn("charge", soul)
        self.assertIn("extra-file", soul)
        self.assertIn("researches their interests itself", soul)
        self.assertIn("profile set --charge yes", soul)


if __name__ == "__main__":
    unittest.main()
