#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kindle自動スクリーンキャプチャツール（ウィンドウID方式）
Amazon Kindle.app の前面ウィンドウだけをキャプチャして PDF 化します。
背景が写らないよう `screencapture -l <windowId> -o` を使用します。

【主な機能】
- KindleウィンドウのAXWindowNumberを取得して影なしでキャプチャ
- ページ送り（右矢印キー）を自動でシミュレート
- 任意の余白トリミング（--crop L,T,R,B）
- フォールバックとして矩形領域キャプチャも可能（自動検出失敗時は対話入力）

【前提】
- macOS（screencapture, osascript が使えること）
- システム設定 > プライバシーとセキュリティ >
  ・「画面収録」にこのターミナル/エディタ（Python）が許可されている
  ・「アクセシビリティ」にこのターミナル/エディタ（Python）が許可されている

【使い方（例）】
# 10ページを2秒間隔でキャプチャ
python3 kindle_capture_auto.py -p 10 -d 2 -o my_book.pdf

# 余白トリミング（左20, 上80, 右20, 下60をカット）
python3 kindle_capture_auto.py -p 20 --crop 20,80,20,60 -o trimmed.pdf

# 無制限（Ctrl+Cで停止）
python3 kindle_capture_auto.py -o all.pdf
"""

import os
import sys
import time
import subprocess
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Installing required package Pillow ...")
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "--user"])
    from PIL import Image


# ---------- AppleScript / macOS helpers ----------

def run_osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def open_kindle_app():
    """Kindleアプリを起動（存在すれば前面化）"""
    subprocess.run(["open", "-a", "Amazon Kindle"])
    time.sleep(1.5)

def activate_kindle():
    """Kindleを最前面に"""
    script = '''
    try
        tell application "Amazon Kindle" to activate
    on error
        try
            tell application "Kindle" to activate
        end try
    end try
    '''
    run_osascript(script)

def get_kindle_window_id():
    """前面KindleウィンドウのAXWindowNumberを取得（なければ window id を返す）"""
    script = '''
    tell application "System Events"
        repeat with p in {"Amazon Kindle","Kindle"}
            if exists process (p as text) then
                tell process (p as text)
                    if exists front window then
                        try
                            return value of attribute "AXWindowNumber" of front window
                        on error
                            try
                                return id of front window
                            on error
                                return ""
                            end try
                        end try
                    end if
                end tell
            end if
        end repeat
    end tell
    '''
    res = run_osascript(script)
    out = res.stdout.strip()
    if res.returncode == 0 and out:
        try:
            return int(out)
        except ValueError:
            return None
    return None

def simulate_page_turn():
    """右矢印キーでページ送り"""
    script = '''
    tell application "System Events"
        key code 124
    end tell
    '''
    run_osascript(script)


# ---------- Capture helpers ----------

def capture_window_by_id(window_id: int):
    """ウィンドウIDでキャプチャ（影なし -o, 無音 -x）。PIL.Image を返す。"""
    output_file = f"/tmp/kindle_capture_{int(time.time()*1000)}.png"
    cmd = ["screencapture", "-x", "-o", "-l", str(window_id), output_file]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(output_file):
        # 画像を完全にメモリへ読んでからファイル削除
        with Image.open(output_file) as im:
            img = im.convert("RGB")
        os.remove(output_file)
        return img
    else:
        err = (result.stderr or "").strip()
        if err:
            print(f"Failed to capture window: {err}")
        return None

def capture_screen_area(x, y, width, height):
    """矩形領域をキャプチャ（フォールバック用）"""
    output_file = f"/tmp/kindle_capture_{int(time.time()*1000)}.png"
    cmd = ["screencapture", "-x", "-R", f"{x},{y},{width},{height}", output_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(output_file):
        with Image.open(output_file) as im:
            img = im.convert("RGB")
        os.remove(output_file)
        return img
    else:
        print(f"Failed to capture region: {result.stderr}")
        return None


# ---------- Main flow ----------

def parse_crop(crop_str: str):
    """--crop L,T,R,B を (left, top, right, bottom) のピクセルで返す"""
    try:
        l, t, r, b = [int(v.strip()) for v in crop_str.split(",")]
        if min(l, t, r, b) < 0:
            raise ValueError
        return (l, t, r, b)
    except Exception:
        raise ValueError("--crop は 'L,T,R,B' の整数で指定してください（例: 20,80,20,60）")

def crop_image_box(img: Image.Image, crop: tuple[int,int,int,int]):
    """余白トリミング: 画像端からのマージンを削る"""
    w, h = img.size
    l, t, r, b = crop
    box = (l, t, w - r, h - b)
    # ボックスの妥当性チェック
    if box[0] < 0 or box[1] < 0 or box[2] <= box[0] or box[3] <= box[1]:
        return img  # 無効ならそのまま返す
    return img.crop(box)

def get_kindle_window_bounds():
    """Kindleウィンドウの位置とサイズを取得（フォールバック表示用）"""
    for process_name in ["Amazon Kindle", "Kindle"]:
        script = f'''
        tell application "System Events"
            if exists process "{process_name}" then
                tell process "{process_name}"
                    set frontWindow to front window
                    set windowPosition to position of frontWindow
                    set windowSize to size of frontWindow
                    return (item 1 of windowPosition as string) & "," & (item 2 of windowPosition as string) & "," & (item 1 of windowSize as string) & "," & (item 2 of windowSize as string)
                end tell
            end if
        end tell
        '''
        res = run_osascript(script)
        if res.returncode == 0 and res.stdout.strip():
            try:
                x, y, w, h = [int(v) for v in res.stdout.strip().split(",")]
                return x, y, w, h
            except Exception:
                pass
    return None

def capture_kindle_book(output_pdf="kindle_book.pdf", max_pages=None, delay=2.0, crop=None, open_after=True):
    print("Kindle to PDF Converter (Window ID mode)")
    print("=" * 52)

    # 1) Kindle起動＆前面化
    open_kindle_app()
    activate_kindle()
    time.sleep(0.8)

    # 2) ウィンドウID取得
    win_id = get_kindle_window_id()

    # 3) フォールバック準備（必要なら領域入力）
    region = None
    if not win_id:
        print("⚠️ KindleのウィンドウIDを取得できませんでした。アクセシビリティ権限/画面収録権限を確認してください。")
        print("   → フォールバックとして矩形領域キャプチャに切り替えます。")
        bounds = get_kindle_window_bounds()
        if bounds:
            x, y, w, h = bounds
            print(f"検出: x={x}, y={y}, width={w}, height={h}")
        else:
            print("Kindleウィンドウの自動検出に失敗しました。")
            x, y, w, h = 100, 100, 800, 1000

        print("\n手動でキャプチャ領域を入力（Enterで既定値）:")
        try:
            xin = input(f"X [{x}]: ").strip()
            yin = input(f"Y [{y}]: ").strip()
            win = input(f"Width [{w}]: ").strip()
            hin = input(f"Height [{h}]: ").strip()
            x = int(xin) if xin else x
            y = int(yin) if yin else y
            w = int(win) if win else w
            h = int(hin) if hin else h
        except KeyboardInterrupt:
            print("\n中断しました。")
            return
        except Exception:
            print("入力値が不正のため既定値を使用します。")
        region = (x, y, w, h)
    else:
        print(f"✅ Kindle window id: {win_id}")

    print(f"\nPages to capture: {max_pages if max_pages else 'Until stopped (Ctrl+C)'}")
    print(f"Delay between pages: {delay} sec")
    if crop:
        print(f"Crop margins (L,T,R,B): {crop}")
    print("\nKindleをキャプチャしたい最初のページに合わせ、必要ならツールバーを隠してください。")
    input("準備できたら Enter ▶︎ 開始します…")

    captured_images = []
    page_num = 0

    print("\nCapturing…（停止は Ctrl+C）")
    try:
        while True:
            if max_pages and page_num >= max_pages:
                break

            page_num += 1
            print(f"  - Page {page_num} … ", end="", flush=True)

            if win_id:
                img = capture_window_by_id(win_id)
                # まれにIDが変わる/失敗時のリトライ（1回だけ再取得）
                if img is None:
                    time.sleep(0.3)
                    win_id = get_kindle_window_id()
                    if win_id:
                        img = capture_window_by_id(win_id)
            else:
                x, y, w, h = region
                img = capture_screen_area(x, y, w, h)

            if img:
                if crop:
                    img = crop_image_box(img, crop)
                captured_images.append(img)
                print("OK")
            else:
                print("FAILED")

            # 次のページへ
            if not (max_pages and page_num >= max_pages):
                simulate_page_turn()
                time.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n手動停止。取得ページ数: {len(captured_images)}")

    # 4) PDF保存
    if not captured_images:
        print("❌ 1ページも取得できませんでした。")
        return

    print(f"\nPDFへ書き出し: {output_pdf}")
    output_pdf = str(Path(output_pdf).expanduser().resolve())

    if len(captured_images) == 1:
        captured_images[0].save(output_pdf, resolution=150.0)
    else:
        captured_images[0].save(
            output_pdf,
            save_all=True,
            append_images=captured_images[1:],
            resolution=150.0
        )

    print("✅ 完了!")
    print(f"   ファイル: {output_pdf}")
    print(f"   ページ数: {len(captured_images)}")
    try:
        size_mb = os.path.getsize(output_pdf) / (1024 * 1024)
        print(f"   サイズ: {size_mb:.2f} MB")
    except Exception:
        pass

    if open_after:
        subprocess.run(["open", output_pdf])


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Kindle Auto Screen Capture to PDF (window-id mode)")
    parser.add_argument('-o', '--output', default='kindle_book.pdf', help='出力PDFファイル名')
    parser.add_argument('-p', '--pages', type=int, default=None, help='キャプチャページ数（未指定=無制限）')
    parser.add_argument('-d', '--delay', type=float, default=2.0, help='ページ間待機秒数（描画待ち）')
    parser.add_argument('--crop', type=str, default=None, help='余白トリミング: L,T,R,B（例: 20,80,20,60）')
    parser.add_argument('--no-open', action='store_true', help='完了後にPDFを開かない')

    args = parser.parse_args()

    crop = parse_crop(args.crop) if args.crop else None
    capture_kindle_book(
        output_pdf=args.output,
        max_pages=args.pages,
        delay=args.delay,
        crop=crop,
        open_after=not args.no_open
    )


if __name__ == '__main__':
    main()