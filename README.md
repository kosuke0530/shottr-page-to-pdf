# shottr-page-to-pdf

macOS で Shottr の範囲撮影を繰り返し、ブラウザのページを GUI 操作で送り、連番 PNG からスクロールできる PDF を作るコマンドラインツールです。保存・複製を許可された資料だけに使ってください。アクセス制御やコピー制限を回避する機能はありません。

操作テスト、連続撮影、PDF 作成を実装しています。GUI は未実装です。

## 準備

- macOS、Python 3、[Shottr](https://shottr.cc/) 1.8 以降が必要です。Shottr を起動し、**Settings で保存先フォルダを確認**してください。
- **システム設定 → プライバシーとセキュリティ**で、Shottr に「画面収録とシステムオーディオ」、使用するターミナルに「アクセシビリティ」の権限を与えてください。変更後はアプリの再起動が必要な場合があります。
- 50 ページを超える PDF を作る場合は、`brew install poppler` で `pdfunite` を導入してください。

```bash
git clone https://github.com/kosuke0530/shottr-page-to-pdf.git
cd shottr-page-to-pdf
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

仮想環境とライブラリの導入は通常、最初の1回だけです。すでに `.venv` がある場合は作り直す必要はありません。

## まず3枚撮影する

ブラウザで撮影開始ページを開いてから、次を実行します。

```bash
.venv/bin/python shottr_page_to_pdf.py capture --focus-wait 2 --wait 4
```

1. フォルダ選択画面で、**Shottr の Settings に表示される保存先と同じフォルダ**を選びます。ここは Shottr が自動保存する元画像の置き場です。
2. ページ送りボタンの中央へマウスを置き、表示された設定を確認して Enter を押します。
3. 5 秒以内にブラウザを前面に出し、Shottr の範囲選択画面で資料の範囲をドラッグします。初回の範囲選択は 60 秒以内に終えてください。
4. 3 枚目の撮影が終わるまで、画面やマウスを操作せず待ちます。完了後、Finder で連番画像のフォルダを開きます。

画像は `captures/run_0001/page_0001.png` のように**撮影順に1から**保存されます。次の実行では `run_0002` を新規作成します。番号は資料に印刷されたページ番号ではありません。Shottr が保存した元画像も残ります。

Shottr の保存先を毎回選びたくない場合は `--shottr-dir "/Shottrの保存先"` を指定できます。必ず Shottr の設定と一致させてください。`--output-dir "/連番画像の親フォルダ"` で連番画像の保存先を変更できます。

## 枚数を指定して撮影する

3枚の画像の範囲と順番を確認したら、撮影開始ページに戻して実行します。`--count` は撮影枚数で、ページ送りはその1回少ない回数です。例は264枚です。

```bash
.venv/bin/python shottr_page_to_pdf.py capture --count 264 --focus-wait 2 --wait 4
```

`--mode key` を付けるとクリックの代わりに右矢印キーで送ります。クリック位置を固定する場合は `--x 1200 --y 700` のように両方指定します。`--browser` で前面に出すブラウザ名、`--wait` でページ送り後の待機秒数を変更できます。全オプションは `capture --help` で確認できます。

撮影中は **Ctrl+C** または PyAutoGUI のフェイルセーフ（主画面の四隅にマウスを移動）で停止できます。保存済み画像は残ります。直前と同じ画素の画像を撮った場合は次の撮影前に停止するので、クリック位置、ブラウザのフォーカス、待機時間を確認してください。停止した実行を自動で再開する機能はありません。

## PDF にする

撮影完了後、実際に作られた `run_XXXX` フォルダを指定します。画像をファイル名の昇順で並べ、見開き画像1枚を PDF の1ページにします。

```bash
.venv/bin/python shottr_page_to_pdf.py pdf captures/run_0001
```

初期値は画質優先で、出力先は `output/pdf/run_0001_quality.pdf` です。容量優先、左右分割、出力先指定もできます。

```bash
.venv/bin/python shottr_page_to_pdf.py pdf captures/run_0001 --mode small
.venv/bin/python shottr_page_to_pdf.py pdf captures/run_0001 --split
.venv/bin/python shottr_page_to_pdf.py pdf captures/run_0001 --split --split-order right-left
.venv/bin/python shottr_page_to_pdf.py pdf captures/run_0001 --output output/pdf/my-document.pdf
```

容量優先モードは JPEG 品質82で一時画像を作ります。左右分割時は元画像1枚が PDF の2ページになり、初期値は左→右です。完成後にページ数とファイルサイズを表示します。PNG の番号に抜けがある場合は停止します。既存 PDF は上書きせず、元画像も削除しません。大量画像は50ページずつ作業用 PDF にして結合するため、出力と一時ファイル用のディスク容量が必要です。

## 操作を個別に試す

連続撮影の前に、Shottr の撮影とページ送りを別々に確認できます。

```bash
.venv/bin/python shottr_page_to_pdf.py check-capture
.venv/bin/python shottr_page_to_pdf.py check-capture --repeat
.venv/bin/python shottr_page_to_pdf.py check-advance --mode click
.venv/bin/python shottr_page_to_pdf.py check-advance --mode key --wait 2
```

`check-capture` は最初の範囲選択、`--repeat` は Shottr の「Repeat Area Screenshot」を試します。Shottr の既定フォルダに元の名前で保存されます。現在の **⌘⇧2** ショートカットを試す場合は `check-capture --shortcut` を使用し、撮影後は Shottr で手動保存してください。Repeat Area Screenshot のキーを設定する場合は **Shottr → Settings → Hotkeys** を開きます。このツールの `--repeat` にキー設定は不要です。

`check-advance --mode click` では、5 秒以内にマウスをページ送りボタンへ置いて座標を取得します。Enter 後、再び5秒以内にブラウザを前面に出します。右矢印キー方式は、ブラウザ側がそのキーに対応している場合だけ使えます。

通常は `shottr_page_to_pdf.py` から起動します。内部のファイルは役割別です。

- `shottr_check.py`: 撮影とページ送りを個別に確認
- `capture_pages.py`: 3枚の試し撮りと、`--count` で指定する連続撮影
- `make_pdf.py`: 連番 PNG を PDF に変換

開発時の Phase 2（3枚撮影）と Phase 3（枚数指定）は同じ撮影処理を使うため、`capture_pages.py` にまとまっています。

## テストと保存対象

```bash
.venv/bin/python -m unittest discover -s tests -q
```

Git に入れるのはプログラム、テスト、説明書です。`.venv/`、`captures/`、`output/`、`tmp/` は Git の管理対象から除外しています。撮影画像や作成した PDF をリポジトリへ公開しないようにしています。
