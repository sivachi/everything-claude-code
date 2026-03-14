#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Slack チャンネル スクレイパー（Playwright / Python, Async, Windows対応）

【使用方法】
1. 必要なライブラリをインストール:
   pip install playwright
   playwright install chromium

2. 基本的な使用例:
   python slack_scraper.py --channel-url "https://workspace.slack.com/archives/CXXXX"

3. 詳細オプション例:
   python slack_scraper.py \
     --channel-url "https://workspace.slack.com/archives/CXXXX" \
     --out "exports/my_channel" \
     --max-minutes 30 \
     --max-rows 1000 \
     --since "2025-01-01" \
     --dl-concurrency 8 \
     --headful

4. 初回実行時:
   - ヘッドレスでセッション確認に失敗した場合、自動でヘッドフルブラウザが起動
   - SlackにログインしてメインUIが表示されたらEnterキーを押す
   - セッション情報が storage_state.json に保存され、次回以降は自動ログイン

5. 出力:
   - out/YYYY_MM_DD_HH_MM/ フォルダに実行時刻別で保存
   - CSV形式（Excel対応）とJSONL形式の両方で出力
   - 添付ファイルは attachments/ サブフォルダに保存
   - すべての時刻はJST（+09:00）で統一

【機能詳細】
- ヘッドレス優先 → セッション無効/未保存なら自動ヘッドフル切替・認証・保存 → ヘッドレス復帰
  （UA固定・検証強化・どうしても失敗時はヘッドフル継続）
- URL正規化: archives/messages → app.slack.com/client/T.../C...
- 中継ページ（アプリ誘導）は自動で「ブラウザで開く」にバイパス
- 抽出（メイン／スレッド右ペイン共通）:
    発言者  : button[data-qa="message_sender_name"]（text と data-message-sender）
    本文    : div.p-rich_text_section を結合（改行保持, innerText）
    表示時刻: span.c-timestamp__label[data-qa="timestamp_label"]
    数値時刻: time[datetime] / data-* / パーマリンク から UNIX秒を推定（保存時にJSTへ変換）
    添付    : a[href^="https://files.slack.com/files-pri/"] を attachments として収集（スレッド右ペインも）
- スレッド: 画面内の reply_bar_count を順にクリック → 右ペインから root+返信を収集（root_ts重複回避）
- 保存:
    実行ごとに PCローカル時刻（YYYY_MM_DD_HH_MM）のサブフォルダを作成（例: out/2025_09_11_02_10）
    すべての時刻は JST（+09:00）に整形して保存（CSV/JSONL）
    添付ファイルは out/<stamp>/attachments/ に保存（メイン＆スレッド両方）
    添付の重複は実行内＆再実行時ともにスキップ（attachments/_manifest.jsonl を参照）
    添付の保存名は「JSTタイムスタンプ + 連番 + 拡張子」（例: 20250911_143012.pdf, 20250911_143012_02.png）
- 自動停止: stagnation 回連続増加ゼロ / max-batch / pass-limit
           + 追加: max-minutes（時間）/ max-rows（件数）/ since（取得開始日時）
