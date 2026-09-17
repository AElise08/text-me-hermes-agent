import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("research", ROOT / "scripts" / "research.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RSS = b"""<?xml version="1.0"?>
<rss><channel>
<item><title>IA na escola muda a sala</title><link>https://ex.test/a</link><source>Agencia</source></item>
<item><title>Economia local em queda</title><link>https://ex.test/b</link><source>Diario</source></item>
<item><title>Boa noticia de ciencia</title><link>https://ex.test/c</link><source>Lab</source></item>
</channel></rss>
"""

CARTOON = b"""<?xml version="1.0"?>
<rss><channel>
<item><title>Tuesday cartoon</title><link>https://ex.test/toon</link><source>The Guardian</source></item>
</channel></rss>
"""


class ResearchTests(unittest.TestCase):
    def test_clips_keep_interests_drop_avoid(self):
        research = load()
        with patch.object(research, "fetch", return_value=RSS):
            out = research.clips(["IA"], avoid=["economia"], language="pt", limit=4)
        self.assertTrue(any("escola" in x.lower() for x in out))
        self.assertTrue(all("economia" not in x.lower() for x in out))
        self.assertTrue(all("https://" not in x for x in out))

    def test_empty_interests_does_not_fetch(self):
        research = load()
        with patch.object(research, "fetch", side_effect=AssertionError("must not fetch")):
            self.assertEqual(research.clips([]), [])

    def test_network_failure_is_empty(self):
        research = load()
        with patch.object(research, "fetch", side_effect=TimeoutError):
            self.assertEqual(research.clips(["IA"]), [])

    def test_charge_includes_source_link(self):
        research = load()
        with patch.object(research, "fetch", return_value=CARTOON):
            out = research.charge("en")
        self.assertEqual(len(out), 1)
        self.assertIn("Tuesday cartoon", out[0])
        self.assertIn("https://ex.test/toon", out[0])


if __name__ == "__main__":
    unittest.main()
