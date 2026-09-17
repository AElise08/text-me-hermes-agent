import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("research", ROOT / "scripts" / "research.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def rss(rows: list[tuple[str, str, str, datetime | None]]) -> bytes:
    items = []
    for title, link, source, when in rows:
        pub = f"<pubDate>{format_datetime(when)}</pubDate>" if when else ""
        items.append(
            f"<item><title>{title}</title><link>{link}</link>"
            f"<source>{source}</source>{pub}</item>"
        )
    return f'<?xml version="1.0"?><rss><channel>{"".join(items)}</channel></rss>'.encode()


class ResearchTests(unittest.TestCase):
    def test_locale_follows_the_chat_tag_not_portuguese(self):
        research = load()
        self.assertEqual(research.locale("de"), ("de", "DE", "DE:de"))
        self.assertEqual(research.locale("ja"), ("ja", "JP", "JP:ja"))
        self.assertEqual(research.locale("en"), ("en", "US", "US:en"))
        self.assertEqual(research.locale("pt-PT"), ("pt-PT", "PT", "PT:pt"))
        self.assertEqual(research.locale(""), ("en", "US", "US:en"))
        self.assertNotEqual(research.locale("")[0], "pt-BR")
        self.assertEqual(research.locale("pt")[1], "BR")

    def test_clips_keep_interests_drop_avoid_and_old(self):
        research = load()
        fresh = NOW - timedelta(hours=2)
        stale = NOW - timedelta(hours=30)
        payload = rss(
            [
                ("IA na escola muda a sala", "https://ex.test/a", "Agencia", fresh),
                ("Economia local em queda", "https://ex.test/b", "Diario", fresh),
                ("Boa noticia velha de ciencia", "https://ex.test/c", "Lab", stale),
            ]
        )
        with patch.object(research, "fetch", return_value=payload):
            out = research.clips(["IA"], avoid=["economia"], language="pt", limit=4, now=NOW)
        self.assertTrue(any("escola" in x.lower() for x in out))
        self.assertTrue(all("economia" not in x.lower() for x in out))
        self.assertTrue(all("velha" not in x.lower() for x in out))
        self.assertTrue(all("https://" not in x for x in out))

    def test_undated_and_stale_are_not_shown(self):
        research = load()
        payload = rss(
            [
                ("Fresh model ships", "https://ex.test/n", "Wire", NOW - timedelta(hours=1)),
                ("Last month's model", "https://ex.test/o", "Wire", NOW - timedelta(days=4)),
                ("No date at all", "https://ex.test/p", "Wire", None),
            ]
        )
        captured = []

        def fake_fetch(url: str) -> bytes:
            captured.append(url)
            return payload

        with patch.object(research, "fetch", side_effect=fake_fetch):
            out = research.clips(["AI"], language="de", now=NOW)
        self.assertEqual(out, ["Fresh model ships — Wire"])
        self.assertTrue(captured)
        self.assertIn("hl=de", captured[0])
        self.assertIn("ceid=DE:de", captured[0])

    def test_empty_interests_does_not_fetch(self):
        research = load()
        with patch.object(research, "fetch", side_effect=AssertionError("must not fetch")):
            self.assertEqual(research.clips([]), [])

    def test_network_failure_is_empty(self):
        research = load()
        with patch.object(research, "fetch", side_effect=TimeoutError):
            self.assertEqual(research.clips(["IA"], language="de"), [])

    def test_charge_uses_speaker_language_and_keeps_link(self):
        research = load()
        payload = rss(
            [("Karikatur am Morgen", "https://ex.test/toon", "Zeitung", NOW - timedelta(hours=1))]
        )
        captured = []

        def fake_fetch(url: str) -> bytes:
            captured.append(url)
            return payload

        with patch.object(research, "fetch", side_effect=fake_fetch):
            with patch.object(research, "image_for", return_value=b""):
                out = research.charge("de", now=NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "Karikatur am Morgen")
        self.assertIn("https://ex.test/toon", out[0]["link"])
        self.assertIn("hl=de", captured[0])
        self.assertIn("Karikatur", captured[0])

    def test_og_image_from_article_html(self):
        research = load()
        html = '<meta property="og:image" content="https://ex.test/c.jpg">'
        self.assertEqual(research.og_image(html), "https://ex.test/c.jpg")


if __name__ == "__main__":
    unittest.main()
