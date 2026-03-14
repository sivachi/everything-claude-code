"""
Playwright DOM and XPath Handler Module

【使用方法】
from dom_xpath_handler import DomXPathHandler

# インスタンス作成
handler = DomXPathHandler(headless=True)

# DOM取得とXPath処理
with handler:
    # ページのDOM全体を取得
    dom_content = handler.get_page_dom(url="https://example.com")

    # XPathで要素を検索
    elements = handler.find_elements_by_xpath(
        url="https://example.com",
        xpath="//h1"
    )

    # XPathで要素のテキストを取得
    texts = handler.get_text_by_xpath(
        url="https://example.com",
        xpath="//p[@class='content']"
    )

    # XPathで要素の属性を取得
    attributes = handler.get_attribute_by_xpath(
        url="https://example.com",
        xpath="//a[@href]",
        attribute="href"
    )

【処理内容】
1. Playwrightを使用してブラウザを起動
2. 指定されたURLにアクセス
3. ページのDOMを取得
4. XPathを使用して要素を検索・取得
5. 要素のテキスト、属性、HTML等を取得して返却
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import Optional, List, Dict, Any
from pathlib import Path
import json


class DomXPathHandler:
    """
    PlaywrightでDOM取得とXPath処理を行うクラス
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

    def get_page_dom(
        self,
        url: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        output_format: str = "html"
    ) -> str:
        """
        指定されたURLのページDOM全体を取得

        Input:
            url: アクセスするURL
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ {"width": 1280, "height": 720}
            output_format: 出力フォーマット ("html", "text")

        Output:
            str: ページのDOM内容（HTML or プレーンテキスト）
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

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

            # DOM取得
            if output_format == "html":
                content = page.content()
            elif output_format == "text":
                content = page.inner_text("body")
            else:
                raise ValueError(f"Unknown output format: {output_format}")

            return content

        finally:
            context.close()

    def find_elements_by_xpath(
        self,
        url: str,
        xpath: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        XPathで要素を検索し、要素の情報を取得

        Input:
            url: アクセスするURL
            xpath: XPath式
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            List[Dict[str, Any]]: 要素情報のリスト
                [{"text": "...", "html": "...", "tag": "...", "attributes": {...}}]
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

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

            # XPathで要素を取得
            elements = page.locator(f"xpath={xpath}")
            count = elements.count()

            results = []
            for i in range(count):
                element = elements.nth(i)

                # 要素の情報を取得
                element_info = {
                    "text": element.inner_text() if element.is_visible() else "",
                    "html": element.inner_html(),
                    "tag": element.evaluate("el => el.tagName.toLowerCase()"),
                    "attributes": element.evaluate(
                        """el => {
                            const attrs = {};
                            for (let attr of el.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            return attrs;
                        }"""
                    ),
                    "visible": element.is_visible(),
                    "enabled": element.is_enabled() if element.evaluate("el => 'disabled' in el") else None
                }
                results.append(element_info)

            return results

        finally:
            context.close()

    def get_text_by_xpath(
        self,
        url: str,
        xpath: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> List[str]:
        """
        XPathで要素のテキストを取得

        Input:
            url: アクセスするURL
            xpath: XPath式
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            List[str]: テキストのリスト
        """
        elements = self.find_elements_by_xpath(url, xpath, wait_time, viewport_size)
        return [elem["text"] for elem in elements]

    def get_attribute_by_xpath(
        self,
        url: str,
        xpath: str,
        attribute: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> List[Optional[str]]:
        """
        XPathで要素の属性を取得

        Input:
            url: アクセスするURL
            xpath: XPath式
            attribute: 取得する属性名
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            List[Optional[str]]: 属性値のリスト
        """
        elements = self.find_elements_by_xpath(url, xpath, wait_time, viewport_size)
        return [elem["attributes"].get(attribute) for elem in elements]

    def extract_dom_structure(
        self,
        url: str,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        ページのDOM構造を抽出

        Input:
            url: アクセスするURL
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ
            max_depth: 最大深度

        Output:
            Dict[str, Any]: DOM構造の辞書
                {
                    "tag": "html",
                    "attributes": {...},
                    "children": [...]
                }
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

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

            # DOM構造を抽出するJavaScript
            structure = page.evaluate(f"""
                (maxDepth) => {{
                    function extractNode(node, depth) {{
                        if (depth > maxDepth || !node || node.nodeType !== 1) {{
                            return null;
                        }}

                        const attrs = {{}};
                        for (let attr of node.attributes || []) {{
                            attrs[attr.name] = attr.value;
                        }}

                        const children = [];
                        for (let child of node.children || []) {{
                            const childNode = extractNode(child, depth + 1);
                            if (childNode) {{
                                children.push(childNode);
                            }}
                        }}

                        return {{
                            tag: node.tagName.toLowerCase(),
                            attributes: attrs,
                            text: node.childNodes.length === 1 && node.childNodes[0].nodeType === 3
                                ? node.textContent.trim()
                                : "",
                            children: children
                        }};
                    }}

                    return extractNode(document.documentElement, 0);
                }}
            """, max_depth)

            return structure

        finally:
            context.close()

    def save_dom_to_file(
        self,
        url: str,
        output_path: str,
        format: str = "html",
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> str:
        """
        ページのDOMをファイルに保存

        Input:
            url: アクセスするURL
            output_path: 保存先パス
            format: 出力フォーマット ("html", "json")
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            str: 保存されたファイルのパス
        """
        # 出力ディレクトリを作成
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        if format == "html":
            content = self.get_page_dom(url, wait_time, viewport_size, output_format="html")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

        elif format == "json":
            structure = self.extract_dom_structure(url, wait_time, viewport_size)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)

        else:
            raise ValueError(f"Unknown format: {format}")

        return str(output_path_obj.absolute())


def quick_xpath_search(url: str, xpath: str, **kwargs) -> List[Dict[str, Any]]:
    """
    クイックXPath検索（コンテキストマネージャー不要）

    Input:
        url: アクセスするURL
        xpath: XPath式
        **kwargs: find_elements_by_xpathに渡す追加引数

    Output:
        List[Dict[str, Any]]: 要素情報のリスト
    """
    with DomXPathHandler() as handler:
        return handler.find_elements_by_xpath(url, xpath, **kwargs)


def quick_get_dom(url: str, output_format: str = "html", **kwargs) -> str:
    """
    クイックDOM取得（コンテキストマネージャー不要）

    Input:
        url: アクセスするURL
        output_format: 出力フォーマット ("html", "text")
        **kwargs: get_page_domに渡す追加引数

    Output:
        str: ページのDOM内容
    """
    with DomXPathHandler() as handler:
        return handler.get_page_dom(url, output_format=output_format, **kwargs)