- 並列ダウンロード: --dl-concurrency で同時数、--dl-retries でリトライ回数
- PDF等が直GETで403/401のときは、Referer付き直GET→失敗時ページ経由クリックDLに自動フォールバック
"""

import asyncio
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, unquote
import random

from playwright.async_api import async_playwright, Page

# =========================
# 設定（停止条件はCLIで上書き可）
# =========================
DEFAULT_MAX_STAGNATION = 8   # 新規が増えない状態が続く回数で停止
DEFAULT_MAX_BATCH      = 60  # 総バッチ数の上限
DEFAULT_PASS_LIMIT     = 5   # 1バッチ内でのスレッド探索パス上限

DEFAULT_DL_CONCURRENCY = 4   # 添付の同時ダウンロード数
DEFAULT_DL_RETRIES     = 2   # 添付の最大リトライ回数

ATTACH_PREFIX = "https://files.slack.com/files-pri/"

STORAGE_STATE_PATH = Path("storage_state.json")
JST = timezone(timedelta(hours=9))  # 保存時に使うJST

# ヘッドレス/ヘッドフルで同一UAを使用（セッション安定化）
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

# =========================
# ユーティリティ
# =========================
def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

@dataclass
class MessageItem:
    author: Optional[str]
    text: Optional[str]
    time_text: Optional[str]

def _sanitize_for_csv(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s).replace("\r\n", "\n").replace("\r", "\n")
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s  # Excelの数式解釈対策
    return s

def to_jst_iso(ts: Optional[int]) -> Optional[str]:
    """UNIX秒を JST の ISO8601(+09:00) に整形"""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), JST).isoformat()
    except Exception:
        return None

def ext_from_url(url: str) -> str:
    """URLから拡張子を抽出（安全ガード付き）"""
    try:
        path = urlparse(url).path
        ext = Path(unquote(path)).suffix  # 例: ".pdf", ".png"
        if ext and len(ext) <= 10 and re.match(r"^\.[A-Za-z0-9]+$", ext):
            return ext
    except Exception:
        pass
    return ""

def jst_stamp_from_ts(ts: Optional[int]) -> str:
    """UNIX秒 → "YYYYMMDD_HHMMSS"（JST）。ts が無い場合は現在JST。"""
    if ts is None:
        dt = datetime.now(JST)
    else:
        dt = datetime.fromtimestamp(int(ts), JST)
    return dt.strftime("%Y%m%d_%H%M%S")

def uniquify(path: Path) -> Path:
    """存在する場合は (1), (2) ... を付与して一意ファイル名に"""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        cand = parent / f"{stem}({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1

# =========================
# ブラウザ起動系（UA固定・ロケール/タイムゾーン指定）
# =========================
async def launch_browser(playwright, headful: bool):
    browser = await playwright.chromium.launch(
        headless=not headful,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context_args = dict(
        viewport={"width": 1400, "height": 900},
        ignore_https_errors=True,
        accept_downloads=True,   # ページ経由のダウンロード保存を許可
        user_agent=CHROME_UA,    # UA固定
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
    )
    if STORAGE_STATE_PATH.exists():
        context_args["storage_state"] = str(STORAGE_STATE_PATH)
    context = await browser.new_context(**context_args)
    return browser, context

async def looks_like_main_ui(page: Page, timeout_ms: int = 10000) -> bool:
    """SlackのメインUI（左サイドバー/メッセージリスト）が表示されているかの簡易判定"""
    try:
        await page.wait_for_selector(
            'nav[aria-label*="Channels"], [data-qa="channel_sidebar"]',
            timeout=timeout_ms,
        )
        await page.wait_for_selector(
            '[data-qa="virtual-list-item"], [data-qa="message_container"], div[role="listitem"]',
            timeout=timeout_ms,
        )
        return True
    except:
        return False

async def interactive_login_and_save_state(playwright) -> None:
    """ヘッドフルで起動してユーザーにログインしてもらい、storage_state.json を保存"""
    log("ヘッドレスでセッション検証に失敗。ヘッドフルに切替えてログインを促します。")
    browser, context = await launch_browser(playwright, headful=True)
    try:
        page = await context.new_page()
        await page.goto("https://app.slack.com/client", wait_until="domcontentloaded")
        print("\n[ログイン] ブラウザで Slack にログインしてください。メインUIが見えたら Enter を押してください。")
        await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        ok = await looks_like_main_ui(page, timeout_ms=12000)
        if not ok:
            log("メインUIを検出できませんでしたが、セッションを保存して続行します。")
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        log(f"セッション保存: {STORAGE_STATE_PATH}")
    finally:
        await browser.close()

async def get_logged_in_context(playwright, prefer_headful: bool):
    """
    - prefer_headful=True: そのままヘッドフルでログイン確認（必要なら手動認証）して返す
    - prefer_headful=False: まずヘッドレスで試行 → 失敗時はヘッドフルでログイン→保存→
                            ヘッドレスで再起動。再検証も失敗ならヘッドフル継続で返す
    """
    async def _verify_with(page: Page, url: str, timeout_ms: int = 12000) -> bool:
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except:
            return False
        # SW/リダイレクト待ち
        await page.wait_for_timeout(800)
        return await looks_like_main_ui(page, timeout_ms=timeout_ms)

    # 1) ヘッドフル希望ならそのまま
    if prefer_headful:
        browser, context = await launch_browser(playwright, headful=True)
        page = await context.new_page()
        ok = await _verify_with(page, "https://app.slack.com/client")
        if not ok:
            print("\n[ログイン] ブラウザで Slack にログインしてください。メインUIが見えたら Enter を押してください。")
            await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        await page.close()
        return browser, context

    # 2) まずヘッドレスで試行
    browser, context = await launch_browser(playwright, headful=False)
    page = await context.new_page()
    ok = await _verify_with(page, "https://app.slack.com/client")
    if not ok:
        # もう一度少し待って再検証
        await page.wait_for_timeout(1200)
        ok = await _verify_with(page, "https://app.slack.com/client")
    if ok:
        await context.storage_state(path=str(STORAGE_STATE_PATH))
        await page.close()
        return browser, context

    # 3) ヘッドレス失敗 → ヘッドフルでログイン保存
    await browser.close()
    await interactive_login_and_save_state(playwright)

    # 4) 保存したセッションでヘッドレス再起動し再検証
    browser2, context2 = await launch_browser(playwright, headful=False)
    page2 = await context2.new_page()
    ok2 = await _verify_with(page2, "https://app.slack.com/client", timeout_ms=15000)
    if not ok2:
        # 最後の手段：ヘッドフルで継続（警告は出すが処理は続ける）
        log("警告: ログインセッションの確認に失敗しました。今回はヘッドフルで継続します。")
        await browser2.close()
        browser3, context3 = await launch_browser(playwright, headful=True)
        page3 = await context3.new_page()
        await _verify_with(page3, "https://app.slack.com/client", timeout_ms=15000)
        await context3.storage_state(path=str(STORAGE_STATE_PATH))
        await page3.close()
        return browser3, context3

    await context2.storage_state(path=str(STORAGE_STATE_PATH))
    await page2.close()
    return browser2, context2

# =========================
# URL 正規化 / 中継ページ回避
# =========================
ARCHIVES_RE = re.compile(r"^https?://[^/]*slack\.com/archives/(C[A-Z0-9]+)")
MSG_URL_RE  = re.compile(r"^https://app\.slack\.com/client/(T[A-Z0-9]+)/messages/(C[A-Z0-9]+)")

async def get_team_id_via_app_client(context) -> str:
    page = await context.new_page()
    await page.goto("https://app.slack.com/client", wait_until="domcontentloaded")
    for _ in range(60):
        url = page.url
        m = re.search(r"/client/(T[A-Z0-9]+)", url)
        if m:
            team_id = m.group(1)
            await page.close()
            return team_id
        await page.wait_for_timeout(1000)
    await page.close()
    raise RuntimeError("Team ID を自動取得できません。ヘッドフルでログイン後に再実行してください。")

async def normalize_channel_url(channel_url: str, context) -> str:
    if "app.slack.com/client/" in channel_url:
        return channel_url
    m = ARCHIVES_RE.match(channel_url)
    if m:
        channel_id = m.group(1)
        team_id = await get_team_id_via_app_client(context)
        return f"https://app.slack.com/client/{team_id}/{channel_id}"
    return channel_url

async def normalize_messages_url_to_client(url: str) -> str:
    m = MSG_URL_RE.match(url)
    if m:
        team, channel = m.groups()
        return f"https://app.slack.com/client/{team}/{channel}"
    return url

async def bypass_desktop_app_prompt(page: Page) -> bool:
    try:
        link = await page.wait_for_selector('a[href*="/messages/C"]', timeout=3000)
        href = await link.get_attribute("href")
        if href:
            norm = await normalize_messages_url_to_client(href)
            await page.goto(norm, wait_until="domcontentloaded")
            return True
    except:
        pass
    try:
        el = await page.wait_for_selector('a:has-text("ブラウザで開く"), button:has-text("ブラウザで開く")', timeout=3000)
        await el.click()
        return True
    except:
        pass
    try:
        el = await page.wait_for_selector('a:has-text("open this link in your browser"), button:has-text("open this link in your browser")', timeout=3000)
        await el.click()
        return True
    except:
        pass
    return False

# =========================
# 抽出（共通JS・スコープ可）
# =========================
def _js_extract_script_scoped(root_sel: Optional[str]) -> str:
    """
    メインリスト／スレッド右ペインのどちらにも効く抽出器。
    添付は files-pri を広めのセレクタで検出（リンク位置の差分に強くする）。
    """
    root = f"document.querySelector('{root_sel}')" if root_sel else "document"
    return rf"""
