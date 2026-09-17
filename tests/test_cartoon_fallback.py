import sys
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cartoon
class CartoonFallbackTests(unittest.TestCase):
    def test_original_cartoon_is_a_readable_image(self):
        row=cartoon.original_daily_cartoon("pt")
        self.assertTrue(row["image"])
        im=Image.open(BytesIO(row["image"]))
        self.assertGreaterEqual(im.width, 900)
        self.assertIn("lista", row["line"].lower())
if __name__ == "__main__": unittest.main()
