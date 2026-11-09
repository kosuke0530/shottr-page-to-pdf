import argparse
import unittest
from unittest.mock import Mock, patch

import phase1


class Phase1Tests(unittest.TestCase):
    @patch("builtins.input", return_value="")
    @patch("phase1.countdown")
    @patch("phase1.subprocess.run")
    def test_capture_uses_shottr_repeat_and_save(self, run, _countdown, _input):
        args = argparse.Namespace(repeat=True, shortcut=False, delay=0)
        phase1.capture(args)
        run.assert_called_once_with(["open", phase1.REPEAT_URL], check=True)

    @patch("builtins.input", return_value="")
    @patch("phase1.countdown")
    @patch("phase1.time.sleep")
    @patch("phase1.load_pyautogui")
    def test_click_uses_picked_mouse_position(self, load_gui, _sleep, _countdown, _input):
        gui = Mock()
        gui.position.return_value = argparse.Namespace(x=321, y=654)
        load_gui.return_value = gui
        args = argparse.Namespace(mode="click", x=None, y=None, delay=0, wait=2.0)
        phase1.advance(args)
        gui.click.assert_called_once_with(x=321, y=654)
        gui.press.assert_not_called()

    @patch("builtins.input", return_value="")
    @patch("phase1.countdown")
    @patch("phase1.time.sleep")
    @patch("phase1.load_pyautogui")
    def test_key_mode_sends_one_right_press(self, load_gui, _sleep, _countdown, _input):
        gui = Mock()
        load_gui.return_value = gui
        args = argparse.Namespace(mode="key", x=None, y=None, delay=0, wait=2.0)
        phase1.advance(args)
        gui.press.assert_called_once_with("right")
        gui.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
