"""
CrowdWorks案件情報スクレイピングモジュール

【使用方法】
from crowdworks_scraper import CrowdWorksScraper

# インスタンス作成
scraper = CrowdWorksScraper(headless=False)

# 案件情報を取得（1件取得後に停止）
with scraper:
    job_data = scraper.scrape_jobs(
        url="https://crowdworks.jp/public/jobs/group/ec",
        max_jobs=1,  # 1件取得後に停止
        stop_after_first=True  # 1件取得後に停止して確認を求める
    )

# CSVに出力
scraper.save_to_csv(job_data, "output.csv")

【処理内容】
1. Playwrightを使用してCrowdWorksの案件一覧ページにアクセス
2. 案件リストを取得
3. 各案件の詳細ページにアクセスして詳細情報を取得
4. 案件情報を辞書形式で返却
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


class CrowdWorksScraper:
    """
    CrowdWorksの案件情報をスクレイピングするクラス
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

    def scrape_jobs(
        self,
        url: str,
        max_jobs: int = 1,
        stop_after_first: bool = True,
        wait_time: int = 3000,
        viewport_size: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        案件情報をスクレイピング

        Input:
            url: スクレイピング対象のURL
            max_jobs: 取得する最大案件数
            stop_after_first: 1件取得後に停止して確認を求めるか
            wait_time: 読み込み待機時間(ミリ秒)
            viewport_size: ビューポートサイズ

        Output:
            List[Dict[str, Any]]: 案件情報のリスト
        """
        page = self.get_page(viewport_size)
        jobs_data = []

        try:
            # 一覧ページにアクセス
            print(f"アクセス中: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"domcontentloadedでタイムアウト、loadを試行: {e}")
                try:
                    page.goto(url, wait_until="load", timeout=60000)
                except Exception as e2:
                    print(f"loadでもタイムアウト、commitを試行: {e2}")
                    page.goto(url, wait_until="commit", timeout=60000)
            page.wait_for_timeout(wait_time)

            # ページのHTMLを取得して構造を確認
            html_content = page.content()
            print(f"ページHTMLの長さ: {len(html_content)} 文字")

            # 案件リンクを探す（複数のセレクタを試す）
            job_links = []
            
            # 一般的なセレクタパターンを試す
            selectors = [
                "a[href*='/public/jobs/']",
                "a[href*='/jobs/']",
                ".job-item a",
                ".job-list-item a",
                "[data-job-id] a",
                "article a",
                ".card a"
            ]

            # 除外するURLパターン（カテゴリーページなど）
            exclude_patterns = [
                "/category/",
                "/group/",
                "/search",
                "/login",
                "/signup",
                "/help",
                "/about"
            ]

            for selector in selectors:
                try:
                    links = page.locator(selector).all()
                    if links:
                        print(f"セレクタ '{selector}' で {len(links)} 件のリンクを発見")
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "/jobs/" in href:
                                # 除外パターンをチェック
                                should_exclude = any(pattern in href for pattern in exclude_patterns)
                                if should_exclude:
                                    continue
                                
                                # 案件詳細ページのURLパターンをチェック（/public/jobs/数字 の形式）
                                # または /jobs/数字 の形式
                                job_id_pattern = r'/jobs/(\d+)(?:/|$)'
                                if re.search(job_id_pattern, href):
                                    full_url = href if href.startswith("http") else f"https://crowdworks.jp{href}"
                                    if full_url not in job_links:
                                        job_links.append(full_url)
                                        print(f"  案件リンク: {full_url}")
                                        
                        if job_links:
                            print(f"合計 {len(job_links)} 件の案件リンクを発見")
                            break
                except Exception as e:
                    print(f"セレクタ '{selector}' でエラー: {e}")
                    continue

            # リンクが見つからない場合、ページのテキストを確認
            if not job_links:
                print("案件リンクが見つかりません。ページ構造を確認します...")
                page_text = page.inner_text("body")
                print(f"ページテキストの最初の500文字:\n{page_text[:500]}")
                
                # HTMLの一部を保存して確認
                output_dir = Path(__file__).parent.parent / "98_tmp"
                output_dir.mkdir(parents=True, exist_ok=True)
                html_file = output_dir / "page_structure.html"
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"HTMLを保存しました: {html_file}")

            # 見つかったリンクから案件情報を取得
            for idx, job_url in enumerate(job_links[:max_jobs]):
                print(f"\n案件 {idx + 1}/{min(len(job_links), max_jobs)} を取得中: {job_url}")
                
                job_info = self.scrape_job_detail(page, job_url, wait_time)
                if job_info:
                    jobs_data.append(job_info)
                    print(f"取得したデータ: {job_info}")

                # 1件取得後に停止
                if stop_after_first and len(jobs_data) >= 1:
                    print("\n" + "="*50)
                    print("1件のデータを取得しました。確認をお願いします。")
                    print("="*50)
                    print(f"取得したデータ:\n{self._format_job_data(jobs_data[0])}")
                    print("\n続行する場合は、スクリプトを再実行してください。")
                    break

        finally:
            page.context.close()

        return jobs_data

    def scrape_job_detail(
        self,
        page: Page,
        job_url: str,
        wait_time: int = 3000
    ) -> Optional[Dict[str, Any]]:
        """
        案件詳細ページから情報を取得

        Input:
            page: PlaywrightのPageオブジェクト
            job_url: 案件詳細ページのURL
            wait_time: 読み込み待機時間(ミリ秒)

        Output:
            Dict[str, Any]: 案件情報の辞書
        """
        try:
            # 詳細ページにアクセス
            try:
                page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"詳細ページのdomcontentloadedでタイムアウト、loadを試行: {e}")
                try:
                    page.goto(job_url, wait_until="load", timeout=60000)
                except Exception as e2:
                    print(f"詳細ページのloadでもタイムアウト、commitを試行: {e2}")
                    page.goto(job_url, wait_until="commit", timeout=60000)
            page.wait_for_timeout(wait_time)

            job_info = {
                "url": job_url,
                "title": "",
                "description": "",
                "price": "",
                "deadline": "",
                "category": "",
                "skills": "",
                "client_info": "",
                "posted_date": "",
                "applicants": "",
                "status": "",
                "raw_html": page.content()[:5000]  # デバッグ用にHTMLの一部を保存
            }

            # タイトルを取得（複数のセレクタを試す）
            title_selectors = [
                "h1.job-title",
                "h1",
                ".job-title",
                "[data-job-title]",
                "title"
            ]
            for selector in title_selectors:
                try:
                    if selector == "title":
                        # titleタグの場合はinner_textではなくtext_contentを使用
                        job_info["title"] = page.title()
                        if job_info["title"] and "クラウドワークス" not in job_info["title"]:
                            # titleタグから「のお仕事」の前までを取得
                            if "のお仕事" in job_info["title"]:
                                job_info["title"] = job_info["title"].split("のお仕事")[0].strip()
                            break
                    else:
                        title_elem = page.locator(selector).first
                        if title_elem.count() > 0:
                            title_text = title_elem.inner_text().strip()
                            if title_text and "クラウドワークス" not in title_text:
                                job_info["title"] = title_text
                                if job_info["title"]:
                                    break
                except Exception as e:
                    continue
            
            # タイトルが取得できなかった場合、titleタグから取得
            if not job_info["title"] or "クラウドワークス" in job_info["title"]:
                try:
                    title_tag = page.title()
                    if "のお仕事" in title_tag:
                        job_info["title"] = title_tag.split("のお仕事")[0].strip()
                    elif "|" in title_tag:
                        job_info["title"] = title_tag.split("|")[0].strip()
                except:
                    pass

            # 説明を取得（複数のセレクタを試す）
            desc_selectors = [
                ".job-description",
                ".description",
                "[data-description]",
                ".job-detail",
                ".detail-content",
                "article .content",
                ".content-body",
                ".job-detail-content",
                "#job-detail",
                "[class*='detail']",
                "[class*='description']"
            ]
            for selector in desc_selectors:
                try:
                    desc_elem = page.locator(selector).first
                    if desc_elem.count() > 0:
                        desc_text = desc_elem.inner_text().strip()
                        if desc_text and len(desc_text) > 50:  # 十分な長さがある場合
                            job_info["description"] = desc_text[:2000]  # 最初の2000文字
                            if job_info["description"]:
                                break
                except:
                    continue
            
            # 説明が取得できなかった場合、「概要」セクションを探す
            if not job_info["description"] or len(job_info["description"]) < 50:
                try:
                    # 「概要」というテキストを含む要素を探す
                    overview_elem = page.locator("text=概要").first
                    if overview_elem.count() > 0:
                        # 親要素から説明を取得
                        parent = overview_elem.locator("..")
                        if parent.count() > 0:
                            desc_text = parent.inner_text().strip()
                            if desc_text and len(desc_text) > 50:
                                job_info["description"] = desc_text[:2000]
                        
                        # 次の兄弟要素を取得
                        if not job_info["description"] or len(job_info["description"]) < 50:
                            try:
                                next_sibling = overview_elem.locator("xpath=following-sibling::*[1]")
                                if next_sibling.count() > 0:
                                    desc_text = next_sibling.inner_text().strip()
                                    if desc_text and len(desc_text) > 50:
                                        job_info["description"] = desc_text[:2000]
                            except:
                                pass
                except:
                    pass
            
            # まだ説明が取得できていない場合、JavaScriptでページ構造を調べる
            if not job_info["description"] or len(job_info["description"]) < 50:
                try:
                    # 「仕事の詳細」セクションを探す
                    detail_section = page.locator("text=仕事の詳細").first
                    if detail_section.count() > 0:
                        # 次の要素を取得
                        try:
                            detail_content = detail_section.locator("xpath=following::*[contains(@class, 'content') or contains(@class, 'detail')][1]")
                            if detail_content.count() > 0:
                                desc_text = detail_content.inner_text().strip()
                                if desc_text and len(desc_text) > 50:
                                    job_info["description"] = desc_text[:2000]
                        except:
                            pass
                except:
                    pass

            # 価格を取得
            price_selectors = [
                "[data-price]",
                ".price",
                ".budget",
                ".job-budget",
                "span:has-text('円')",
                "span:has-text('¥')",
                "dd:has-text('円')",
                "dt:has-text('予算') + dd",
                "dt:has-text('報酬') + dd",
                "[class*='budget']",
                "[class*='price']"
            ]
            for selector in price_selectors:
                try:
                    price_elem = page.locator(selector).first
                    if price_elem.count() > 0:
                        price_text = price_elem.inner_text().strip()
                        if price_text and ("円" in price_text or "¥" in price_text or "万円" in price_text):
                            # 数字と円を含む部分だけを抽出
                            import re
                            price_match = re.search(r'([0-9,]+[万円円]+)', price_text)
                            if price_match:
                                job_info["price"] = price_match.group(1)
                            else:
                                job_info["price"] = price_text
                            if job_info["price"]:
                                break
                except:
                    continue
            
            # 価格が取得できなかった場合、テキストから「円」を含む部分を探す
            if not job_info["price"]:
                try:
                    page_text = page.inner_text("body")
                    # 「予算」や「報酬」の後に続く金額を探す
                    price_patterns = [
                        r'予算[：:]\s*([0-9,]+[万円円]+)',
                        r'報酬[：:]\s*([0-9,]+[万円円]+)',
                        r'([0-9,]+[万円円]+)',
                    ]
                    for pattern in price_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            job_info["price"] = match.group(1) if match.lastindex else match.group(0)
                            break
                except:
                    pass
            
            # 価格が取得できなかった場合、「予算」というテキストの近くを探す
            if not job_info["price"]:
                try:
                    budget_elem = page.locator("text=予算").first
                    if budget_elem.count() > 0:
                        # 親要素から価格を取得
                        parent = budget_elem.locator("..")
                        if parent.count() > 0:
                            parent_text = parent.inner_text().strip()
                            price_match = re.search(r'([0-9,]+[万円円]+)', parent_text)
                            if price_match:
                                job_info["price"] = price_match.group(1)
                except:
                    pass

            # その他の情報を取得（テキストから抽出を試みる）
            page_text = page.inner_text("body")
            
            # 応募期限を取得（より詳細に）
            try:
                deadline_elem = page.locator("text=応募期限").first
                if deadline_elem.count() > 0:
                    # 親要素から日付を取得
                    parent = deadline_elem.locator("..")
                    if parent.count() > 0:
                        deadline_text = parent.inner_text().strip()
                        # 日付パターンを抽出
                        date_match = re.search(r'応募期限\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', deadline_text)
                        if date_match:
                            job_info["deadline"] = date_match.group(1)
                        elif "応募期限" in deadline_text:
                            parts = deadline_text.split("応募期限")
                            if len(parts) > 1:
                                # 日付パターンを抽出
                                date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', parts[1])
                                if date_match:
                                    job_info["deadline"] = date_match.group(1)
                                else:
                                    job_info["deadline"] = parts[1].strip()[:100]
                
                # 応募期限が取得できなかった場合、テキストから直接探す
                if not job_info["deadline"]:
                    deadline_match = re.search(r'応募期限\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', page_text)
                    if deadline_match:
                        job_info["deadline"] = deadline_match.group(1)
            except Exception as e:
                pass
            
            # 掲載日を取得（より詳細に）
            try:
                posted_elem = page.locator("text=掲載日").first
                if posted_elem.count() > 0:
                    parent = posted_elem.locator("..")
                    if parent.count() > 0:
                        posted_text = parent.inner_text().strip()
                        # 日付パターンを抽出
                        date_match = re.search(r'掲載日\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', posted_text)
                        if date_match:
                            job_info["posted_date"] = date_match.group(1)
                        elif "掲載日" in posted_text:
                            parts = posted_text.split("掲載日")
                            if len(parts) > 1:
                                # 日付パターンを抽出
                                date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', parts[1])
                                if date_match:
                                    job_info["posted_date"] = date_match.group(1)
                                else:
                                    job_info["posted_date"] = parts[1].strip()[:100]
                
                # 掲載日が取得できなかった場合、テキストから直接探す
                if not job_info["posted_date"]:
                    posted_match = re.search(r'掲載日\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', page_text)
                    if posted_match:
                        job_info["posted_date"] = posted_match.group(1)
            except Exception as e:
                pass
            
            # 応募者数を取得（より詳細に）
            try:
                applicants_elem = page.locator("text=応募した人").first
                if applicants_elem.count() > 0:
                    # 親要素から取得
                    parent = applicants_elem.locator("..")
                    if parent.count() > 0:
                        applicants_text = parent.inner_text().strip()
                    else:
                        applicants_text = applicants_elem.inner_text().strip()
                    # 「応募した人 XX 人」の形式から数値を抽出
                    match = re.search(r'応募した人\s*(\d+)\s*人', applicants_text)
                    if match:
                        job_info["applicants"] = f"{match.group(1)}人"
                
                # 応募者数が取得できなかった場合、テキストから直接探す
                if not job_info["applicants"]:
                    applicants_match = re.search(r'応募した人\s*(\d+)\s*人', page_text)
                    if applicants_match:
                        job_info["applicants"] = f"{applicants_match.group(1)}人"
            except Exception as e:
                pass
            
            # カテゴリーを取得（より詳細に）
            try:
                # カテゴリーは通常、タイトルの近くやメタ情報に含まれる
                category_elem = page.locator("text=カテゴリ").first
                if category_elem.count() > 0:
                    parent = category_elem.locator("..")
                    if parent.count() > 0:
                        category_text = parent.inner_text().strip()
                        if "カテゴリ" in category_text:
                            parts = category_text.split("カテゴリ")
                            if len(parts) > 1:
                                job_info["category"] = parts[1].strip()[:200]
                
                # カテゴリーが取得できなかった場合、titleタグから取得を試みる
                if not job_info["category"]:
                    title_tag = page.title()
                    if "(" in title_tag and ")" in title_tag:
                        # タイトルに「(カテゴリー名)」の形式で含まれている場合
                        category_match = re.search(r'\(([^)]+)\)', title_tag)
                        if category_match:
                            job_info["category"] = category_match.group(1)
                
                # まだ取得できていない場合、説明テキストから抽出
                if not job_info["category"] and job_info.get("description"):
                    # 説明の中にカテゴリー情報が含まれている場合
                    desc_text = job_info["description"]
                    if "ECサイト制作" in desc_text:
                        job_info["category"] = "ECサイト制作"
                    elif "ECサイト" in desc_text:
                        category_match = re.search(r'(ECサイト[^の\s]+)', desc_text)
                        if category_match:
                            job_info["category"] = category_match.group(1)
            except Exception as e:
                pass
            
            # クライアント情報を取得
            try:
                client_elem = page.locator("text=クライアント").first
                if client_elem.count() > 0:
                    parent = client_elem.locator("..")
                    if parent.count() > 0:
                        client_text = parent.inner_text().strip()
                        if "クライアント" in client_text:
                            parts = client_text.split("クライアント")
                            if len(parts) > 1:
                                job_info["client_info"] = parts[1].strip()[:200]
            except:
                pass

            # 説明テキストから情報を抽出（説明に含まれている情報を個別フィールドに抽出）
            if job_info.get("description"):
                desc_text = job_info["description"]
                
                # 応募期限を説明から抽出
                if not job_info.get("deadline"):
                    deadline_match = re.search(r'応募期限\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', desc_text)
                    if deadline_match:
                        job_info["deadline"] = deadline_match.group(1)
                
                # 掲載日を説明から抽出
                if not job_info.get("posted_date"):
                    posted_match = re.search(r'掲載日\s*(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)', desc_text)
                    if posted_match:
                        job_info["posted_date"] = posted_match.group(1)
                
                # 応募者数を説明から抽出
                if not job_info.get("applicants"):
                    applicants_match = re.search(r'応募した人\s*(\d+)\s*人', desc_text)
                    if applicants_match:
                        job_info["applicants"] = f"{applicants_match.group(1)}人"
                
                # カテゴリーを説明から抽出
                if not job_info.get("category"):
                    if "ECサイト制作" in desc_text:
                        job_info["category"] = "ECサイト制作"
                    elif "ECサイト" in desc_text:
                        category_match = re.search(r'(ECサイト[^の\s]+)', desc_text)
                        if category_match:
                            job_info["category"] = category_match.group(1)
                
                # 価格を説明から抽出（「報酬」や「予算」のキーワードの後）
                if not job_info.get("price"):
                    price_match = re.search(r'(報酬|予算)[：:]\s*([0-9,]+[万円円]+)', desc_text)
                    if price_match:
                        job_info["price"] = price_match.group(2)
                    else:
                        # より広範囲に金額を探す
                        price_match = re.search(r'([0-9,]+[万円円]+)', desc_text)
                        if price_match:
                            job_info["price"] = price_match.group(1)

            return job_info

        except Exception as e:
            print(f"案件詳細の取得でエラー: {e}")
            return None

    def _format_job_data(self, job_data: Dict[str, Any]) -> str:
        """
        案件データを読みやすい形式でフォーマット

        Input:
            job_data: 案件情報の辞書

        Output:
            str: フォーマットされた文字列
        """
        lines = []
        for key, value in job_data.items():
            if key != "raw_html":
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def save_to_csv(
        self,
        jobs_data: List[Dict[str, Any]],
        output_path: str,
        encoding: str = "utf-8-sig"
    ) -> str:
        """
        案件情報をCSVファイルに保存

        Input:
            jobs_data: 案件情報のリスト
            output_path: 出力ファイルパス
            encoding: エンコーディング（デフォルト: utf-8-sig for Excel）

        Output:
            str: 保存されたファイルのパス
        """
        if not jobs_data:
            print("保存するデータがありません。")
            return ""

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # すべてのキーを取得
        all_keys = set()
        for job in jobs_data:
            all_keys.update(job.keys())
        
        # raw_htmlは除外
        all_keys.discard("raw_html")
        fieldnames = sorted(list(all_keys))

        with open(output_path, "w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for job in jobs_data:
                row = {key: job.get(key, "") for key in fieldnames}
                writer.writerow(row)

        print(f"CSVファイルを保存しました: {output_path}")
        return str(output_path_obj.absolute())

