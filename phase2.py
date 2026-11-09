"""Phase 2/3: capture ordered browser spreads with Shottr."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from PIL import Image

from phase1 import AREA_URL, REPEAT_URL, countdown, load_pyautogui


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
DEFAULT_COUNT = 3
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "captures"


class StopRequested(Exception):
    """The mouse was moved to a primary-screen corner."""


def shottr_is_running() -> bool:
    from AppKit import NSRunningApplication

    return bool(
        NSRunningApplication.runningApplicationsWithBundleIdentifier_("cc.ffitch.shottr")
    )


def check_stop(gui) -> None:
    point = gui.position()
    screen = gui.size()
    if (point.x <= 0 or point.x >= screen.width - 1) and (
        point.y <= 0 or point.y >= screen.height - 1
    ):
        raise StopRequested("マウスが画面の隅に移動したため停止しました")


def pause_with_stop(seconds: float, gui) -> None:
    deadline = time.monotonic() + seconds
    while True:
        check_stop(gui)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.2, remaining))


def new_run_folder(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for number in range(1, 10_000):
        folder = parent / f"run_{number:04d}"
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        return folder
    raise RuntimeError("保存用の run フォルダを作成できませんでした")


def choose_shottr_folder() -> Path:
    print("Shottr の設定画面に表示されている保存先と、同じフォルダを選んでください。")
    result = subprocess.run(
        [
            "osascript", "-e",
            'POSIX path of (choose folder with prompt "Shottrの設定と同じ保存先を選択")',
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Shottr の保存先フォルダ選択を中止しました")
    return Path(result.stdout.strip())


def image_files(folder: Path) -> set[Path]:
    return {
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }


def wait_for_shottr_file(folder: Path, before: set[Path], timeout: float, gui) -> Path:
    deadline = time.monotonic() + timeout
    last_size = None
    while time.monotonic() < deadline:
        check_stop(gui)
        created = image_files(folder) - before
        if len(created) > 1:
            raise RuntimeError(
                "Shottr の保存先に複数の新しい画像が現れました。取り違え防止のため停止します。"
            )
        if created:
            path = next(iter(created))
            size = path.stat().st_size
            if size > 0 and size == last_size:
                return path
            last_size = size
        time.sleep(0.2)
    raise TimeoutError(
        f"{timeout:g} 秒以内に選択フォルダ {folder} に新しい画像が見つかりませんでした。"
        "Shottr の設定画面にある保存先と一致しているか、範囲選択を完了したか確認してください。"
    )


def save_png_without_overwrite(source: Path, destination: Path) -> tuple[tuple[int, int], str]:
    """Decode one image, write a PNG, and link it into place only if absent."""
    temp_path: Path | None = None
    try:
        with Image.open(source) as image:
            image.load()
            dimensions = image.size
            pixels = hashlib.sha256()
            pixels.update(f"{dimensions[0]}x{dimensions[1]}:".encode("ascii"))
            pixels.update(image.convert("RGBA").tobytes())
            digest = pixels.hexdigest()
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{destination.stem}-", suffix=".tmp",
                dir=destination.parent, delete=False
            ) as temp:
                temp_path = Path(temp.name)
                image.save(temp, format="PNG")
        os.link(temp_path, destination)  # FileExistsError if another process created it.
        return dimensions, digest
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run(args: argparse.Namespace) -> None:
    source_dir = (args.shottr_dir or choose_shottr_folder()).expanduser().resolve()
    output_root = args.output_dir.expanduser().resolve()
    if not source_dir.is_dir():
        raise ValueError(f"Shottr の保存先が見つかりません: {source_dir}")
    if not shottr_is_running():
        raise RuntimeError("Shottr が起動していません。Shottr を起動してから再実行してください")

    gui = load_pyautogui()
    if args.mode == "click":
        if (args.x is None) != (args.y is None):
            raise ValueError("座標を指定する場合は --x と --y を両方指定してください。")
        if args.x is None:
            countdown(args.delay, "ページ送りボタンの中央にマウスを置いてください。")
            point = gui.position()
            x, y = point.x, point.y
        else:
            x, y = args.x, args.y
        operation = f"({x}, {y}) をクリック"
    else:
        if args.x is not None or args.y is not None:
            raise ValueError("矢印キー方式では --x / --y は使えません。")
        operation = f"{args.browser} に右矢印キーを送る"

    print("\nPhase 2 の設定確認")
    print(f"  Shottr の保存先: {source_dir}")
    print("  ※このフォルダが Shottr の設定画面にある保存先と同じことを確認してください。")
    print(f"  連番画像の保存先: {output_root} 内の新しい run フォルダ")
    print(f"  撮影: {args.count} 枚（ページ送りは {args.count - 1} 回）")
    print(f"  ページ送り: {operation} / {args.browser} を前面に出して {args.focus_wait:g} 秒後に操作")
    print(f"  ページ送り後の待機: {args.wait:g} 秒")
    print("  1枚目は範囲を手で選択し、以降は同じ範囲を撮影します。")
    input("開始する場合は Enter、取りやめる場合は Ctrl+C: ")
    output_dir = new_run_folder(output_root)
    destinations = [output_dir / f"page_{number:04d}.png" for number in range(1, args.count + 1)]
    print(f"  今回の保存先: {output_dir}")
    countdown(args.delay, "対象のブラウザページを前面に表示してください。")

    previous_digest = None
    for index, destination in enumerate(destinations, start=1):
        check_stop(gui)
        before = image_files(source_dir)
        url = AREA_URL if index == 1 else REPEAT_URL
        print(f"[{index}/{args.count}] Shottr で撮影します。", flush=True)
        subprocess.run(["open", url], check=True)
        source = wait_for_shottr_file(source_dir, before, args.timeout, gui)
        dimensions, digest = save_png_without_overwrite(source, destination)
        print(f"  保存: {destination.name} ({dimensions[0]}×{dimensions[1]} px)")
        if previous_digest == digest:
            raise RuntimeError(
                "直前の画像と画素が同じため停止しました。"
                "クリック位置、ブラウザのフォーカス、待機時間を確認してください"
            )
        previous_digest = digest

        if index < args.count:
            subprocess.run(["open", "-a", args.browser], check=True)
            pause_with_stop(args.focus_wait, gui)
            if args.mode == "click":
                gui.click(x=x, y=y)
                # Leave the control so its hover tooltip is not in the next capture.
                park_y = y - 160 if y >= 160 else y + 160
                gui.moveTo(x=x, y=park_y)
            else:
                gui.press("right")
            print(f"  ページ送り操作を送信しました。{args.wait:g} 秒待機します。")
            pause_with_stop(args.wait, gui)

    print(f"{args.count}枚の撮影が完了しました。連番画像の保存先: {output_dir}")
    try:
        subprocess.run(["open", str(output_dir)], check=True)
    except (OSError, subprocess.CalledProcessError):
        print("Finder を自動で開けませんでした。上記の保存先を開いて確認してください。")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 2/3: 見開き画像を連続撮影します。初期値は3枚です。")
    parser.add_argument("--shottr-dir", type=Path, help="Shottr の既定保存フォルダ。省略時はフォルダ選択")
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="実行別の run フォルダを作る親フォルダ（初期値: このスクリプトの captures）"
    )
    parser.add_argument("--mode", choices=("click", "key"), default="click")
    parser.add_argument(
        "--count", type=int, default=DEFAULT_COUNT,
        help="撮影枚数（1～9999、初期値: 3）"
    )
    parser.add_argument("--x", type=int, help="ページ送りボタンの X 座標")
    parser.add_argument("--y", type=int, help="ページ送りボタンの Y 座標")
    parser.add_argument("--browser", default="Google Chrome", help="ページ送り前に前面に出すブラウザ")
    parser.add_argument("--delay", type=int, default=5, help="開始前の秒数（初期値: 5）")
    parser.add_argument(
        "--focus-wait", type=float, default=1.0,
        help="Shottr 保存後にブラウザを前面に出してから操作するまでの秒数（初期値: 1）"
    )
    parser.add_argument("--wait", type=float, default=2.0, help="ページ送り後の待機秒数（初期値: 2）")
    parser.add_argument("--timeout", type=float, default=60.0, help="1枚の保存待ち秒数（初期値: 60）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("このツールは macOS 専用です。")
    if not 1 <= args.count <= 9999:
        parser.error("--count は1～9999にしてください。")
    if args.delay < 0 or not math.isfinite(args.wait) or args.wait < 0:
        parser.error("--delay と --wait は0以上にしてください。")
    if not math.isfinite(args.focus_wait) or args.focus_wait < 0:
        parser.error("--focus-wait は0以上にしてください。")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout は0より大きくしてください。")
    try:
        run(args)
    except StopRequested as exc:
        print(f"\n{exc}。保存済み画像はそのまま残します。", file=sys.stderr)
        return 130
    except (KeyboardInterrupt, EOFError):
        print("\n撮影を中止しました。保存済み画像はそのまま残します。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"エラー: {exc}。保存済み画像はそのまま残します。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