(() => {{
  const root = {root};
  if (!root) return [];

  const q  = (base, sel) => base ? base.querySelector(sel) : null;
  const qa = (base, sel) => base ? Array.from(base.querySelectorAll(sel)) : [];

  const getInnerText = (el) => {{
    if (!el) return null;
    const t = (el.innerText || el.textContent || '').replace(/\u00A0/g, ' ');
    return t.replace(/\s+$/,''); // 改行保持・末尾空白のみ除去
  }};

  const pickTimestamp = (container) => {{
    let timeEl = container.querySelector('time');
    if (timeEl && timeEl.getAttribute('datetime')) {{
      const d = Date.parse(timeEl.getAttribute('datetime'));
      if (!Number.isNaN(d)) {{
        const ts = Math.floor(d/1000);
        return {{ ts, ts_iso: new Date(ts*1000).toISOString() }};
      }}
    }}
    let tsHolder =
      container.querySelector('[data-timestamp]') ||
      container.querySelector('[data-message-ts]') ||
      container.querySelector('[data-ts]');
    if (tsHolder) {{
      const v = tsHolder.getAttribute('data-timestamp') ||
                tsHolder.getAttribute('data-message-ts') ||
                tsHolder.getAttribute('data-ts');
      if (v && /^\d+(?:\.\d+)?$/.test(v)) {{
        const ts = Math.floor(parseFloat(v));
        return {{ ts, ts_iso: new Date(ts*1000).toISOString() }};
      }}
    }}
    const link = container.querySelector('a[data-qa="message_permalink"], a[href*="/archives/"][href*="/p"], a[href*="/thread/"]');
    const href = link?.getAttribute('href') || '';
    let m = href.match(/\/p(\d{10})(\d{{3,}})?/);
    if (m) {{
      const ts = parseInt(m[1], 10);
      return {{ ts, ts_iso: new Date(ts*1000).toISOString() }};
    }}
    m = href.match(/-(\d{10})\.\d{{3,}}/);
    if (m) {{
      const ts = parseInt(m[1], 10);
      return {{ ts, ts_iso: new Date(ts*1000).toISOString() }};
    }}
    return {{ ts: null, ts_iso: null }};
  }};

  const containers = qa(root,
    '[data-qa="message_container"], [data-qa="virtual-list-item"], div[role="listitem"], [data-qa="message_pane"] *[role="listitem"]'
  );

  const out = [];
  const seen = new Set();

  for (const node of containers) {{
    const container = node.closest?.('[data-qa="message_container"]') || node;

    const authorBtn =
      container.querySelector('button[data-qa="message_sender_name"]') ||
      container.querySelector('[data-qa="message_sender_name"]');
    const author_name = getInnerText(authorBtn);
    const author_id   = authorBtn?.getAttribute('data-message-sender') || null;

    const sections = Array.from(container.querySelectorAll('div.p-rich_text_section'));
    let body = null;
    if (sections.length) {{
      body = sections.map(getInnerText).filter(Boolean).join('\\n');
    }} else {{
      const textEl = container.querySelector('[data-qa="message_content"], div[data-qa="message-text"]');
      body = getInnerText(textEl);
    }}

    const timeLabel =
      container.querySelector('span.c-timestamp__label[data-qa="timestamp_label"]') ||
      container.querySelector('[data-qa="message_time"]') ||
      container.querySelector('time') ||
      container.querySelector('button[aria-label*=" at "]') ||
      container.querySelector('button[aria-label*="時"]');
    const time_text = (timeLabel?.getAttribute?.('aria-label') || timeLabel?.textContent || '').trim() || null;

    const {{ ts, ts_iso }} = pickTimestamp(container);

    // 添付リンク（files-pri のみ）
    const fileLinkNodes = [
      ...qa(container, 'a[href^="{ATTACH_PREFIX}"]'),
      ...qa(container, '[data-qa="message_content"] a[href^="{ATTACH_PREFIX}"]'),
      ...qa(container, 'div[data-qa="file_card"] a[href^="{ATTACH_PREFIX}"]'),
      ...qa(container, 'button.c-link--button[href^="{ATTACH_PREFIX}"]')
    ];
    const fileLinks = Array.from(new Set(fileLinkNodes
      .map(a => a.getAttribute('href'))
      .filter(href => !!href && href.startsWith("{ATTACH_PREFIX}"))
    ));

    if (!author_name && !body && fileLinks.length === 0) continue;

    const key = JSON.stringify([author_name || '', body || '', ts || time_text || '', fileLinks.join('|')]);
    if (seen.has(key)) continue;
    seen.add(key);

    let reply_count = null;
    const replyBtn = container.querySelector('button[data-qa="reply_bar_count"]');
    if (replyBtn) {{
      const t = replyBtn.textContent || '';
      const m = t.match(/(\d+)/);
      reply_count = m ? parseInt(m[1], 10) : 0;
    }}

    out.push({{
      author: author_name || null,
      author_id: author_id,
      text: body || null,
      time_text: time_text,
      ts: ts,
      ts_iso: ts_iso,
      reply_count: reply_count,
      attachments: fileLinks
    }});
  }}
  return out;
}})();
    """

async def extract_messages(page: Page) -> Tuple[List[MessageItem], List[Dict[str, Any]]]:
    items = await page.evaluate(_js_extract_script_scoped(root_sel=None))
    typed = [MessageItem(i.get("author"), i.get("text"), i.get("time_text")) for i in items]
    return typed, items

async def extract_thread_messages(page: Page) -> List[Dict[str, Any]]:
    """
    右ペインのスレッドからメッセージを抽出し、thread_root_ts / thread_root_ts_iso / kind を付与
    （添付も files-pri を検出し attachments に格納）
    """
    pane_sel_candidates = [
        '[data-qa="thread_view"]',
        'div[aria-label*="スレッド"]',
        'div[aria-label*="Thread"]',
        'div.p-workspace__primary_view--right',
        'div[data-qa="slack_kit_scrollbar"]',
    ]
    pane_sel = None
    for sel in pane_sel_candidates:
        try:
            await page.wait_for_selector(sel, timeout=2500)
            pane_sel = sel
            break
        except:
            continue
    if not pane_sel:
        return []

    # thread_ts（rootの10桁秒）を URL から推定
    thread_root_ts = await page.evaluate(r"""
