"""
Playwright Screenshot Capture Module

【使用方法】
from playwright_capture import PlaywrightCapture

# インスタンス作成
capture = PlaywrightCapture(headless=True)

# スクリーンショット撮影
screenshot_path = capture.capture_screenshot(
    url="https://example.com",
    output_path="./screenshots/example.png",
    wait_time=2000
)

# 複数ページのスクリーンショット撮影
screenshots = capture.capture_multiple(
    urls=["https://example.com", "https://google.com"],
    output_dir="./screenshots"
)

【処理内容】
1. Playwrightを使用してブラウザを起動
2. 指定されたURLにアクセス
3. ページの読み込みを待機
4. スクリーンショットを撮影して保存
5. ファイルパスを返却
"""

from playwright.sync_api import sync_playwright, Page, Browser
from pathlib import Path
from typing import Optional, List, Dict
import time
from datetime import datetime


class PlaywrightCapture:
    """
    Playwrightを使用してWebページのスクリーンショットを撮影するクラス
    """

    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        """
        初期化

        Args:
            headless: ヘッドレスモードで実行するか
            browser_type: ブラウザタイプ ("chromium", "firefox", "webkit")
        """
        self.headless = headless
        self.browser_type = browser_type
        self.playwright = None
        self.browser: Optional[Browser] = None

    def __enter__(self):
        """コンテキストマネージャー開始"""
        self.playwright = sync_playwright().start()

        if self.browser_type == "chromium":
            self.browser = self.playwright.chromium.launch(headless=self.headless)
        elif self.browser_type == "firefox":
            self.browser = self.playwright.firefox.launch(headless=self.headless)
        elif self.browser_type == "webkit":
            self.browser = self.playwright.webkit.launch(headless=self.headless)
        else:
            raise ValueError(f"Unknown browser type: {self.browser_type}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def capture_screenshot(
        self,
        url: str,
        output_path: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        full_page: bool = True
    ) -> str:
        """
        指定されたURLのスクリーンショットを撮影

        Input:
            url: アクセスするURL
            output_path: 保存先パス
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ {"width": 1280, "height": 720}
            full_page: フルページスクリーンショットを撮るか

        Output:
            str: 保存されたスクリーンショットのファイルパス
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

        # 出力ディレクトリを作成
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # ページを作成
        context = self.browser.new_context(
            viewport=viewport_size or {"width": 1280, "height": 720}
        )
        page = context.new_page()

        try:
            # URLにアクセス
            page.goto(url, wait_until="networkidle", timeout=30000)

            # 追加の待機時間
            if wait_time > 0:
                page.wait_for_timeout(wait_time)

            # スクリーンショット撮影
            page.screenshot(path=str(output_path), full_page=full_page)

            return str(output_path_obj.absolute())

        finally:
            context.close()

    def capture_multiple(
        self,
        urls: List[str],
        output_dir: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        full_page: bool = True,
        prefix: str = "screenshot"
    ) -> List[Dict[str, str]]:
        """
        複数のURLのスクリーンショットを撮影

        Input:
            urls: アクセスするURLのリスト
            output_dir: 保存先ディレクトリ
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ
            full_page: フルページスクリーンショットを撮るか
            prefix: ファイル名のプレフィックス

        Output:
            List[Dict[str, str]]: URLと保存先パスの辞書のリスト
                [{"url": "...", "path": "...", "status": "success|error", "error": "..."}]
        """
        results = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, url in enumerate(urls):
            output_filename = f"{prefix}_{timestamp}_{idx}.png"
            output_path = Path(output_dir) / output_filename

            try:
                saved_path = self.capture_screenshot(
                    url=url,
                    output_path=str(output_path),
                    wait_time=wait_time,
                    viewport_size=viewport_size,
                    full_page=full_page
                )

                results.append({
                    "url": url,
                    "path": saved_path,
                    "status": "success",
                    "error": None
                })

            except Exception as e:
                results.append({
                    "url": url,
                    "path": None,
                    "status": "error",
                    "error": str(e)
                })

        return results

    def capture_with_interaction(
        self,
        url: str,
        output_path: str,
        interactions: List[Dict],
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        full_page: bool = True
    ) -> str:
        """
        ページ操作後にスクリーンショットを撮影

        Input:
            url: アクセスするURL
            output_path: 保存先パス
            interactions: 操作のリスト
                [
                    {"type": "click", "selector": "#button"},
                    {"type": "fill", "selector": "#input", "value": "text"},
                    {"type": "wait", "time": 1000}
                ]
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ
            full_page: フルページスクリーンショットを撮るか

        Output:
            str: 保存されたスクリーンショットのファイルパス
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

        # 出力ディレクトリを作成
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # ページを作成
        context = self.browser.new_context(
            viewport=viewport_size or {"width": 1280, "height": 720}
        )
        page = context.new_page()

        try:
            # URLにアクセス
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_time)

            # インタラクション実行
            for interaction in interactions:
                action_type = interaction.get("type")

                if action_type == "click":
                    page.click(interaction["selector"])

                elif action_type == "fill":
                    page.fill(interaction["selector"], interaction["value"])

                elif action_type == "wait":
                    page.wait_for_timeout(interaction["time"])

                elif action_type == "select":
                    page.select_option(interaction["selector"], interaction["value"])

                elif action_type == "hover":
                    page.hover(interaction["selector"])

            # 最終待機
            page.wait_for_timeout(wait_time)

            # スクリーンショット撮影
            page.screenshot(path=str(output_path), full_page=full_page)

            return str(output_path_obj.absolute())

        finally:
            context.close()


def quick_capture(url: str, output_path: str, **kwargs) -> str:
    """
    クイックスクリーンショット撮影（コンテキストマネージャー不要）

    Input:
        url: アクセスするURL
        output_path: 保存先パス
        **kwargs: capture_screenshotに渡す追加引数

    Output:
        str: 保存されたスクリーンショットのファイルパス
    """
    with PlaywrightCapture() as capture:
        return capture.capture_screenshot(url, output_path, **kwargs)
