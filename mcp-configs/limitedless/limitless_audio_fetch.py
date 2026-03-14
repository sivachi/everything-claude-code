
import os
import time
import requests
import argparse
import subprocess
import sys
from datetime import datetime, date, timedelta
from dateutil import tz
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_BASE = "https://api.limitless.ai/v1"
API_KEY = os.environ.get("LIMITLESS_API_KEY")
TIMEZONE = "Asia/Tokyo"

if not API_KEY:
    raise SystemExit("環境変数 LIMITLESS_API_KEY を設定してください。")


def _get(path: str, params: dict = None):
    """429時のリトライ付きGET"""
    headers = {"X-API-Key": API_KEY}
    if path.startswith("/v1/"):
        path = path[3:]
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
                    print(f"  Warning: Max retries ({max_retries}) exceeded for 429 in _get.")
                    r.raise_for_status()
                wait = int(r.headers.get("Retry-After", "3"))
                time.sleep(min(wait, 10))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise e


def _download_audio(start_ms: int, end_ms: int, output_path: str):
    """音声ファイルをダウンロード"""
    headers = {"X-API-Key": API_KEY}
    params = {
        "startMs": start_ms,
        "endMs": end_ms,
        "audioSource": "pendant"
    }
    
    retries = 0
    max_retries = 5
    while True:
        try:
            r = requests.get(
                f"{API_BASE}/download-audio",
                params=params,
                headers=headers,
                timeout=60
            )
            if r.status_code == 429:
                retries += 1
                if retries > max_retries:
                    print(f"  Warning: Max retries ({max_retries}) exceeded for 429 in _download_audio.")
                    r.raise_for_status()
                wait = int(r.headers.get("Retry-After", "3"))
                time.sleep(min(wait, 10))
                continue
            r.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(r.content)
            return
        except requests.RequestException as e:
            raise e


