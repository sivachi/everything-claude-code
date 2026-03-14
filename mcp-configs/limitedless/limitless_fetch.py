import os
import time
import requests
import argparse
from datetime import datetime, date, timedelta
import sys
from datetime import datetime, date, timedelta
from dateutil import tz

try:
    # Load variables from .env if present
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # Fallback if python-dotenv is not installed; env must be set externally
    pass

API_BASE = "https://api.limitless.ai/v1"
API_KEY = os.environ.get("LIMITLESS_API_KEY")
TIMEZONE = "Asia/Tokyo"  # 好みで変更

if not API_KEY:
    raise SystemExit("環境変数 LIMITLESS_API_KEY を設定してください。")


def _get(path: str, params: dict):
    """429時のリトライ付きGET"""
    headers = {"X-API-Key": API_KEY}  # LimitlessはAPIキーをX-API-Keyヘッダで渡す
    # 正規化: API_BASEは/v1を含むため、pathは先頭に/v1を付けない
    if path.startswith("/v1/"):
        path = path[3:]
    retries = 0
    max_retries = 5
    while True:
        try:
            r = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                retries += 1
                if retries > max_retries:
                    print(f"  Warning: Max retries ({max_retries}) exceeded for 429.")
                    r.raise_for_status()
                wait = int(r.headers.get("Retry-After", "3"))
                print(f"  Rate limited (429). Retrying in {wait}s...")
                time.sleep(min(wait, 10))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            # 接続エラーなどもリトライしたい場合はここで処理するが、今回は429ループ対策が主
            raise e


def list_lifelogs_for_date(d: date, include_contents: bool = True):
    """指定日の全Lifelogをカーソルでページング取得"""
    params = {
        "date": d.strftime("%Y-%m-%d"),
        "timezone": TIMEZONE,
        "direction": "asc",  # 時系列に並べる
        "limit": 10,  # APIの最大
        "includeContents": "true" if include_contents else "false",
    }
    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        data = _get("/lifelogs", params)
        lifelogs = data.get("data", {}).get("lifelogs", [])
        for ll in lifelogs:
            yield ll
        cursor = data.get("meta", {}).get("lifelogs", {}).get("nextCursor")
        if not cursor:
            break


def _iter_segments(contents):
    """入れ子のchildrenをフラットにして発言テキストを取り出す"""
    if not contents:
        return
    stack = list(contents)
    while stack:
        seg = stack.pop(0)
        # type: heading1/heading2/blockquoteなどが来る。contentが本文。
        text = (seg.get("content") or "").strip()
        if text:
            yield {
                "startTime": seg.get("startTime"),
                "endTime": seg.get("endTime"),
                "speaker": seg.get("speakerName") or "",
                "text": text,
            }
        # 子要素も走査
        children = seg.get("children") or []
        if children:
            stack[0:0] = children  # 先頭に挿入して順序維持


def _fmt_ts(iso_str: str, tzname: str = TIMEZONE):
    if not iso_str:
        return ""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(tz.gettz(tzname)).strftime("%H:%M:%S")


def lifelog_to_plaintext(lifelog: dict) -> str:
    """1件のlifelogから「[HH:MM:SS] Speaker: text」形式のプレーンテキストへ"""
    lines = []
    title = lifelog.get("title") or ""
    if title:
        lines.append(f"# {title}")
    for seg in _iter_segments(lifelog.get("contents")):
        ts = _fmt_ts(seg["startTime"])
        spk = f'{seg["speaker"]}: ' if seg["speaker"] else ""
        lines.append(f"[{ts}] {spk}{seg['text']}")
    if not lines:  # contentsがない場合はmarkdownだけでも
        md = (lifelog.get("markdown") or "").strip()
        if md:
            lines.append(md)
    return "\n".join(lines)


