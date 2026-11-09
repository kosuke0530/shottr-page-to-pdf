from pathlib import Path
import tempfile
import unittest

from PIL import Image
import pikepdf

import phase4


class Phase4Tests(unittest.TestCase):
    def save_png(self, folder: Path, number: int, width: int) -> None:
        with Image.new("RGB", (width, 10), (number * 30 % 256, 80, 120)) as image:
            image.save(folder / f"page_{number:04d}.png")

    def test_quality_pdf_follows_filename_order_and_preserves_ratio(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "images"
            folder.mkdir()
            for number, width in ((3, 40), (1, 20), (2, 30)):
                self.save_png(folder, number, width)
            output = Path(root) / "ordered.pdf"
            pages, size = phase4.create_pdf(folder, output)
            self.assertEqual(pages, 3)
            self.assertGreater(size, 0)
            with pikepdf.Pdf.open(output) as pdf:
                widths = [float(page.MediaBox[2]) for page in pdf.pages]
                heights = [float(page.MediaBox[3]) for page in pdf.pages]
            self.assertEqual(widths, [10.0, 15.0, 20.0])
            self.assertEqual(heights, [5.0, 5.0, 5.0])

    def test_small_split_can_show_right_page_first(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "images"
            folder.mkdir()
            self.save_png(folder, 1, 25)
            output = Path(root) / "split.pdf"
            pages, _ = phase4.create_pdf(
                folder, output, mode="small", split=True, split_order="right-left"
            )
            self.assertEqual(pages, 2)
            with pikepdf.Pdf.open(output) as pdf:
                widths = [float(page.MediaBox[2]) for page in pdf.pages]
            self.assertEqual(widths, [6.5, 6.0])

    def test_existing_pdf_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "images"
            folder.mkdir()
            self.save_png(folder, 1, 20)
            output = Path(root) / "existing.pdf"
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                phase4.create_pdf(folder, output)
            self.assertEqual(output.read_bytes(), b"existing")

    def test_missing_number_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            self.save_png(folder, 1, 20)
            self.save_png(folder, 3, 40)
            with self.assertRaisesRegex(ValueError, "連続"):
                phase4.numbered_images(folder)

    def test_more_than_one_chunk_keeps_all_pages_in_order(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "images"
            folder.mkdir()
            for number in range(1, 52):
                self.save_png(folder, number, 20 + number)
            output = Path(root) / "many.pdf"
            pages, _ = phase4.create_pdf(folder, output)
            self.assertEqual(pages, 51)
            with pikepdf.Pdf.open(output) as pdf:
                self.assertEqual(len(pdf.pages), 51)
                self.assertEqual(float(pdf.pages[0].MediaBox[2]), 10.5)
                self.assertEqual(float(pdf.pages[-1].MediaBox[2]), 35.5)


if __name__ == "__main__":
    unittest.main()
