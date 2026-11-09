"""Combine numbered screenshots into a scrollable PDF."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import img2pdf
from PIL import Image
import pikepdf


ROOT = Path(__file__).resolve().parent
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
TEMP_PDF_DIR = ROOT / "tmp" / "pdfs"
PAGE_NAME = re.compile(r"page_(\d{4,})\.png\Z")
CHUNK_SIZE = 50


def numbered_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise ValueError(f"画像フォルダが見つかりません: {folder}")
    found: list[tuple[int, Path]] = []
    for path in folder.iterdir():
        match = PAGE_NAME.fullmatch(path.name)
        if path.is_file() and match:
            found.append((int(match.group(1)), path))
    found.sort(key=lambda item: item[0])
    if not found:
        raise ValueError("page_0001.png 形式の画像がありません")
    numbers = [number for number, _ in found]
    expected = list(range(1, len(found) + 1))
    if numbers != expected:
        raise ValueError("画像番号が1から連続していません。抜け・重複を確認してください")
    return [path for _, path in found]


def jpeg_ready(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white = Image.new("RGB", rgba.size, "white")
        white.paste(rgba, mask=rgba.getchannel("A"))
        return white
    return image.convert("RGB")


def prepared_images(
    sources: list[Path], workspace: Path, mode: str, split: bool, split_order: str
) -> list[Path]:
    if mode == "quality" and not split:
        return sources

    prepared: list[Path] = []
    for index, source in enumerate(sources, start=1):
        with Image.open(source) as original:
            original.load()
            if split:
                midpoint = original.width // 2
                if midpoint < 1:
                    raise ValueError(f"左右に分割できない幅の画像です: {source.name}")
                halves = {
                    "left": original.crop((0, 0, midpoint, original.height)),
                    "right": original.crop((midpoint, 0, original.width, original.height)),
                }
                order = ("left", "right") if split_order == "left-right" else ("right", "left")
            else:
                halves = {"full": original}
                order = ("full",)

            for side in order:
                image = halves[side]
                suffix = ".png" if mode == "quality" else ".jpg"
                target = workspace / f"{index:04d}_{side}{suffix}"
                if mode == "quality":
                    image.save(target, format="PNG")
                else:
                    rgb = jpeg_ready(image)
                    rgb.save(target, format="JPEG", quality=82, subsampling=0, optimize=True)
                    if rgb is not image:
                        rgb.close()
                prepared.append(target)
            for side, image in halves.items():
                if image is not original:
                    image.close()
        print(f"  画像準備: {index}/{len(sources)}", flush=True)
    return prepared


def create_pdf(
    input_dir: Path, output: Path, mode: str = "quality", split: bool = False,
    split_order: str = "left-right", cover: Path | None = None
) -> tuple[int, int]:
    input_dir = input_dir.expanduser().resolve()
    output = output.expanduser().resolve()
    sources = numbered_images(input_dir)
    if cover is not None:
        cover = cover.expanduser().resolve()
        if not cover.is_file():
            raise ValueError(f"表紙画像が見つかりません: {cover}")
        if cover in sources:
            raise ValueError("表紙画像には連番画像とは別のファイルを指定してください")
        with Image.open(cover) as image:
            if image.format not in ("PNG", "JPEG"):
                raise ValueError("表紙画像は PNG または JPEG にしてください")
            image.verify()
    if output.exists():
        raise FileExistsError(f"既存のPDFは上書きしません: {output}")
    page_count = len(sources) * (2 if split else 1) + (cover is not None)
    if page_count > CHUNK_SIZE and shutil.which("pdfunite") is None:
        raise RuntimeError("大量画像の結合には Poppler の pdfunite が必要です: brew install poppler")
    output.parent.mkdir(parents=True, exist_ok=True)

    TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)
    temp_pdf: Path | None = None
    with tempfile.TemporaryDirectory(prefix="shottr-pdf-", dir=TEMP_PDF_DIR) as temp_dir:
        workspace = Path(temp_dir)
        images = prepared_images(sources, workspace, mode, split, split_order)
        if cover is not None:
            cover_workspace = workspace / "cover"
            cover_workspace.mkdir()
            cover_image = prepared_images([cover], cover_workspace, mode, False, split_order)
            images = cover_image + images
        try:
            fd, name = tempfile.mkstemp(
                prefix=f".{output.stem}-", suffix=".tmp", dir=output.parent
            )
            os.close(fd)
            temp_pdf = Path(name)
            print(f"PDFに結合中: {len(images)} ページ", flush=True)
            if len(images) <= CHUNK_SIZE:
                with temp_pdf.open("wb") as stream:
                    img2pdf.convert(
                        images, outputstream=stream,
                        layout_fun=img2pdf.get_fixed_dpi_layout_fun((144, 144)),
                        engine=img2pdf.Engine.pikepdf,
                    )
            else:
                chunks = []
                for start in range(0, len(images), CHUNK_SIZE):
                    chunk = workspace / f"chunk_{start // CHUNK_SIZE:04d}.pdf"
                    with chunk.open("wb") as stream:
                        img2pdf.convert(
                            images[start:start + CHUNK_SIZE], outputstream=stream,
                            layout_fun=img2pdf.get_fixed_dpi_layout_fun((144, 144)),
                            engine=img2pdf.Engine.pikepdf,
                        )
                    chunks.append(chunk)
                    print(f"  結合準備: {min(start + CHUNK_SIZE, len(images))}/{len(images)} ページ")
                temp_pdf.unlink()
                subprocess.run(["pdfunite", *(str(path) for path in chunks), str(temp_pdf)], check=True)
            with pikepdf.Pdf.open(temp_pdf) as pdf:
                if len(pdf.pages) != len(images):
                    raise RuntimeError("PDFのページ数が画像数と一致しません")
            os.link(temp_pdf, output)  # Existing destination causes FileExistsError.
        finally:
            if temp_pdf is not None:
                temp_pdf.unlink(missing_ok=True)

    return len(images), output.stat().st_size


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="連番PNGを順番にPDFへ結合します。")
    parser.add_argument("input_dir", type=Path, help="page_0001.png などがある run フォルダ")
    parser.add_argument("--output", type=Path, help="PDF出力先。省略時は output/pdf 内")
    parser.add_argument("--cover", type=Path, help="先頭に1ページ追加する表紙画像（PNG または JPEG）")
    parser.add_argument(
        "--mode", choices=("quality", "small"), default="quality",
        help="quality=画質優先、small=容量優先（JPEG品質82）"
    )
    parser.add_argument("--split", action="store_true", help="見開き画像を左右に分割")
    parser.add_argument(
        "--split-order", choices=("left-right", "right-left"), default="left-right",
        help="分割時のPDFページ順（初期値: 左→右）"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    input_dir = args.input_dir.expanduser().resolve()
    suffix = ("_split" if args.split else "") + ("_cover" if args.cover else "")
    output = args.output or DEFAULT_PDF_DIR / f"{input_dir.name}_{args.mode}{suffix}.pdf"
    print(f"画像フォルダ: {input_dir}")
    print(f"PDF出力先: {output.expanduser().resolve()}")
    print(f"モード: {args.mode} / 左右分割: {'あり' if args.split else 'なし'}")
    if args.cover:
        print(f"表紙画像: {args.cover.expanduser().resolve()}")
    try:
        pages, size = create_pdf(
            input_dir, output, args.mode, args.split, args.split_order, cover=args.cover
        )
    except KeyboardInterrupt:
        print("\n中止しました。元画像は残しています。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"エラー: {exc}。元画像は残しています。", file=sys.stderr)
        return 1
    print(f"完了: {pages} ページ / {size / (1024 * 1024):.2f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