def find_missing_dates(data_dir: str, start_date: date = None, end_date: date = None):
    """指定範囲内で、まだダウンロードされていない日付を返す"""
    if start_date is None:
        # dataディレクトリ内の既存ファイルから最も古い日付を見つける
        existing_files = [f for f in os.listdir(data_dir) if f.startswith("limitless_transcript_") and f.endswith(".txt")]
        if existing_files:
            dates = []
            for f in existing_files:
                try:
                    date_str = f.replace("limitless_transcript_", "").replace(".txt", "")
                    dates.append(date.fromisoformat(date_str))
                except ValueError:
                    continue
            if dates:
                start_date = min(dates)
            else:
                # 過去30日分をデフォルトとする
                start_date = date.today() - timedelta(days=30)
        else:
            # 過去30日分をデフォルトとする
            start_date = date.today() - timedelta(days=30)
    
    if end_date is None:
        end_date = date.today()
    
    missing_dates = []
    current_date = start_date
    while current_date <= end_date:
        file_path = os.path.join(data_dir, f"limitless_transcript_{current_date.isoformat()}.txt")
        if not os.path.exists(file_path):
            missing_dates.append(current_date)
        current_date += timedelta(days=1)
    
    return missing_dates


def download_single_date(target_day: date, data_dir: str):
    """指定日のデータをダウンロード"""
    out_path = os.path.join(data_dir, f"limitless_transcript_{target_day.isoformat()}.txt")
    
    print(f"Fetching lifelogs for {target_day} ({TIMEZONE}) ...")
    texts = []
    for lifelog in list_lifelogs_for_date(target_day, include_contents=True):
        texts.append(lifelog_to_plaintext(lifelog))

    result = "\n\n---\n\n".join(t for t in texts if t.strip())
    if not result:
        print(f"  → {target_day}: トランスクリプトは見つかりませんでした。")
        # 空ファイルを作成して、次回スキップされるようにする
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("")
        return False

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"  → 保存しました: {out_path}")
    return True


def main():
    # コマンドライン引数を解析
    parser = argparse.ArgumentParser(description="Limitless APIから指定日のトランスクリプトを取得")
    parser.add_argument(
        "--date", 
        type=str, 
        help="取得する日付 (YYYY-MM-DD形式)。指定しない場合は全ての未取得日を処理"
    )
    parser.add_argument(
        "--days-ago",
        type=int,
        help="何日前のデータを取得するか (例: 1 = 昨日)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="開始日付 (YYYY-MM-DD形式)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="終了日付 (YYYY-MM-DD形式)"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="何日前までのデータを取得するか (デフォルト: 365日)"
    )
    args = parser.parse_args()
    
    # データディレクトリを作成（存在しない場合）
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # 単一日付の処理
    if args.date:
        try:
            target_day = date.fromisoformat(args.date)
        except ValueError:
            print(f"エラー: 日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
        download_single_date(target_day, data_dir)
        return
    
    if args.days_ago:
        target_day = date.today() - timedelta(days=args.days_ago)
        download_single_date(target_day, data_dir)
        return
    
    # デフォルト動作：全ての未取得日付を自動でダウンロード
    start_date = None
    end_date = None
    
    if args.start_date:
        try:
            start_date = date.fromisoformat(args.start_date)
        except ValueError:
            print(f"エラー: 開始日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
    else:
        # デフォルト：過去365日分（または--days-backで指定された日数）
        start_date = date.today() - timedelta(days=args.days_back)
    
    if args.end_date:
        try:
            end_date = date.fromisoformat(args.end_date)
        except ValueError:
            print(f"エラー: 終了日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
    else:
        # デフォルト：今日まで
        end_date = date.today()
    
    missing_dates = find_missing_dates(data_dir, start_date, end_date)
    
    if not missing_dates:
        print(f"{start_date} から {end_date} までの全データがダウンロード済みです。")
        return
    
    print(f"=== Limitless自動ダウンロード開始 ===")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"未取得: {len(missing_dates)}件")
    print(f"予想時間: 約{len(missing_dates) * 0.5 / 60:.1f}分")
    print("=" * 40)
    
    success_count = 0
    failed_dates = []
    
    for i, target_day in enumerate(missing_dates, 1):
        print(f"\n[{i}/{len(missing_dates)}] {target_day} を処理中...")
        try:
            if download_single_date(target_day, data_dir):
                success_count += 1
        except Exception as e:
            print(f"  → エラー: {e}")
            failed_dates.append(target_day)
        
        # APIレート制限を考慮（少し短縮して高速化）
        time.sleep(0.3)
    
    print("\n" + "=" * 40)
    print(f"=== ダウンロード完了 ===")
    print(f"成功: {success_count}/{len(missing_dates)} 件")
    if failed_dates:
        print(f"失敗した日付: {', '.join(str(d) for d in failed_dates)}")
        sys.exit(1)
    print("=" * 40)


if __name__ == "__main__":
    main()

