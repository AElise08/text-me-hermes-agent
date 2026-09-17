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

    def test_photo_is_not_a_drawing(self):
        buf = BytesIO()
        Image.new("RGB", (200, 140), (40, 80, 120)).save(buf, format="JPEG")
        # a flat fill still has few colors; a noisy photo does not
        noisy = Image.new("RGB", (120, 80))
        pix = noisy.load()
        for x in range(120):
            for y in range(80):
                pix[x, y] = ((x * 13) % 256, (y * 29) % 256, (x * y) % 256)
        buf2 = BytesIO()
        noisy.save(buf2, format="JPEG")
        self.assertFalse(cartoon.is_drawing(buf2.getvalue()))
        self.assertTrue(cartoon.is_drawing(cartoon.original_daily_cartoon("pt")["image"]))
        skin = Image.new("RGB", (200, 140), (190, 140, 110))
        buf3 = BytesIO()
        skin.save(buf3, format="JPEG")
        self.assertTrue(cartoon.looks_like_photo(buf3.getvalue()))
        self.assertFalse(cartoon.looks_like_photo(cartoon.original_daily_cartoon("pt")["image"]))
if __name__ == "__main__": unittest.main()