(() => {
  const link = document.querySelector('a[href*="thread_ts="]');
  if (!link) return null;
  const href = link.getAttribute('href') || '';
  const m = href.match(/thread_ts=(\d{10})\.\d{3,}/);
  return m ? parseInt(m[1], 10) : null;
})()
    """)
    thread_root_ts_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(thread_root_ts)) if thread_root_ts else None

    items = await page.evaluate(_js_extract_script_scoped(root_sel=pane_sel))

    out: List[Dict[str, Any]] = []
    for it in items:
        row = dict(it)
        row["thread_root_ts"] = thread_root_ts
        row["thread_root_ts_iso"] = thread_root_ts_iso
        kind = "reply"
        if thread_root_ts and it.get("ts") and int(it["ts"]) == int(thread_root_ts):
            kind = "root"
        row["kind"] = kind
        out.append(row)
    return out

async def close_thread_pane(page: Page):
    candidates = [
        '[data-qa="thread_close"]',
        'button[aria-label*="スレッドを閉じる"]',
        'button[aria-label*="Close thread"]',
        'button[title*="Close"]',
    ]
    for sel in candidates:
        try:
            btn = await page.wait_for_selector(sel, timeout=800)
            await btn.click()
            await page.wait_for_timeout(250)
            return
        except:
            continue

# =========================
# スクロール
# =========================
async def scroll_up(page: Page, steps: int = 6, pause_ms: int = 400):
    for _ in range(steps):
        await page.mouse.wheel(0, -1200)
        await page.wait_for_timeout(pause_ms)

# =========================
# ダウンロード実装（Referer付き直GET → 失敗時ページ経由フォールバック）
# =========================
async def _download_via_page(context, url: str, save_path: Path) -> bool:
    """
    ページ内で <a href="url"> をクリックして Playwright の Download API で保存。
    クッキー/リダイレクト/CSRF 等をブラウザ同等に処理できる。
    """
    page = await context.new_page()
    try:
        # Referer を与えるために一度クライアントに遷移
        await page.goto("https://app.slack.com/client", wait_until="domcontentloaded")

        async with page.expect_download() as dl_info:
            await page.evaluate(
                """(u) => {
                    const a = document.createElement('a');
                    a.href = u;
                    a.download = '';
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => a.remove(), 1000);
                }""",
                url,
            )
        download = await dl_info.value
        await download.save_as(str(save_path))
        return True
    except Exception as e:
        log(f"[DL失敗(page)] {url} ({e})")
        return False
    finally:
        await page.close()

async def _download_one_with_retry(context, url: str, save_path: Path, retries: int) -> bool:
    """
    1) APIリクエスト（Referer付き）で試行
    2) 401/403/HTML等ならページ経由にフォールバック
    3) 失敗時は指数バックオフでリトライ
    """
    attempt = 0
    wait_base = 0.8

    while True:
        # --- まずは API リクエストで直接 ---
        try:
            resp = await context.request.get(
                url,
                headers={
                    "Referer": "https://app.slack.com/client",
                    "Accept": "*/*",
                },
            )
            if resp.ok:
                data = await resp.body()
                ct = (resp.headers or {}).get("content-type", "")
                # まれにHTMLログインが返るので軽く判別
                if b"<html" in data[:1024].lower() and "text/html" in ct:
                    raise PermissionError("HTML/ログインページを受信（クッキーが必要）")

                with open(save_path, "wb") as f:
                    f.write(data)
                return True
            else:
                # 認可系はページ経由にフォールバック
                if resp.status in (401, 403):
                    ok = await _download_via_page(context, url, save_path)
                    if ok:
                        return True
                    err = f"HTTP {resp.status}（pageフォールバックも失敗）"
                else:
                    err = f"HTTP {resp.status}"
        except PermissionError as e:
            ok = await _download_via_page(context, url, save_path)
            if ok:
                return True
            err = str(e)
        except Exception as e:
            err = str(e)

        if attempt >= retries:
            log(f"[DL失敗] {url} ({err})")
            return False

        # backoff (±20% jitter)
        backoff = wait_base * (2 ** attempt)
        jitter = backoff * (0.2 * (random.random() - 0.5) * 2)
        wait_s = max(0.3, backoff + jitter)
        log(f"[DLリトライ] {url} ({err}) -> {attempt+1}/{retries} 後 {wait_s:.1f}s")
        await asyncio.sleep(wait_s)
        attempt += 1

# =========================
# 添付ダウンロード（JSTタイムスタンプ名・重複URLスキップ・並列DL）
# =========================
async def download_attachments(context, messages: List[Dict[str, Any]], run_dir: Path,
                               dl_concurrency: int, dl_retries: int):
    """
    添付URLを out/<stamp>/attachments/ に保存。
    保存ファイル名: JSTタイムスタンプ + 連番 + 元拡張子
       例) 20250911_143012.pdf, 20250911_143012_02.png
    既存URLは manifest でスキップ。並列ダウンロード対応。
    """
    attach_dir = run_dir / "attachments"
    attach_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = attach_dir / "_manifest.jsonl"

    # 既存マニフェストのURL集合をロード
    persisted: Set[str] = set()
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as mf:
                for line in mf:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        url = rec.get("url")
                        if isinstance(url, str):
                            persisted.add(url)
                    except Exception:
                        continue
        except Exception:
            pass

    # 対象URLを (url, ts) で収集。ts はメッセージの ts を用いる（無ければ None）
    targets: List[Tuple[str, Optional[int]]] = []
    seen_this_run: Set[str] = set()

    for m in messages:
        ts = m.get("ts") if isinstance(m.get("ts"), int) else None
        for url in m.get("attachments", []) or []:
            if not isinstance(url, str) or not url.startswith(ATTACH_PREFIX):
                continue
            if url in seen_this_run:
                continue
            if url in persisted:
                log(f"[DLスキップ] 既に保存済み: {url}")
                continue
            seen_this_run.add(url)
            targets.append((url, ts))

    if not targets:
        log("[DL] 添付対象なし")
        return

    # 同一タイムスタンプ内の連番管理
    seq_per_stamp: Dict[str, int] = {}

    # 保存名を事前に決める（実際の保存時は uniquify で最終調整）
    planned: Dict[str, Path] = {}  # url -> save_path
    for url, ts in targets:
        stamp = jst_stamp_from_ts(ts)  # "YYYYMMDD_HHMMSS"
        seq_per_stamp.setdefault(stamp, 0)
        seq_per_stamp[stamp] += 1
        seq = seq_per_stamp[stamp]

        suffix = ext_from_url(url)
        # 1件目は連番省略、2件目以降は _02, _03 ...
        tag = "" if seq == 1 else f"_{seq:02d}"
        fname = f"{stamp}{tag}{suffix}"
        planned[url] = attach_dir / fname

    # 並列実行のためのセマフォとマニフェスト書き込みロック
    sem = asyncio.Semaphore(max(1, dl_concurrency))
    manifest_lock = asyncio.Lock()

    async def worker(url: str, save_path_planned: Path):
        # 万一の衝突に備えて一意化
        save_path = uniquify(save_path_planned)

        # 既に完全同名があれば manifest 追記だけ（URL未登録時）
        if save_path.exists():
            log(f"[DLスキップ] 同名ファイルが存在: {save_path.name}")
            async with manifest_lock:
                with manifest_path.open("a", encoding="utf-8") as mf:
                    mf.write(json.dumps(
                        {"url": url, "filename": save_path.name, "saved_at": datetime.now().isoformat()},
                        ensure_ascii=False
                    ) + "\n")
            return

        async with sem:
            ok = await _download_one_with_retry(context, url, save_path, retries=dl_retries)
            if ok:
                log(f"[DL] 添付保存: {save_path.name}")
                # 成功したら manifest に追記
                async with manifest_lock:
                    try:
                        with manifest_path.open("a", encoding="utf-8") as mf:
                            mf.write(json.dumps(
                                {"url": url, "filename": save_path.name, "saved_at": datetime.now().isoformat()},
                                ensure_ascii=False
                            ) + "\n")
                        # ここで persisted にも追加（再実行時スキップ用）
                        persisted.add(url)
                    except Exception as e:
                        log(f"[manifest警告] 記録に失敗: {e}")

    log(f"[DL] 目標 {len(targets)} 件, 並列 {dl_concurrency}, リトライ {dl_retries}")
    await asyncio.gather(*(worker(u, planned[u]) for u, _ in targets))

# =========================
# 保存（テキスト＆JSONL）
# =========================
def decorate_with_jst(rows: List[Dict[str, Any]], is_thread: bool = False) -> List[Dict[str, Any]]:
    """各行に JST の ISO を付与。thread の場合は root_ts のJSTも付与"""
    out = []
    for r in rows:
        r = dict(r)  # コピー
        r["ts_iso_jst"] = to_jst_iso(r.get("ts"))
        if is_thread:
            r["thread_root_ts_iso_jst"] = to_jst_iso(r.get("thread_root_ts"))
        out.append(r)
    return out

def _attachments_csv_cell(r: Dict[str, Any]) -> str:
    urls = r.get("attachments") or []
    if not urls:
        return ""
    return _sanitize_for_csv(", ".join(urls))

def save_main_csv(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Author", "本文", "タイムスタンプ", "添付URL(カンマ区切り)"])
        for r in rows:
            author = _sanitize_for_csv(r.get("author"))
            body   = _sanitize_for_csv(r.get("text"))
            ts_jst = r.get("ts_iso_jst") or _sanitize_for_csv(r.get("time_text"))
            attach = _attachments_csv_cell(r)
            w.writerow([author, body, ts_jst, attach])

def save_threads_csv(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["RootTS(ISO_JST)", "Kind", "Author", "本文", "タイムスタンプ", "添付URL(カンマ区切り)"])
    for r in rows:
        root_iso_jst = r.get("thread_root_ts_iso_jst") or ""
        kind     = r.get("kind") or ""
        author   = _sanitize_for_csv(r.get("author"))
        body     = _sanitize_for_csv(r.get("text"))
        ts_jst   = r.get("ts_iso_jst") or _sanitize_for_csv(r.get("time_text"))
        attach   = _attachments_csv_cell(r)
        with path.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow([root_iso_jst, kind, author, body, ts_jst, attach])

def save_jsonl(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# =========================
# メイン処理
# =========================
async def scrape_channel(channel_url: str, out_basename: str, headful_requested: bool,
                         max_stagnation: int, max_batch: int, pass_limit: int,
                         max_minutes: int, max_rows: int, since_ts: Optional[int],
                         dl_concurrency: int, dl_retries: int):
    async with async_playwright() as p:
        # ---- ログイン済みコンテキストを入手（ヘッドレス優先 / 必要なら自動ヘッドフル）----
        browser, context = await get_logged_in_context(p, prefer_headful=headful_requested)
        try:
            # URL正規化（archives → client）
            normalized_url = await normalize_channel_url(channel_url, context)

            page = await context.new_page()
            log(f"移動: {normalized_url}")
            await page.goto(normalized_url, wait_until="domcontentloaded", timeout=90_000)

            # 中継ページ(アプリ誘導)ならバイパス
            await bypass_desktop_app_prompt(page)

            # UI待機
            await page.wait_for_selector(
                '[data-qa="channel_sidebar"], nav[aria-label*="Channels"], [aria-label*="メッセージ"]',
                timeout=60_000
            )
            await page.wait_for_selector(
                '[data-qa="virtual-list-item"], [data-qa="message_container"], div[role="listitem"], [data-qa="message_pane"] *[role="listitem"]',
                timeout=60_000
            )

            # 収集バッファ
            main_rows:   List[Dict[str, Any]] = []
            thread_rows: List[Dict[str, Any]] = []
            seen_main:   Set[Tuple[str, str, str]] = set()   # (author, text, ts_iso/time_text)
            seen_roots:  Set[int] = set()                    # 処理済み thread_root_ts

            prev_total = 0
            stagnation = 0
            start_monotonic = time.monotonic()

            stop_due_to_row_limit = False

            # ===== メインスクレイプ（上方向へ読み戻し） =====
            for batch in range(1, max_batch + 1):
                if stop_due_to_row_limit:
                    break
                # 1) 時間上限
                if max_minutes > 0:
                    elapsed_min = (time.monotonic() - start_monotonic) / 60.0
                    if elapsed_min >= max_minutes:
                        log(f"時間上限 {max_minutes} 分に達したため終了します。")
                        break

                # メイン面の抽出
                _, items = await extract_messages(page)

                # 2) since の到達判定（画面内の最小 ts が since より古ければ終了）
                if since_ts is not None:
                    visible_ts = [r.get("ts") for r in items if isinstance(r.get("ts"), int)]
                    if visible_ts:
                        oldest = min(visible_ts)
                        if oldest < since_ts:
                            log("since 以前の領域に到達したため終了します。")
                            break

                # 追加・重複排除
                added_main = 0
                for r in items:
                    key = (r.get("author",""), r.get("text",""), r.get("ts_iso","") or r.get("time_text",""))
                    if key in seen_main:
                        continue
                    # since フィルタ（アイテム単位）
                    if since_ts is not None and isinstance(r.get("ts"), int) and r["ts"] < since_ts:
                        continue
                    seen_main.add(key)
                    main_rows.append(r)
                    added_main += 1

                log(f"[main] batch={batch} 新規={added_main} 累計={len(main_rows)}")

                # ===== スレッド収集（複数対応 / 新規が尽きるまで複数パス）=====
                thread_new_in_batch = 0
                for _pass in range(pass_limit):
                    if stop_due_to_row_limit:
                        break
                    # 1) 時間上限（長いスレッドでハマらないよう各パス頭でも確認）
                    if max_minutes > 0:
                        elapsed_min = (time.monotonic() - start_monotonic) / 60.0
                        if elapsed_min >= max_minutes:
                            log(f"時間上限 {max_minutes} 分に達したため終了します。")
                            break

                    new_this_pass = 0
                    reply_buttons = page.locator('button[data-qa="reply_bar_count"]')
                    count = await reply_buttons.count()
                    if count == 0:
                        break

                    for i in range(count):
                        if stop_due_to_row_limit:
                            break
                        try:
                            btn = reply_buttons.nth(i)
                            await btn.scroll_into_view_if_needed()
                            await btn.click()
                            await page.wait_for_timeout(250)

                            # 右ペイン抽出（添付も含む）
                            thread_items = await extract_thread_messages(page)
                            if not thread_items:
                                await close_thread_pane(page)
                                continue

                            # root_ts で重複スレッドを判定
                            root_ts = thread_items[0].get("thread_root_ts")
                            if root_ts and isinstance(root_ts, int) and root_ts in seen_roots:
                                await close_thread_pane(page)
                                continue

                            # まだ未処理のスレッドなら保存（since フィルタも適用）
                            accepted = []
                            for it in thread_items:
                                if since_ts is not None and isinstance(it.get("ts"), int) and it["ts"] < since_ts:
                                    continue
                                accepted.append(it)

                            if root_ts and isinstance(root_ts, int):
                                seen_roots.add(root_ts)
                            thread_rows.extend(accepted)
                            if accepted:
                                new_this_pass += 1

                            await close_thread_pane(page)
                            await page.wait_for_timeout(150)

                            # 2) 件数上限（スレッド内で増えすぎないよう随時確認）
                            total_now = len(main_rows) + len(thread_rows)
                            if max_rows > 0 and total_now >= max_rows:
                                log(f"件数上限 {max_rows} 件に達したため終了します。")
                                stop_due_to_row_limit = True
                                break

                        except Exception:
                            # 要素が消える等は無視して続行
                            continue

                    thread_new_in_batch += new_this_pass
                    if stop_due_to_row_limit or new_this_pass == 0:
                        break

                if thread_new_in_batch:
                    log(f"[thread] batch={batch} 新規スレッド={thread_new_in_batch} 累計行={len(thread_rows)}")

                # 3) 件数上限
                total_now = len(main_rows) + len(thread_rows)
                if max_rows > 0 and total_now >= max_rows:
                    if not stop_due_to_row_limit:
                        log(f"件数上限 {max_rows} 件に達したため終了します。")
                    stop_due_to_row_limit = True
                    break

                # 4) stagnation 判定
                if total_now == prev_total:
                    stagnation += 1
                    if stagnation >= max_stagnation:
                        log(f"新規の収集が{max_stagnation}回続けて増えないため終了します。")
                        break
                else:
                    stagnation = 0
                    prev_total = total_now

                # さらに過去へ
                await scroll_up(page, steps=6, pause_ms=400)

            # ===== 保存先フォルダ（PCローカル時刻）を作成 =====
            base_path = Path(out_basename)
            out_parent = base_path.parent if str(base_path.parent) != "." else Path("out")
            out_stem   = base_path.name
            stamp = datetime.now().strftime("%Y_%m_%d_%H_%M")  # 実行開始ローカル時刻
            run_dir = out_parent / stamp
            run_dir.mkdir(parents=True, exist_ok=True)
            log(f"出力フォルダ: {run_dir}")

            # ===== JST 付与（JSONLにも保持）=====
            main_rows_jst   = decorate_with_jst(main_rows, is_thread=False)
            thread_rows_jst = decorate_with_jst(thread_rows, is_thread=True)

            # ===== 保存 =====
            out_main_jsonl   = run_dir / f"{out_stem}.jsonl"
            out_main_csv     = run_dir / f"{out_stem}.csv"
            out_thread_jsonl = run_dir / f"{out_stem}_threads.jsonl"
            out_thread_csv   = run_dir / f"{out_stem}_threads.csv"

            save_jsonl(out_main_jsonl, main_rows_jst)
            save_main_csv(out_main_csv, main_rows_jst)
            save_jsonl(out_thread_jsonl, thread_rows_jst)
            save_threads_csv(out_thread_csv, thread_rows_jst)

            log(f"保存: {out_main_jsonl} / {out_main_csv}")
            log(f"保存: {out_thread_jsonl} / {out_thread_csv}")

            # ===== 添付ダウンロード（メイン＋スレッド、並列）=====
            await download_attachments(
                context,
                main_rows_jst + thread_rows_jst,
                run_dir,
                dl_concurrency=dl_concurrency,
                dl_retries=dl_retries,
            )
            log("添付ダウンロード完了。")

        finally:
            await browser.close()

# =========================
# CLI
# =========================
def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="Slack チャンネル スクレイパー (JST保存・時刻別フォルダ / 自動ヘッドフル切替 / 添付並列DL)")
    ap.add_argument("--channel-url", required=True, help="例: https://workspace.slack.com/archives/CXXXX でも可（自動正規化）")
    ap.add_argument("--out", dest="out_basename", default="out/channel_export", help="出力ベース名（拡張子は自動付与）")
    ap.add_argument("--headful", action="store_true",
                    help="ヘッドフルで実行（未指定ならヘッドレス優先。必要時のみ自動ヘッドフル切替）")
    ap.add_argument("--stagnation", type=int, default=DEFAULT_MAX_STAGNATION,
                    help=f"新規増加が止まった回数の上限（デフォルト: {DEFAULT_MAX_STAGNATION}）")
    ap.add_argument("--max-batch", type=int, default=DEFAULT_MAX_BATCH,
                    help=f"総バッチ回数の上限（デフォルト: {DEFAULT_MAX_BATCH}）")
    ap.add_argument("--pass-limit", type=int, default=DEFAULT_PASS_LIMIT,
                    help=f"1バッチ内のスレッド探索パス上限（デフォルト: {DEFAULT_PASS_LIMIT}）")

    # 追加の停止条件
    ap.add_argument("--max-minutes", type=int, default=0, help="実行時間(分)の上限。0で無効")
    ap.add_argument("--max-rows", type=int, default=0, help="保存総件数(メイン+スレッド)の上限。0で無効")
    ap.add_argument("--since", type=str, default="", help="この日時以降のみ収集 (例: 2025-09-01T00:00:00+09:00 または 2025-09-01)")

    # ダウンロード並列設定
    ap.add_argument("--dl-concurrency", type=int, default=DEFAULT_DL_CONCURRENCY,
                    help=f"添付の同時ダウンロード数（デフォルト: {DEFAULT_DL_CONCURRENCY}）")
    ap.add_argument("--dl-retries", type=int, default=DEFAULT_DL_RETRIES,
                    help=f"添付の最大リトライ回数（デフォルト: {DEFAULT_DL_RETRIES}）")
    return ap.parse_args()

def parse_since_to_ts(since: str) -> Optional[int]:
    if not since:
        return None
    try:
        dt = datetime.fromisoformat(since)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return int(dt.timestamp())
    except Exception:
        log("since の形式を解釈できませんでした（例: 2025-09-01 または 2025-09-01T00:00:00+09:00）")
        return None

if __name__ == "__main__":
    args = parse_args()
    try:
        since_ts = parse_since_to_ts(args.since)
        asyncio.run(
            scrape_channel(
                channel_url=args.channel_url,
                out_basename=args.out_basename,
                headful_requested=args.headful,
                max_stagnation=args.stagnation,
                max_batch=args.max_batch,
                pass_limit=args.pass_limit,
                max_minutes=args.max_minutes,
                max_rows=args.max_rows,
                since_ts=since_ts,
                dl_concurrency=max(1, args.dl_concurrency),
                dl_retries=max(0, args.dl_retries),
            )
        )
    except KeyboardInterrupt:
        log("中断しました。")
