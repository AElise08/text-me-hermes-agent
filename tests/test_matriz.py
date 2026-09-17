import json, os, subprocess, tempfile, unittest, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "matriz.py"
NUDGE = ROOT / "scripts" / "morning_nudge.py"
DATES = ROOT / "scripts" / "dates.py"


class MatrixTests(unittest.TestCase):
    def cli(self, h, *a):
        return json.loads(
            subprocess.check_output(
                ["python3", str(SCRIPT), *a],
                env={**os.environ, "HERMES_HOME": h},
                text=True,
            )
        )

    def test_life_work_quadrants_goals_and_morning(self):
        with tempfile.TemporaryDirectory() as h:
            self.cli(h, "goal", "set", "--category", "work", "--text", "Ship")
            self.cli(h, "goal", "set", "--category", "life", "--text", "Sleep")
            w = self.cli(
                h, "add", "--text", "report", "--category", "work",
                "--important", "yes", "--urgent", "yes",
            )["created"]
            l = self.cli(
                h, "add", "--text", "walk", "--category", "life",
                "--important", "yes", "--urgent", "no",
            )["created"]
            show = self.cli(h, "show")
            self.assertEqual(show["goals"], {"work": "Ship", "life": "Sleep"})
            self.assertEqual(show["categories"]["work"]["Q1"][0]["id"], w["id"])
            self.assertEqual(show["categories"]["life"]["Q2"][0]["id"], l["id"])
            m = self.cli(h, "morning")
            self.assertEqual(m["categories"]["work"]["do_now"][0]["text"], "report")
            self.assertEqual(m["categories"]["life"]["protect_next"][0]["text"], "walk")

    def test_nudge_empty_and_pt(self):
        with tempfile.TemporaryDirectory() as h:
            e = {**os.environ, "HERMES_HOME": h}
            out = subprocess.check_output(["python3", str(NUDGE)], env=e, text=True)
            self.assertIn("most important", out)
            self.assertIn("mais importante", out)
            self.cli(h, "language", "set", "pt")
            out = subprocess.check_output(["python3", str(NUDGE)], env=e, text=True)
            self.assertIn("mais importante", out)

    def test_update_category(self):
        with tempfile.TemporaryDirectory() as h:
            x = self.cli(
                h, "add", "--text", "x", "--category", "work",
                "--important", "no", "--urgent", "yes",
            )["created"]
            y = self.cli(
                h, "update", x["id"], "--category", "life",
                "--important", "yes", "--urgent", "no",
            )["updated"]
            self.assertEqual((y["category"], y["quadrant"]), ("life", "Q2"))

    def test_duration_learns_from_extensions(self):
        with tempfile.TemporaryDirectory() as h:
            first = self.cli(
                h, "duration", "suggest", "--activity", "editar video", "--asked", "45"
            )
            self.assertEqual(first["suggested_minutes"], 45)
            block = self.cli(
                h, "block", "start", "--text", "editar video", "--minutes", "45"
            )["created"]
            self.cli(h, "block", "extend", block["id"], "--minutes", "20")
            self.cli(h, "block", "extend", block["id"], "--minutes", "20")
            self.cli(h, "block", "extend", block["id"], "--minutes", "20")
            closed = self.cli(h, "block", "close", block["id"])
            self.assertEqual(closed["updated"]["actual_minutes"], 105)
            again = self.cli(
                h, "duration", "suggest", "--activity", "editar video", "--asked", "45"
            )
            self.assertGreaterEqual(again["suggested_minutes"], 45)
            second = self.cli(
                h, "block", "start", "--text", "editar video", "--minutes", "45"
            )
            self.assertTrue(second["used_learned_duration"])
            self.assertGreater(second["created"]["planned_minutes"], 45)

    def test_commit_reads_date_from_html_never_invents(self):
        with tempfile.TemporaryDirectory() as h:
            html = "<html><body>Hackathon ends on September 23, 2026. Kickoff was 2026-01-01.</body></html>"
            created = self.cli(
                h, "commit", "add", "--text", "depois do hackathon", "--html", html
            )["created"]
            self.assertEqual(created["mode"], "after_url")
            self.assertTrue(created["after_when"].startswith("2026-09-23"))
            empty = self.cli(
                h, "commit", "add", "--text", "depois", "--html", "<p>no dates here</p>"
            )["created"]
            self.assertEqual(empty["after_when"], "")
            self.assertEqual(empty["dates"], [])

    def test_commit_blocks_a_non_public_link(self):
        with tempfile.TemporaryDirectory() as h:
            created = self.cli(
                h, "commit", "add", "--text", "after launch", "--after-url", "http://127.0.0.1/private"
            )["created"]
            self.assertIn("public http", created["fetch_error"])
            self.assertEqual(created["after_when"], "")

    def test_concurrent_writes_do_not_drop_tasks(self):
        with tempfile.TemporaryDirectory() as h:
            processes = [
                subprocess.Popen(
                    [
                        "python3", str(SCRIPT), "add", "--text", f"task-{i}",
                        "--category", "work", "--important", "yes", "--urgent", "no",
                    ],
                    env={**os.environ, "HERMES_HOME": h},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for i in range(16)
            ]
            errors = [p.communicate()[1] for p in processes]
            self.assertTrue(all(p.returncode == 0 for p in processes), errors)
            shown = self.cli(h, "show")
            self.assertEqual(len(shown["categories"]["work"]["Q2"]), 16)

    def test_edition_writes_epub_and_respects_kindle_delivery(self):
        with tempfile.TemporaryDirectory() as h:
            self.cli(h, "profile", "set", "--delivery", "kindle", "--routine", "bus to campus")
            self.cli(h, "language", "set", "en")
            self.cli(h, "goal", "set", "--category", "work", "--text", "Ship the Kindle edition")
            out = self.cli(h, "edition", "--no-send")
            md = Path(out["markdown"]).read_text(encoding="utf-8")
            self.assertIn("Today in one sentence", md)
            self.assertNotIn("What needs you today", md)
            self.assertNotIn("Nothing in the inbox matches", md)
            self.assertIn("kindle edition", md.lower())
            self.assertEqual(md.lower().count("ship the kindle edition"), 1)
            self.assertIn("morning edition", md)
            self.assertNotIn("A yes waiting in email", md)
            self.assertNotIn("bus to campus", md)
            self.assertNotIn("Routine:", md)
            epub = Path(out["epub"])
            pdf = Path(out["pdf"])
            self.assertEqual(out["delivery"], "kindle")
            self.assertNotIn("sent", out)
            self.assertTrue(epub.exists())
            self.assertTrue(pdf.exists())
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            self.assertTrue(epub.exists())
            with zipfile.ZipFile(epub) as zf:
                self.assertIn("mimetype", zf.namelist())
                self.assertEqual(zf.read("mimetype"), b"application/epub+zip")
                self.assertIn("OEBPS/PlayfairDisplay-Bold.ttf", zf.namelist())
                self.assertIn("OEBPS/UnifrakturCook-Bold.ttf", zf.namelist())
                body = zf.read("OEBPS/body.html").decode("utf-8")
                self.assertIn('class="masthead"', body)
                self.assertIn("The Text-me", body)
            e = {**os.environ, "HERMES_HOME": h}
            nudge = subprocess.check_output(["python3", str(NUDGE)], env=e, text=True)
            self.assertIn("Kindle", nudge)

    def test_profile_setup(self):
        with tempfile.TemporaryDirectory() as h:
            p = self.cli(
                h, "profile", "set",
                "--delivery", "printer",
                "--interests", "films, series",
                "--avoid", "violence",
                "--done",
            )["profile"]
            self.assertTrue(p["setup_done"])
            self.assertEqual(p["delivery"], "printer")
            self.assertEqual(p["avoid"], ["violence"])

    def test_learn_saves_investor_as_work_and_correction_moves_it(self):
        with tempfile.TemporaryDirectory() as h:
            saved = self.cli(
                h, "learn", "add", "--sphere", "work",
                "--text", "follow-up of an investor",
            )
            self.assertEqual(saved["learned"]["sphere"], "work")
            show = self.cli(h, "learn", "show")
            self.assertEqual(show["known"]["work"][0]["text"], "follow-up of an investor")
            self.cli(
                h, "learn", "add", "--sphere", "life",
                "--text", "follow-up of an investor",
            )
            moved = self.cli(h, "learn", "show")
            self.assertEqual(moved["known"]["work"], [])
            self.assertEqual(moved["known"]["life"][0]["text"], "follow-up of an investor")

    def test_slot_saves_the_whole_day_not_one_block(self):
        with tempfile.TemporaryDirectory() as h:
            aula = self.cli(
                h, "slot", "add",
                "--text", "Aula",
                "--start", "2026-09-17T07:30:00-03:00",
                "--end", "2026-09-17T09:20:00-03:00",
            )["created"]
            self.cli(
                h, "slot", "add",
                "--text", "Estudo faculdade",
                "--start", "2026-09-17T09:20:00-03:00",
                "--end", "2026-09-17T11:10:00-03:00",
            )
            self.cli(
                h, "slot", "add",
                "--text", "Aula",
                "--start", "2026-09-17T11:10:00-03:00",
                "--end", "2026-09-17T13:00:00-03:00",
            )
            fisio = self.cli(
                h, "slot", "add",
                "--text", "Fisioterapia",
                "--start", "2026-09-17T15:00:00-03:00",
                "--end", "2026-09-17T16:20:00-03:00",
            )["created"]
            again = self.cli(
                h, "slot", "add",
                "--text", "Aula",
                "--start", "2026-09-17T07:30:00-03:00",
                "--end", "2026-09-17T09:20:00-03:00",
            )
            listed = self.cli(h, "slot", "list")["slots"]
            self.assertEqual(len(listed), 4)
            self.assertEqual(aula["text"], "Aula")
            self.assertEqual(fisio["text"], "Fisioterapia")
            self.assertEqual(again["skipped"], "duplicate")

    def test_day_dump_books_every_clock_not_only_study(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("day", ROOT / "scripts" / "day.py")
        day = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(day)
        when = datetime(2026, 9, 17, tzinfo=timezone.utc).astimezone()
        text = (
            "Oi, então eu tenho faculdade amanhã às 7h30. Aí eu vou ter horário "
            "livre entre 9h20 às 11h10 na faculdade. Então eu não consigo fazer "
            "muita coisa. Eu tenho aula das 11h10 até 1h da tarde. E fora isso "
            "eu também tenho fisioterapia 3 horas da tarde, então provavelmente "
            "eu vou ter que almoçar na faculdade. E vai até umas 4h20."
        )
        slots = day.parse(text, when.replace(hour=0, minute=0, second=0, microsecond=0))
        self.assertGreaterEqual(len(slots), 3)
        blob = " ".join(s["text"].casefold() for s in slots)
        self.assertRegex(blob, r"aula|faculdade")
        self.assertRegex(blob, r"fisio|livre|estudo|aula")
        starts = [s["start"][11:16] for s in slots]
        self.assertTrue(any(t <= "08:00" for t in starts), starts)
        self.assertTrue(any(t >= "14:00" for t in starts), starts)
        en = (
            "I have class tomorrow at 7:30. Free between 9:20 and 11:10. "
            "Class from 11:10 to 1pm. Gym at 3pm until 4:20."
        )
        en_slots = day.parse(en, when.replace(hour=0, minute=0, second=0, microsecond=0))
        self.assertGreaterEqual(len(en_slots), 3)
        with tempfile.TemporaryDirectory() as h:
            out = self.cli(h, "day", "--date", "2026-09-17", "--text", text)
            self.assertGreaterEqual(len(out["created"]), 3)

    def test_learn_reading_and_hobby_and_edition_separates_them(self):
        with tempfile.TemporaryDirectory() as h:
            self.cli(h, "learn", "add", "--sphere", "reading", "--text", "lista de livros")
            self.cli(h, "learn", "add", "--sphere", "hobby", "--text", "piano")
            known = self.cli(h, "learn", "show")["known"]
            self.assertEqual(known["reading"][0]["text"], "lista de livros")
            self.assertEqual(known["hobby"][0]["text"], "piano")
            import importlib.util
            import sys
            scripts = str(ROOT / "scripts")
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            spec = importlib.util.spec_from_file_location(
                "edition", ROOT / "scripts" / "edition.py"
            )
            edition = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(edition)
            md = edition.compose(
                {"language": "pt", "goals": {}, "tasks": [], "profile": {}},
                datetime.now(timezone.utc),
                extra={
                    "fires": [
                        {
                            "text": "Lembrete de pagamento — fatura de luz",
                            "sphere": "life",
                        }
                    ],
                    "readings": ["lista de livros"],
                    "hobbies": ["piano"],
                },
            )
            self.assertIn("Leituras", md)
            self.assertIn("lista de livros", md)
            self.assertIn("Hobbies", md)
            self.assertIn("piano", md)
            self.assertIn("Lembrete de pagamento", md)
            self.assertNotIn("Vida: Lembrete", md)

    def test_focus_orders_by_importance_not_insertion(self):
        with tempfile.TemporaryDirectory() as h:
            self.cli(
                h, "add", "--text", "arrumar gaveta", "--category", "life",
                "--important", "no", "--urgent", "no",
            )
            self.cli(
                h, "add", "--text", "escrever newsletter", "--category", "work",
                "--important", "yes", "--urgent", "no", "--reason", "meta da semana",
            )
            self.cli(
                h, "add", "--text", "entregar relatório", "--category", "work",
                "--important", "yes", "--urgent", "yes", "--reason", "prazo hoje",
            )
            self.cli(h, "language", "set", "pt")
            out = self.cli(h, "edition", "--no-send")
            md = Path(out["markdown"]).read_text(encoding="utf-8")
            self.assertIn("Seu Reporte Diário", out["title"])
            q1 = md.index("entregar relatório")
            q2 = md.index("escrever newsletter")
            q4 = md.index("arrumar gaveta")
            self.assertLess(q1, q2)
            self.assertLess(q2, q4)
            self.assertIn("prazo hoje", md)

    def test_extra_file_injects_research_and_title(self):
        with tempfile.TemporaryDirectory() as h:
            extra = Path(h) / "extra.json"
            extra.write_text(json.dumps({
                "title": "Seu Report Diário — 17/09",
                "clips": ["IA na educação: resumo curto de uma frase."],
                "charge": ["Charge do dia — The Guardian https://example.com/c"],
                "meetings": ["07:30–09:20  Aula"],
            }), encoding="utf-8")
            self.cli(h, "language", "set", "pt")
            out = self.cli(h, "edition", "--no-send", "--extra-file", str(extra))
            md = Path(out["markdown"]).read_text(encoding="utf-8")
            self.assertTrue(out["title"].startswith("Seu Reporte Diário"))
            self.assertIn("IA na educação", md)
            self.assertIn("## Charge do dia", md)
            self.assertIn("The Guardian", md)
            self.assertIn("## Agenda", md)
            self.assertIn("07:30–09:20  Aula", md)
            self.assertIn("## No radar", md)
            start = md.index("## Agenda")
            news = md.index("## No radar")
            self.assertLess(start, news)

    def test_same_commitment_is_not_printed_three_times(self):
        import importlib.util
        import sys
        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("edition", ROOT / "scripts" / "edition.py")
        edition = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(edition)
        md = edition.compose(
            {
                "language": "pt",
                "goals": {"work": "Fechar mecânica dos fluidos usando a janela na faculdade"},
                "tasks": [
                    {
                        "text": "Estudar mecânica dos fluidos",
                        "category": "work",
                        "quadrant": "Q1",
                        "done": False,
                        "due": "2026-09-17",
                        "reason": "janela de 9h20-11h10 na faculdade",
                    }
                ],
                "profile": {"name": "Mel"},
                "blocks": [
                    {"text": "Estudar mecânica dos fluidos", "planned_minutes": 110, "status": "open"}
                ],
            },
            datetime.now(timezone.utc),
        )
        self.assertIn("## Hoje em uma frase", md)
        self.assertLessEqual(md.count("mecânica dos fluidos"), 2)
        self.assertIn("Mel, hoje o que importa é", md)
        self.assertIn("necessário: janela das 9h20 às 11h10", md)
        self.assertNotIn("Mel precisa", md)
        self.assertNotIn("até 2026-09-17", md)
        self.assertNotIn("## Não larga hoje", md)
        self.assertNotIn("## Blocos em andamento", md)
        self.assertNotIn("o usuário", md.lower())
        self.assertNotIn("the user", md.lower())
        self.assertIn("edição da manhã", md)
        self.assertNotIn("Report Diário", md)
        self.assertIn("Reporte Diário", md)

    def test_edition_opens_with_the_matrix_then_calendar_and_news_recap(self):
        import importlib.util
        import sys
        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("edition", ROOT / "scripts" / "edition.py")
        edition = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(edition)
        md = edition.compose(
            {
                "language": "pt",
                "goals": {"work": "acelerar a startup"},
                "tasks": [
                    {
                        "text": "processo de aceleração",
                        "category": "work",
                        "quadrant": "Q1",
                        "done": False,
                        "reason": "prazo da turma",
                    }
                ],
                "profile": {},
                "blocks": [],
            },
            datetime.now(timezone.utc),
            extra={
                "fires": [{"text": "Reunião com a banca às 11h", "sphere": "work", "who": "Banca"}],
                "approvals": [
                    {
                        "text": "Confirmar a banca das 11h",
                        "who": "Banca",
                        "due": "hoje 11:00",
                    }
                ],
                "meetings": ["11:00–12:00  Banca da aceleradora"],
                "clips": [
                    {
                        "title": "IA na sala de aula",
                        "happened": "Uma rede passou a usar modelos na correção.",
                        "why": "Impacto na meta de trabalho: IA na sala de aula.",
                        "source": "Folha",
                    }
                ],
            },
        )
        cover = md.index("## Hoje em uma frase")
        agenda = md.index("## Agenda")
        decisions = md.index("## Decisões")
        risks = md.index("## Riscos e bloqueios")
        people = md.index("## Pessoas")
        actions = md.index("## Próximas ações")
        news = md.index("## No radar")
        self.assertLess(cover, agenda)
        self.assertLess(agenda, decisions)
        self.assertLess(decisions, risks)
        self.assertLess(risks, people)
        self.assertLess(people, actions)
        self.assertLess(actions, news)
        self.assertIn("processo de aceleração", md)
        self.assertIn("Banca da aceleradora", md)
        self.assertIn("prazo hoje 11:00", md)
        self.assertIn("O que aconteceu:", md)
        self.assertIn("Porque te importa:", md)
        self.assertNotIn("Pediste para acompanhar", md)
        self.assertIn("Banca —", md)

    def test_title_date_is_the_local_day_not_the_extra_file(self):
        import importlib.util
        import sys
        from zoneinfo import ZoneInfo

        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("edition", ROOT / "scripts" / "edition.py")
        edition = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(edition)
        when = datetime(2026, 9, 16, 23, 54, tzinfo=ZoneInfo("America/Sao_Paulo"))
        title = edition.stamp_title(True, when, {"title": "Seu Report Diário — 17/09"})
        self.assertEqual(title, "Seu Reporte Diário — 16/09")
        md = edition.compose(
            {"language": "pt", "profile": {"routine": "aula 7h30, fisio 15h"}},
            when,
        )
        self.assertIn("16/09", md)
        self.assertNotIn("Rotina", md)
        self.assertNotIn("7h30", md)

    def test_charge_image_is_inside_the_epub(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (12, 8), (200, 40, 40)).save(buf, format="JPEG")
        with tempfile.TemporaryDirectory() as h:
            extra = Path(h) / "extra.json"
            extra.write_text(json.dumps({
                "meetings": ["07:30–09:20  Aula"],
                "charge": [{"title": "Charge do dia", "line": "Charge do dia", "file": "skip"}],
            }), encoding="utf-8")
            # extra-file cannot carry bytes; dump via compose helper
            import importlib.util, sys
            scripts = str(ROOT / "scripts")
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            spec = importlib.util.spec_from_file_location("edition", ROOT / "scripts" / "edition.py")
            edition = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(edition)
            dest = Path(h) / "editions"
            out = edition.dump(
                {"language": "pt", "goals": {}, "tasks": [], "profile": {}, "blocks": []},
                dest,
                datetime.now(timezone.utc),
                extra={
                    "meetings": ["07:30–09:20  Aula"],
                    "charge": [{"title": "Charge do dia", "line": "Charge do dia", "image": buf.getvalue()}],
                    "clips": ["Uma notícia"],
                },
            )
            md = Path(out["markdown"]).read_text(encoding="utf-8")
            self.assertIn("## Agenda", md)
            self.assertIn("07:30–09:20  Aula", md)
            self.assertIn("![Charge](charge-0.jpg)", md)
            self.assertIn("## No radar", md)
            with zipfile.ZipFile(out["epub"]) as zf:
                names = zf.namelist()
                self.assertIn("OEBPS/charge-0.jpg", names)
                self.assertTrue(zf.read("OEBPS/charge-0.jpg")[:3] == b"\xff\xd8\xff")
            from PIL import Image as PilImage
            import pdf as pdf_mod
            pages = pdf_mod.pages_from_markdown(
                md,
                {"charge-0.jpg": Path(out["markdown"]).with_name("charge-0.jpg").read_bytes()},
            )
            paper = (247, 243, 234)
            inked = []
            for page in pages:
                sample = page.resize((40, 56), PilImage.BOX)
                inked.append(any(px != paper for px in sample.getdata()))
            self.assertTrue(any(inked))
            tones = 0
            for page in pages:
                for px in page.resize((80, 110), PilImage.BOX).getdata():
                    if px[0] > 140 and px[1] < 110 and px[2] < 110:
                        tones += 1
            self.assertGreater(tones, 0)
            self.assertTrue(Path(out["pdf"]).read_bytes().startswith(b"%PDF"))

    def test_profile_name_survives(self):
        with tempfile.TemporaryDirectory() as h:
            p = self.cli(h, "profile", "set", "--name", "Mel")["profile"]
            self.assertEqual(p["name"], "Mel")


class DateParseTests(unittest.TestCase):
    def test_named_and_iso(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dates", DATES)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = datetime(2026, 9, 17, tzinfo=timezone.utc)
        found = mod.parse_html(
            "<p>Ends September 23, 2026 and also 2026-10-01</p>", now=now
        )
        self.assertEqual(found[0]["date"], "2026-09-23")
        self.assertEqual(found[-1]["date"], "2026-10-01")
        self.assertEqual(mod.latest(found)["date"], "2026-10-01")


if __name__ == "__main__":
    unittest.main()
