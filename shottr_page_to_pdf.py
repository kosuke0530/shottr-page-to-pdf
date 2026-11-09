"""Command-line entry point for Shottr capture and PDF creation."""

from __future__ import annotations

import sys


USAGE = """使い方: .venv/bin/python shottr_page_to_pdf.py <コマンド> [オプション]

コマンド:
  check-capture   Shottr の撮影を1回試す
  check-advance   ブラウザのページ送りを1回試す
  capture         連続撮影する（初期値は3枚）
  pdf             連番PNGからPDFを作る

各コマンドの詳細: .venv/bin/python shottr_page_to_pdf.py <コマンド> --help
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    command, *options = args
    if command == "check-capture":
        from shottr_check import main as shottr_check_main

        return shottr_check_main(["capture", *options])
    if command == "check-advance":
        from shottr_check import main as shottr_check_main

        return shottr_check_main(["advance", *options])
    if command == "capture":
        from capture_pages import main as capture_main

        return capture_main(options)
    if command == "pdf":
        from make_pdf import main as pdf_main

        return pdf_main(options)

    print(f"不明なコマンド: {command}\n\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