def list_lifelogs_for_date(d: date):
    """指定日の全Lifelogを取得（タイムスタンプのみ）"""
    params = {
        "date": d.strftime("%Y-%m-%d"),
        "timezone": TIMEZONE,
        "direction": "asc",
        "limit": 10,
        "includeContents": "false"  # タイムスタンプだけ取得
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


def parse_iso_to_ms(iso_str: str) -> int:
    """ISO形式の日時をミリ秒タイムスタンプに変換"""
    if not iso_str:
        return 0
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def merge_audio_files(audio_files: list, output_path: str):
    """複数のOGGファイルを1つに結合（ffmpeg使用）"""
    if not audio_files:
        return
    
    # ffmpegのconcatフィルターを使用
    with open("concat_list.txt", "w") as f:
        for audio_file in audio_files:
            f.write(f"file '{audio_file}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.remove("concat_list.txt")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if isinstance(e, subprocess.CalledProcessError):
            print(f"ffmpeg エラー: {e.stderr.decode()}")
        # ffmpegがない、またはエラーの場合は単純結合（Chained Ogg）を行う
        print("  ffmpegが利用できないため、ファイルを単純結合します。")
        try:
            with open(output_path, "wb") as outfile:
                for f_path in audio_files:
                    with open(f_path, "rb") as infile:
                        outfile.write(infile.read())
        except Exception as merge_err:
             print(f"  結合エラー: {merge_err}")
        
        if os.path.exists("concat_list.txt"):
            os.remove("concat_list.txt")


def download_day_audio(target_day: date, force: bool = False):
    """指定日の音声をダウンロード"""
    # 出力ディレクトリ
    audio_dir = Path(__file__).parent / "audio"
    audio_dir.mkdir(exist_ok=True)
    
    # 最終出力ファイル
    final_output = audio_dir / f"limitless_audio_{target_day.isoformat()}.ogg"
    
    # スキップチェック
    if final_output.exists() and not force:
        print(f"既に存在: {final_output}")
        return
    
    print(f"Fetching audio for {target_day} ({TIMEZONE})...")
    
    # lifelogsを取得
    lifelogs = list(list_lifelogs_for_date(target_day))
    if not lifelogs:
        print("データが見つかりませんでした。")
        return
    
    # 各lifelogの音声をダウンロード
    temp_files = []
    max_duration_ms = 5 * 60 * 60 * 1000  # 5時間
    
    for i, lifelog in enumerate(lifelogs):
        start_time = lifelog.get("startTime")
        end_time = lifelog.get("endTime")
        
        if not start_time or not end_time:
            continue
        
        start_ms = parse_iso_to_ms(start_time)
        end_ms = parse_iso_to_ms(end_time)
        
        # 5時間制限チェック
        duration_ms = end_ms - start_ms
        if duration_ms <= 0:
            continue
        
        # 5時間を超える場合は分割
        chunks = []
        current_start = start_ms
        while current_start < end_ms:
            chunk_end = min(current_start + max_duration_ms, end_ms)
            chunks.append((current_start, chunk_end))
            current_start = chunk_end
        
        for j, (chunk_start, chunk_end) in enumerate(chunks):
            temp_file = audio_dir / f"temp_{target_day}_{i:03d}_{j:03d}.ogg"
            temp_files.append(temp_file)
            
            if temp_file.exists():
                print(f"  既存を使用: {temp_file.name}")
                continue
            
            print(f"  ダウンロード中 [{i+1}/{len(lifelogs)}] チャンク {j+1}/{len(chunks)}...")
            try:
                _download_audio(chunk_start, chunk_end, str(temp_file))
                time.sleep(0.5)  # レート制限対策
            except Exception as e:
                print(f"    エラー: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                continue
    
    if not temp_files:
        print("ダウンロードできる音声がありませんでした。")
        return
    
    # 音声ファイルを結合
    print(f"音声を結合中...")
    existing_files = [f for f in temp_files if f.exists()]
    
    if len(existing_files) == 1:
        # 1ファイルのみの場合はそのままコピー
        existing_files[0].rename(final_output)
    else:
        # 複数ファイルを結合
        merge_audio_files(existing_files, str(final_output))
        
        # 一時ファイルを削除
        for temp_file in existing_files:
            temp_file.unlink()
    
    print(f"保存完了: {final_output}")
    print(f"サイズ: {final_output.stat().st_size / 1024 / 1024:.1f} MB")


def find_missing_audio_dates(audio_dir: Path, start_date: date = None, end_date: date = None):
    """指定範囲内で、まだダウンロードされていない音声ファイルの日付を返す"""
    if start_date is None:
        # audioディレクトリ内の既存ファイルから最も古い日付を見つける
        existing_files = list(audio_dir.glob("limitless_audio_*.ogg"))
        if existing_files:
            dates = []
            for f in existing_files:
                try:
                    date_str = f.stem.replace("limitless_audio_", "")
                    dates.append(date.fromisoformat(date_str))
                except ValueError:
                    continue
            if dates:
                start_date = min(dates)
            else:
                # デフォルト：過去365日
                start_date = date.today() - timedelta(days=365)
        else:
            # デフォルト：過去365日
            start_date = date.today() - timedelta(days=365)
    
    if end_date is None:
        end_date = date.today()
    
    missing_dates = []
    current_date = start_date
    while current_date <= end_date:
        file_path = audio_dir / f"limitless_audio_{current_date.isoformat()}.ogg"
        if not file_path.exists():
            missing_dates.append(current_date)
        current_date += timedelta(days=1)
    
    return missing_dates


def main():
    parser = argparse.ArgumentParser(description="Limitless APIから音声ファイルをダウンロード")
    parser.add_argument(
        "--date",
        type=str,
        help="取得する日付 (YYYY-MM-DD形式)"
    )
    parser.add_argument(
        "--days-ago",
        type=int,
        help="何日前のデータを取得するか"
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存ファイルを上書き"
    )
    
    args = parser.parse_args()
    
    # 音声ディレクトリを作成
    audio_dir = Path(__file__).parent / "audio"
    audio_dir.mkdir(exist_ok=True)
    
    # 単一日付の処理
    if args.date:
        try:
            target_day = date.fromisoformat(args.date)
        except ValueError:
            print("エラー: 日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
        download_day_audio(target_day, force=args.force)
        return
    
    if args.days_ago:
        target_day = date.today() - timedelta(days=args.days_ago)
        download_day_audio(target_day, force=args.force)
        return
    
    # デフォルト動作：全ての未取得音声を自動でダウンロード
    start_date = None
    end_date = None
    
    if args.start_date:
        try:
            start_date = date.fromisoformat(args.start_date)
        except ValueError:
            print("エラー: 開始日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
    else:
        # デフォルト：過去365日分（または--days-backで指定された日数）
        start_date = date.today() - timedelta(days=args.days_back)
    
    if args.end_date:
        try:
            end_date = date.fromisoformat(args.end_date)
        except ValueError:
            print("エラー: 終了日付形式が正しくありません。YYYY-MM-DD形式で指定してください。")
            return
    else:
        # デフォルト：今日まで
        end_date = date.today()
    
    missing_dates = find_missing_audio_dates(audio_dir, start_date, end_date)
    
    if not missing_dates:
        print(f"{start_date} から {end_date} までの全音声ファイルがダウンロード済みです。")
        return
    
    print(f"=== Limitless音声自動ダウンロード開始 ===")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"未取得: {len(missing_dates)}件")
    print(f"予想時間: 約{len(missing_dates) * 2 / 60:.1f}分")
    print("=" * 40)
    
    success_count = 0
    failed_dates = []
    
    for i, target_day in enumerate(missing_dates, 1):
        print(f"\n[{i}/{len(missing_dates)}] {target_day} を処理中...")
        try:
            download_day_audio(target_day, force=args.force)
            success_count += 1
        except Exception as e:
            print(f"  → エラー: {e}")
            failed_dates.append(target_day)
        
        # APIレート制限を考慮
        if i < len(missing_dates):  # 最後以外は待機
            time.sleep(1.0)
    
    print("\n" + "=" * 40)
    print(f"=== ダウンロード完了 ===")
    print(f"成功: {success_count}/{len(missing_dates)} 件")
    if failed_dates:
        print(f"失敗した日付: {', '.join(str(d) for d in failed_dates)}")
    print("=" * 40)
    if failed_dates:
        print(f"失敗した日付: {', '.join(str(d) for d in failed_dates)}")
        sys.exit(1)


if __name__ == "__main__":
    main()