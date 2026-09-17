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
            with patch.object(research, "article_lede", return_value="A escola mudou a sala com um modelo novo de IA."):
                out = research.clips(["IA"], avoid=["economia"], language="pt", limit=4, now=NOW)
        titles = [x["title"] for x in out]
        self.assertTrue(any("escola" in t.lower() for t in titles))
        self.assertTrue(all("economia" not in t.lower() for t in titles))
        self.assertTrue(all("velha" not in t.lower() for t in titles))
        self.assertIn("escola", out[0]["happened"].lower())
        self.assertIn("IA", out[0]["why"])
        self.assertTrue(all("https://" not in x["title"] for x in out))

    def test_why_matters_scores_goals_and_decisions(self):
        research = load()
        goals = {"work": "estudar mecânica dos fluidos"}
        why = research.why_matters(
            "IA",
            "pt",
            title="Modelo novo na mecânica dos fluidos",
            happened="Um lab soltou um solver hoje.",
            goals=goals,
        )
        self.assertIn("meta de trabalho", why)
        self.assertNotIn("Pediste para acompanhar", why)
        decide = research.why_matters(
            "IA",
            "pt",
            title="O congresso deve aprovar a regra",
            happened="A votação pode sair hoje.",
            goals={},
        )
        self.assertIn("decisão", decide)

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
            with patch.object(research, "article_lede", return_value="A lab shipped a fresh model this morning."):
                out = research.clips(["AI"], language="de", now=NOW)
        self.assertEqual([x["title"] for x in out], ["Fresh model ships"])
        self.assertIn("AI", out[0]["why"])
        self.assertIn("model", out[0]["happened"])
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

    def test_image_for_skips_google_news_mark(self):
        research = load()
        from io import BytesIO
        from PIL import Image

        logo = b"\xff\xd8\xff" + b"\x00" * 80
        buf = BytesIO()
        Image.new("RGB", (640, 400), (30, 30, 30)).save(buf, format="JPEG")
        cartoon = buf.getvalue()
        page = (
            '<html><head><meta property="og:image" content="https://www.gstatic.com/gnews/logo.png"></head>'
            '<body><img src="https://paper.test/charge-do-dia.jpg" width="640"></body></html>'
        )

        def fake_page(url: str, source_url: str = "", title: str = ""):
            return "https://paper.test/charge", page

        def fake_img(url: str) -> bytes:
            if "gstatic" in url or "logo" in url:
                return logo
            if "charge-do-dia" in url:
                return cartoon
            return b""

        with patch.object(research, "follow_publisher", side_effect=fake_page):
            with patch.object(research, "fetch_image", side_effect=fake_img):
                data = research.image_for(
                    "https://news.google.com/articles/x",
                    "https://www.gstatic.com/gnews/logo.png",
                )
        self.assertEqual(data, cartoon)
        self.assertTrue(research.logoish("https://www.gstatic.com/gnews/logo.png"))
        self.assertTrue(research.googleish("https://news.google.com/rss/articles/x"))
        self.assertFalse(research.article_href("https://www.google-analytics.com/analytics.js"))
        self.assertTrue(research.article_href("https://atarde.com.br/charges/charge-do-dia-17092026"))


if __name__ == "__main__":
    unittest.main()
