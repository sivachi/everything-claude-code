"""
eBay商品情報スクレイピングモジュール

【使用方法】
from ebay_scraper import EbayScraper

# インスタンス作成
scraper = EbayScraper(headless=False)

# 商品情報を取得（1件取得後に停止）
with scraper:
    product_data = scraper.scrape_products(
        url="https://www.ebay.com/sch/58058/i.html?_nkw=mac+mini+m4&_from=R40",
        max_products=1,  # 1件取得後に停止
        stop_after_first=True  # 1件取得後に停止して確認を求める
    )

# CSVに出力
scraper.save_to_csv(product_data, "output.csv")

【処理内容】
1. Playwrightを使用してeBayの検索結果ページにアクセス
2. 商品リストを取得
3. 各商品の詳細情報を取得
4. 商品情報を辞書形式で返却
5. CSVファイルに出力
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
import csv
import time
import re

# 03_e2eフォルダのパスを追加（直接importは禁止なので、コピーして使用）
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "03_e2e"))

# 03_e2eのモジュールをコピーして使用（直接importは禁止）
from playwright.sync_api import sync_playwright, Page, Browser


class EbayScraper:
    """
    eBayの商品情報をスクレイピングするクラス
    """

    def __init__(self, headless: bool = False, browser_type: str = "chromium"):
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

    def get_page(self, viewport_size: Optional[Dict[str, int]] = None) -> Page:
        """
        新しいページを作成

        Input:
            viewport_size: ビューポートサイズ {"width": 1280, "height": 720}

        Output:
            Page: PlaywrightのPageオブジェクト
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use context manager (with statement)")

        context = self.browser.new_context(
            viewport=viewport_size or {"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return context.new_page()

    def scrape_products(
        self,
        url: str,
        max_products: Optional[int] = None,
        max_pages: Optional[int] = None,
        wait_time: int = 5000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        商品情報をスクレイピング（複数ページ対応）

        Input:
            url: スクレイピング対象のURL
            max_products: 取得する最大商品数（Noneの場合は制限なし）
            max_pages: 取得する最大ページ数（Noneの場合は制限なし）
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            List[Dict[str, Any]]: 商品情報のリスト
        """
        page = self.get_page(viewport_size)
        products_data = []
        current_url = url
        page_num = 1

        try:
            while True:
                # 最大ページ数のチェック
                if max_pages and page_num > max_pages:
                    print(f"\n最大ページ数({max_pages})に達しました。")
                    break

                # 最大商品数のチェック
                if max_products and len(products_data) >= max_products:
                    print(f"\n最大商品数({max_products})に達しました。")
                    break

                # 検索結果ページにアクセス
                print(f"\n{'='*60}")
                print(f"ページ {page_num} にアクセス中: {current_url}")
                print(f"{'='*60}")
                try:
                    # networkidleを使用してJavaScriptの読み込みを待つ
                    page.goto(current_url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"networkidleでタイムアウト、loadを試行: {e}")
                    try:
                        page.goto(current_url, wait_until="load", timeout=60000)
                    except Exception as e2:
                        print(f"loadでもタイムアウト、domcontentloadedを試行: {e2}")
                        page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                
                # eBayのページが完全に読み込まれるまで待機
                page.wait_for_timeout(wait_time)
                
                # ボット検出を回避するため、追加の待機とスクロール
                try:
                    # 商品リストが表示されるまで待機
                    page.wait_for_selector("ul.srp-results", timeout=15000)
                    # ページを少しスクロールしてコンテンツを読み込む
                    page.evaluate("window.scrollTo(0, 500)")
                    page.wait_for_timeout(2000)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"srp-resultsセレクタが見つかりません: {e}")
                    print("ページ構造を確認します...")

                # ページのHTMLを取得して構造を確認
                html_content = page.content()
                print(f"ページHTMLの長さ: {len(html_content)} 文字")

                # 商品リストを取得
                product_items = []
                
                # eBayの検索結果ページの一般的なセレクタパターンを試す
                selectors = [
                    "ul.srp-results > li.s-item",
                    "ul.srp-results li.s-item",
                    ".srp-results .s-item",
                    "ul.srp-results li",
                    "[data-view] li",
                    ".srp-item",
                    "li[data-viewid]",
                    "li.s-item"
                ]

                for selector in selectors:
                    try:
                        # セレクタが存在するか確認
                        count = page.locator(selector).count()
                        if count > 0:
                            items = page.locator(selector).all()
                            # 実際に商品情報を含むアイテムをフィルタリング
                            valid_items = []
                            for item in items:
                                try:
                                    # タイトルや価格が含まれているか確認
                                    item_text = item.inner_text()
                                    if item_text and len(item_text) > 50:  # 十分な情報がある
                                        valid_items.append(item)
                                except:
                                    continue
                            
                            if valid_items:
                                print(f"セレクタ '{selector}' で {len(valid_items)} 件の商品を発見")
                                product_items = valid_items
                                break
                    except Exception as e:
                        print(f"セレクタ '{selector}' でエラー: {e}")
                        continue

                # 商品が見つからない場合、ページのテキストを確認
                if not product_items:
                    print("商品が見つかりません。ページ構造を確認します...")
                    page_text = page.inner_text("body")
                    print(f"ページテキストの最初の500文字:\n{page_text[:500]}")
                    
                    # HTMLの一部を保存して確認
                    output_dir = Path(__file__).parent.parent / "98_tmp"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    html_file = output_dir / f"ebay_page_structure_page{page_num}.html"
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print(f"HTMLを保存しました: {html_file}")
                    
                    # 商品が見つからない場合は終了
                    print("商品が見つからないため、スクレイピングを終了します。")
                    break

                # 見つかった商品から情報を取得
                remaining_products = max_products - len(products_data) if max_products else len(product_items)
                products_to_scrape = min(len(product_items), remaining_products) if max_products else len(product_items)
                
                for idx, item in enumerate(product_items[:products_to_scrape]):
                    print(f"\n商品 {len(products_data) + 1} を取得中... (ページ {page_num}, アイテム {idx + 1}/{products_to_scrape})")
                    
                    product_info = self.scrape_product_item(page, item, wait_time)
                    if product_info:
                        products_data.append(product_info)
                        print(f"✓ 取得完了: {product_info.get('title', 'N/A')[:50]}...")

                print(f"\nページ {page_num} で {len(product_items)} 件の商品を処理しました。")
                print(f"累計取得数: {len(products_data)} 件")

                # 次のページへのリンクを探す
                next_page_url = self._find_next_page_url(page)
                if not next_page_url:
                    print("\n次のページが見つかりません。スクレイピングを終了します。")
                    break
                
                current_url = next_page_url
                page_num += 1
                
                # ページ間の待機時間（ボット検出を回避）
                page.wait_for_timeout(3000)

        finally:
            page.context.close()

        return products_data

    def _find_next_page_url(self, page: Page) -> Optional[str]:
        """
        次のページへのURLを探す

        Input:
            page: PlaywrightのPageオブジェクト

        Output:
            Optional[str]: 次のページのURL（見つからない場合はNone）
        """
        try:
            # 次のページへのリンクを探す（複数のパターンを試す）
            next_selectors = [
                "a.pagination__next",
                "a[aria-label='次のページ']",
                "a[aria-label='Next page']",
                "a:has-text('次へ')",
                "a:has-text('Next')",
                ".pagination a[rel='next']",
                "a[rel='next']",
                ".pagination__item--next a",
                "nav.pagination a:has-text('次へ')",
                "nav.pagination a:has-text('Next')"
            ]

            for selector in next_selectors:
                try:
                    next_link = page.locator(selector).first
                    if next_link.count() > 0:
                        href = next_link.get_attribute("href")
                        if href:
                            full_url = href if href.startswith("http") else f"https://www.ebay.com{href}"
                            print(f"\n次のページへのリンクを発見: {full_url}")
                            return full_url
                except:
                    continue

            # セレクタで見つからない場合、ページ番号のリンクから次のページを探す
            try:
                # 現在のページ番号を取得
                current_page_elem = page.locator(".pagination__item--active, .pagination__item.is-active, [aria-current='page']").first
                if current_page_elem.count() > 0:
                    current_page_text = current_page_elem.inner_text().strip()
                    try:
                        current_page_num = int(current_page_text)
                        # 次のページ番号のリンクを探す
                        next_page_num = current_page_num + 1
                        next_page_link = page.locator(f"a:has-text('{next_page_num}')").first
                        if next_page_link.count() > 0:
                            href = next_page_link.get_attribute("href")
                            if href:
                                full_url = href if href.startswith("http") else f"https://www.ebay.com{href}"
                                print(f"\n次のページ({next_page_num})へのリンクを発見: {full_url}")
                                return full_url
                    except:
                        pass
            except:
                pass

            # URLパラメータから次のページを構築
            try:
                current_url = page.url
                if "_pgn=" in current_url:
                    # ページ番号パラメータを更新
                    import re
                    match = re.search(r'_pgn=(\d+)', current_url)
                    if match:
                        current_pgn = int(match.group(1))
                        next_pgn = current_pgn + 1
                        next_url = re.sub(r'_pgn=\d+', f'_pgn={next_pgn}', current_url)
                        print(f"\nURLパラメータから次のページ({next_pgn})を構築: {next_url}")
                        return next_url
                else:
                    # ページ番号パラメータを追加
                    separator = "&" if "?" in current_url else "?"
                    next_url = f"{current_url}{separator}_pgn=2"
                    print(f"\nURLパラメータから次のページ(2)を構築: {next_url}")
                    return next_url
            except Exception as e:
                print(f"次のページURLの構築でエラー: {e}")

            return None
        except Exception as e:
            print(f"次のページURLの検索でエラー: {e}")
            return None

    def scrape_product_item(
        self,
        page: Page,
        item_locator,
        wait_time: int = 3000
    ) -> Optional[Dict[str, Any]]:
        """
        商品アイテムから情報を取得

        Input:
            page: PlaywrightのPageオブジェクト
            item_locator: 商品アイテムのLocatorオブジェクト
            wait_time: 読み込み待機時間(ミリ秒)

        Output:
            Dict[str, Any]: 商品情報の辞書
        """
        try:
            product_info = {
                "url": "",
                "title": "",
                "price": "",
                "shipping": "",
                "condition": "",
                "seller_name": "",
                "seller_feedback": "",
                "seller_rating": "",
                "location": "",
                "image_url": "",
                "time_left": "",
                "bids": "",
                "buy_it_now": "",
                "best_offer": "",
                "item_number": "",
                "raw_html": ""
            }

            # 商品のHTMLを取得（デバッグ用）
            try:
                product_info["raw_html"] = item_locator.inner_html()[:2000]
            except:
                pass

            # URLを取得
            try:
                link_elem = item_locator.locator("a").first
                if link_elem.count() > 0:
                    href = link_elem.get_attribute("href")
                    if href:
                        product_info["url"] = href if href.startswith("http") else f"https://www.ebay.com{href}"
            except Exception as e:
                print(f"URL取得エラー: {e}")

            # タイトルを取得
            title_selectors = [
                "h3.s-item__title",
                ".s-item__title",
                "h3",
                "[class*='title']",
                "a[class*='title']"
            ]
            for selector in title_selectors:
                try:
                    title_elem = item_locator.locator(selector).first
                    if title_elem.count() > 0:
                        title_text = title_elem.inner_text().strip()
                        if title_text and title_text.lower() != "shop on ebay":
                            product_info["title"] = title_text
                            break
                except:
                    continue

            # 価格を取得
            price_selectors = [
                ".s-item__price",
                "[class*='price']",
                "span:has-text('$')",
                ".s-item__detail--primary"
            ]
            for selector in price_selectors:
                try:
                    price_elem = item_locator.locator(selector).first
                    if price_elem.count() > 0:
                        price_text = price_elem.inner_text().strip()
                        if price_text and ("$" in price_text or "USD" in price_text or "円" in price_text):
                            product_info["price"] = price_text
                            break
                except:
                    continue

            # 送料情報を取得
            shipping_selectors = [
                ".s-item__shipping",
                ".s-item__freeXDays",
                "[class*='shipping']",
                "span:has-text('送料')",
                "span:has-text('shipping')"
            ]
            for selector in shipping_selectors:
                try:
                    shipping_elem = item_locator.locator(selector).first
                    if shipping_elem.count() > 0:
                        shipping_text = shipping_elem.inner_text().strip()
                        if shipping_text:
                            product_info["shipping"] = shipping_text
                            break
                except:
                    continue

            # 商品の状態を取得
            condition_selectors = [
                ".s-item__condition",
                "[class*='condition']",
                ".SECONDARY_INFO"
            ]
            for selector in condition_selectors:
                try:
                    condition_elem = item_locator.locator(selector).first
                    if condition_elem.count() > 0:
                        condition_text = condition_elem.inner_text().strip()
                        if condition_text:
                            product_info["condition"] = condition_text
                            break
                except:
                    continue

            # 出品者情報を取得
            seller_selectors = [
                ".s-item__seller-info",
                "[class*='seller']",
                ".s-item__seller-info-text"
            ]
            for selector in seller_selectors:
                try:
                    seller_elem = item_locator.locator(selector).first
                    if seller_elem.count() > 0:
                        seller_text = seller_elem.inner_text().strip()
                        if seller_text:
                            # 出品者名と評価を分離
                            if "(" in seller_text:
                                parts = seller_text.split("(")
                                product_info["seller_name"] = parts[0].strip()
                                if len(parts) > 1:
                                    feedback_match = re.search(r'(\d+[%]?)', parts[1])
                                    if feedback_match:
                                        product_info["seller_feedback"] = feedback_match.group(1)
                            else:
                                product_info["seller_name"] = seller_text
                            break
                except:
                    continue

            # 出品者の評価を取得
            rating_selectors = [
                ".s-item__seller-info .clipped",
                "[class*='rating']",
                ".s-item__reviews"
            ]
            for selector in rating_selectors:
                try:
                    rating_elem = item_locator.locator(selector).first
                    if rating_elem.count() > 0:
                        rating_text = rating_elem.get_attribute("aria-label") or rating_elem.inner_text().strip()
                        if rating_text:
                            product_info["seller_rating"] = rating_text
                            break
                except:
                    continue

            # 場所を取得
            location_selectors = [
                ".s-item__location",
                "[class*='location']",
                ".s-item__itemLocation"
            ]
            for selector in location_selectors:
                try:
                    location_elem = item_locator.locator(selector).first
                    if location_elem.count() > 0:
                        location_text = location_elem.inner_text().strip()
                        if location_text:
                            product_info["location"] = location_text
                            break
                except:
                    continue

            # 画像URLを取得
            try:
                img_elem = item_locator.locator("img").first
                if img_elem.count() > 0:
                    img_src = img_elem.get_attribute("src")
                    if img_src:
                        product_info["image_url"] = img_src
            except:
                pass

            # 残り時間を取得
            time_selectors = [
                ".s-item__time-left",
                "[class*='time']",
                ".s-item__time"
            ]
            for selector in time_selectors:
                try:
                    time_elem = item_locator.locator(selector).first
                    if time_elem.count() > 0:
                        time_text = time_elem.inner_text().strip()
                        if time_text:
                            product_info["time_left"] = time_text
                            break
                except:
                    continue

            # 入札数を取得
            bids_selectors = [
                ".s-item__bids",
                "[class*='bid']",
                ".s-item__bidCount"
            ]
            for selector in bids_selectors:
                try:
                    bids_elem = item_locator.locator(selector).first
                    if bids_elem.count() > 0:
                        bids_text = bids_elem.inner_text().strip()
                        if bids_text:
                            product_info["bids"] = bids_text
                            break
                except:
                    continue

            # Buy It Nowの有無を確認
            try:
                buy_it_now_elem = item_locator.locator(":has-text('Buy It Now')").first
                if buy_it_now_elem.count() > 0:
                    product_info["buy_it_now"] = "Yes"
            except:
                pass

            # Best Offerの有無を確認
            try:
                best_offer_elem = item_locator.locator(":has-text('Best Offer')").first
                if best_offer_elem.count() > 0:
                    product_info["best_offer"] = "Yes"
            except:
                pass

            # 商品番号を取得（URLから抽出）
            if product_info["url"]:
                item_match = re.search(r'/itm/(\d+)', product_info["url"])
                if item_match:
                    product_info["item_number"] = item_match.group(1)

            # アイテム全体のテキストから追加情報を抽出
            try:
                item_text = item_locator.inner_text()
                
                # 価格が取得できていない場合、テキストから抽出
                if not product_info["price"]:
                    price_match = re.search(r'\$[\d,]+\.?\d*', item_text)
                    if price_match:
                        product_info["price"] = price_match.group(0)
                
                # 送料が取得できていない場合、テキストから抽出
                if not product_info["shipping"]:
                    if "free shipping" in item_text.lower() or "送料無料" in item_text:
                        product_info["shipping"] = "Free Shipping"
                    elif "shipping" in item_text.lower() or "送料" in item_text:
                        shipping_match = re.search(r'(shipping|送料)[:\s]*([^\n]+)', item_text, re.IGNORECASE)
                        if shipping_match:
                            product_info["shipping"] = shipping_match.group(2).strip()[:100]
                
                # 状態が取得できていない場合、テキストから抽出
                if not product_info["condition"]:
                    condition_keywords = ["New", "Used", "Refurbished", "新品", "中古", "再生品"]
                    for keyword in condition_keywords:
                        if keyword in item_text:
                            product_info["condition"] = keyword
                            break
                
                # 残り時間が取得できていない場合、テキストから抽出
                if not product_info["time_left"]:
                    time_match = re.search(r'(\d+[dhms]\s*left|\d+日\s*残り)', item_text, re.IGNORECASE)
                    if time_match:
                        product_info["time_left"] = time_match.group(0)
                
                # 入札数が取得できていない場合、テキストから抽出
                if not product_info["bids"]:
                    bids_match = re.search(r'(\d+)\s*bids?', item_text, re.IGNORECASE)
                    if bids_match:
                        product_info["bids"] = f"{bids_match.group(1)} bids"
            except:
                pass

            return product_info

        except Exception as e:
            print(f"商品情報の取得でエラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _format_product_data(self, product_data: Dict[str, Any]) -> str:
        """
        商品データを読みやすい形式でフォーマット

        Input:
            product_data: 商品情報の辞書

        Output:
            str: フォーマットされた文字列
        """
        lines = []
        for key, value in product_data.items():
            if key != "raw_html":
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def save_to_csv(
        self,
        products_data: List[Dict[str, Any]],
        output_path: str,
        encoding: str = "utf-8-sig"
    ) -> str:
        """
        商品情報をCSVファイルに保存

        Input:
            products_data: 商品情報のリスト
            output_path: 出力ファイルパス
            encoding: エンコーディング（デフォルト: utf-8-sig for Excel）

        Output:
            str: 保存されたファイルのパス
        """
        if not products_data:
            print("保存するデータがありません。")
            return ""

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # すべてのキーを取得
        all_keys = set()
        for product in products_data:
            all_keys.update(product.keys())
        
        # raw_htmlは除外
        all_keys.discard("raw_html")
        fieldnames = sorted(list(all_keys))

        with open(output_path, "w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products_data:
                row = {key: product.get(key, "") for key in fieldnames}
                writer.writerow(row)

        print(f"CSVファイルを保存しました: {output_path}")
        return str(output_path_obj.absolute())

