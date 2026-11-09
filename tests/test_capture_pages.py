import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import capture_pages


class CapturePagesTests(unittest.TestCase):
    def args(self, source: Path, output: Path) -> argparse.Namespace:
        return argparse.Namespace(
            shottr_dir=source, output_dir=output, mode="click", x=200, y=300,
            count=3, browser="Google Chrome", delay=0, focus_wait=0.0,
            wait=0.0, timeout=2.0
        )

    @patch("capture_pages.shottr_is_running", return_value=True)
    @patch("builtins.input", return_value="")
    @patch("capture_pages.countdown")
    @patch("capture_pages.time.sleep")
    @patch("capture_pages.load_pyautogui")
    @patch("capture_pages.subprocess.run")
    def test_five_captures_are_ordered_and_four_clicks_are_sent(
        self, open_command, load_gui, _sleep, _countdown, _input, _shottr_running
    ):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "shottr"
            output = Path(root) / "output"
            source.mkdir()
            gui = Mock()
            gui.position.return_value = argparse.Namespace(x=100, y=100)
            gui.size.return_value = argparse.Namespace(width=1000, height=800)
            load_gui.return_value = gui
            colors = ("red", "green", "blue", "yellow", "purple")

            captured = []

            def save_shottr_image(command, check):
                if command[1].startswith("shottr://"):
                    number = len(captured) + 1
                    captured.append(command[1])
                    Image.new("RGB", (20, 10), colors[number - 1]).save(
                        source / f"shottr_{number}.png"
                    )

            open_command.side_effect = save_shottr_image
            args = self.args(source, output)
            args.count = 5
            capture_pages.run(args)

            self.assertEqual(open_command.call_count, 10)
            self.assertEqual(open_command.call_args_list[0].args[0][1], capture_pages.AREA_URL)
            self.assertEqual(open_command.call_args_list[1].args[0], ["open", "-a", "Google Chrome"])
            self.assertEqual(open_command.call_args_list[2].args[0][1], capture_pages.REPEAT_URL)
            self.assertEqual(gui.click.call_count, 4)
            self.assertEqual(gui.moveTo.call_count, 4)
            self.assertEqual(
                open_command.call_args_list[-1].args[0],
                ["open", str((output / "run_0001").resolve())],
            )
            gui.moveTo.assert_called_with(x=200, y=140)
            self.assertEqual(
                sorted(path.name for path in (output / "run_0001").iterdir()),
                [f"page_{number:04d}.png" for number in range(1, 6)],
            )
            for number, color in enumerate(colors, start=1):
                with Image.open(output / "run_0001" / f"page_{number:04d}.png") as image:
                    self.assertEqual(image.size, (20, 10))
                    self.assertEqual(image.convert("RGB").getpixel((0, 0)), Image.new("RGB", (1, 1), color).getpixel((0, 0)))

    def test_new_run_folder_keeps_previous_images(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output"
            output.mkdir()
            page = output / "page_0001.png"
            page.write_bytes(b"existing")
            first = capture_pages.new_run_folder(output)
            (first / "page_0001.png").write_bytes(b"first run")
            second = capture_pages.new_run_folder(output)
            self.assertEqual(first.name, "run_0001")
            self.assertEqual(second.name, "run_0002")
            self.assertEqual(page.read_bytes(), b"existing")
            self.assertEqual((first / "page_0001.png").read_bytes(), b"first run")

    def test_mouse_corner_requests_stop(self):
        gui = Mock()
        gui.position.return_value = argparse.Namespace(x=0, y=0)
        gui.size.return_value = argparse.Namespace(width=1000, height=800)
        with self.assertRaises(capture_pages.StopRequested):
            capture_pages.check_stop(gui)

    @patch("capture_pages.shottr_is_running", return_value=False)
    @patch("capture_pages.load_pyautogui")
    def test_missing_shottr_stops_before_gui_actions(self, load_gui, _shottr_running):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "shottr"
            source.mkdir()
            with self.assertRaisesRegex(RuntimeError, "Shottr が起動していません"):
                capture_pages.run(self.args(source, Path(root) / "output"))
            load_gui.assert_not_called()

    @patch("capture_pages.shottr_is_running", return_value=True)
    @patch("builtins.input", return_value="")
    @patch("capture_pages.countdown")
    @patch("capture_pages.time.sleep")
    @patch("capture_pages.load_pyautogui")
    @patch("capture_pages.subprocess.run")
    def test_duplicate_image_stops_before_third_capture(
        self, open_command, load_gui, _sleep, _countdown, _input, _shottr_running
    ):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "shottr"
            output = Path(root) / "output"
            source.mkdir()
            gui = Mock()
            gui.position.return_value = argparse.Namespace(x=100, y=100)
            gui.size.return_value = argparse.Namespace(width=1000, height=800)
            load_gui.return_value = gui
            shot_count = 0

            def save_same_image(command, check):
                nonlocal shot_count
                if command[1].startswith("shottr://"):
                    shot_count += 1
                    Image.new("RGB", (20, 10), "red").save(
                        source / f"shottr_{shot_count}.png"
                    )

            open_command.side_effect = save_same_image
            with self.assertRaisesRegex(RuntimeError, "画素が同じ"):
                capture_pages.run(self.args(source, output))
            self.assertEqual(shot_count, 2)
            self.assertEqual(gui.click.call_count, 1)
            self.assertTrue((output / "run_0001" / "page_0002.png").exists())
            self.assertFalse((output / "run_0001" / "page_0003.png").exists())


if __name__ == "__main__":
    unittest.main()
