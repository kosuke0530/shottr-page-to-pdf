"""Phase 1: Shottr capture and browser page advance, tested separately."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


AREA_URL = "shottr://grab/area?then=save"
REPEAT_URL = "shottr://grab/repeat?then=save"


def countdown(seconds: int, instruction: str) -> None:
    print(instruction, flush=True)
    for remaining in range(seconds, 0, -1):
        print(f"  {remaining}...", flush=True)
        time.sleep(1)


def load_pyautogui():
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError(
            "PyAutoGUI がありません。README.md の手順でインストールしてください。"
        ) from exc
    pyautogui.FAILSAFE = True
    return pyautogui


def capture(args: argparse.Namespace) -> None:
    if args.repeat and args.shortcut:
        raise ValueError("--repeat と --shortcut は同時に指定できません。")

    if args.shortcut:
        print("撮影: Shottr の ⌘⇧2。範囲選択後、Shottr で手動保存します。")
    else:
        mode = "前回の範囲" if args.repeat else "新しく選ぶ範囲"
        print(f"撮影: Shottr の {mode}。Shottr の既定フォルダに自動保存します。")
    input("準備ができたら Enter を押してください（Ctrl+C で中止）: ")
    countdown(args.delay, "撮影する画面を表示してください。")

    if args.shortcut:
        load_pyautogui().hotkey("command", "shift", "2")
    else:
        url = REPEAT_URL if args.repeat else AREA_URL
        subprocess.run(["open", url], check=True)

    print("撮影を起動しました。Shottr の保存先で画像を確認してください。")


def advance(args: argparse.Namespace) -> None:
    pyautogui = load_pyautogui()
    if args.mode == "click":
        if (args.x is None) != (args.y is None):
            raise ValueError("座標を指定する場合は --x と --y を両方指定してください。")
        if args.x is None:
            countdown(args.delay, "ページ送りボタンの中央にマウスを置いてください。")
            point = pyautogui.position()
            x, y = point.x, point.y
        else:
            x, y = args.x, args.y
        print(f"操作: ({x}, {y}) を1回クリック。操作後 {args.wait:g} 秒待機します。")
    else:
        if args.x is not None or args.y is not None:
            raise ValueError("矢印キー方式では --x / --y は使えません。")
        print(f"操作: 右矢印キーを1回押す。操作後 {args.wait:g} 秒待機します。")

    input("この操作でよければ Enter を押してください（Ctrl+C で中止）: ")
    countdown(args.delay, "ブラウザを表示し、必要ならクリックしてフォーカスを移してください。")
    if args.mode == "click":
        pyautogui.click(x=x, y=y)
    else:
        pyautogui.press("right")
    time.sleep(args.wait)
    print("ページ送り操作が終わりました。ブラウザの表示を確認してください。")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 1: Shottr 撮影とページ送りを個別に試します。"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    capture_parser = commands.add_parser("capture", help="Shottr で1枚撮影")
    capture_parser.add_argument(
        "--repeat", action="store_true", help="Shottr の前回選択範囲を再撮影"
    )
    capture_parser.add_argument(
        "--shortcut", action="store_true", help="現在の ⌘⇧2 ショートカットを試す"
    )
    capture_parser.add_argument(
        "--delay", type=int, default=5, help="撮影前の秒数（初期値: 5）"
    )
    capture_parser.set_defaults(func=capture)

    advance_parser = commands.add_parser("advance", help="ページを1回送る")
    advance_parser.add_argument(
        "--mode", choices=("click", "key"), default="click", help="操作方式（初期値: click）"
    )
    advance_parser.add_argument("--x", type=int, help="クリックする X 座標")
    advance_parser.add_argument("--y", type=int, help="クリックする Y 座標")
    advance_parser.add_argument(
        "--delay", type=int, default=5, help="操作前の秒数（初期値: 5）"
    )
    advance_parser.add_argument(
        "--wait", type=float, default=2.0, help="操作後の待機秒数（初期値: 2）"
    )
    advance_parser.set_defaults(func=advance)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.delay < 0:
        parser.error("--delay は0以上にしてください。")
    if args.command == "advance" and args.wait < 0:
        parser.error("--wait は0以上にしてください。")
    if sys.platform != "darwin":
        parser.error("このツールは macOS 専用です。")
    try:
        args.func(args)
    except (KeyboardInterrupt, EOFError):
        print("\n操作を中止しました。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
