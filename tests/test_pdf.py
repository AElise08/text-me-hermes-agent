import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PdfTests(unittest.TestCase):
    def test_writes_a4_pdf_with_portuguese(self):
        pdf = load("pdf_mod", "scripts/pdf.py")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "day.pdf"
            pdf.write_pdf(path, "# Edição de 17/09\n\n- Café da manhã\n- ônibus pra campus\n")
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-1.4"))
            self.assertIn(b"%%EOF", data[-16:])
            self.assertGreater(len(data), 2000)


class IppTests(unittest.TestCase):
    def test_ipp_uri_becomes_http_631(self):
        printer = load("printer_mod", "scripts/printer.py")
        self.assertEqual(
            printer.http_url("ipp://192.168.1.50/ipp/print"),
            "http://192.168.1.50:631/ipp/print",
        )
