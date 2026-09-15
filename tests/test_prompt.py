import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PromptTests(unittest.TestCase):
 def test_first_contact_is_bilingual_and_does_not_assume_portuguese(self):
  soul=(ROOT/'runtime'/'SOUL.md').read_text(encoding='utf-8')
  self.assertIn("Hi! Send me everything on your plate",soul)
  self.assertIn("Oi! Me manda tudo que está na tua lista",soul)
  # The reply follows the words the person actually sent, from the first
  # message; the bilingual opening is reserved for a first message with no
  # words at all.
  self.assertIn("Reply in the language the person actually wrote in",soul)
  self.assertIn("from their very first message",soul)
  self.assertIn("Only when the first message carries no words at all",soul)
 def test_proposal_first_survives(self):
  soul=(ROOT/'runtime'/'SOUL.md').read_text(encoding='utf-8')
  self.assertIn("Chegue propondo, não entrevistando",soul)
  self.assertIn("Só pergunte quando falta um fato que realmente mudaria a ordem",soul)
if __name__=='__main__': unittest.main()

class SeparationAndNudgeTests(unittest.TestCase):
 def test_life_work_and_nudge_rules(self):
  soul=(ROOT/'runtime'/'SOUL.md').read_text(encoding='utf-8')
  self.assertIn('life',soul); self.assertIn('work',soul)
  self.assertIn('Vida e Trabalho separadamente',soul)
  self.assertIn('Toda manhã',soul)
