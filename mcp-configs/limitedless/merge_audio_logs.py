import os
import re
import subprocess
from pathlib import Path
from collections import defaultdict

def get_audio_files_by_date(audio_dir: Path):
    """
    audioディレクトリ内のtempファイルを取得し、日付ごとにグループ化する
    戻り値: {date_str: [file_path1, file_path2, ...]}
    """
    pattern = re.compile(r"temp_(\d{4}-\d{2}-\d{2})_.*\.ogg")
    files_by_date = defaultdict(list)
    
    for f in audio_dir.glob("temp_*.ogg"):
        match = pattern.match(f.name)
        if match:
            date_str = match.group(1)
            files_by_date[date_str].append(f)
            
    return files_by_date

def merge_audio_files(audio_files: list, output_path: str):
    """複数のOGGファイルを1つに結合（ffmpeg使用）"""
    if not audio_files:
        return False
    
    # ファイル名でソート（タイムスタンプ順、またはインデックス順になることを期待）
    # ファイル名例: temp_2025-11-17_001_000.ogg
    # 日付の後の数字でソートされるようにする
    audio_files.sort(key=lambda x: x.name)

    list_file_path = "concat_list_temp.txt"
    try:
        with open(list_file_path, "w") as f:
            for audio_file in audio_files:
                # ffmpegのconcat demuxer用に絶対パスを使用し、エスケープ処理
                safe_path = str(audio_file.absolute()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"FAILED: {output_path}")
        print(f"  ffmpeg Error: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"FAILED: {output_path}")
        print(f"  Error: {e}")
        return False
    finally:
        if os.path.exists(list_file_path):
            os.remove(list_file_path)

def main():
    audio_dir = Path(__file__).parent / "audio"
    if not audio_dir.exists():
        print(f"Directory not found: {audio_dir}")
        return

    print(f"Scanning {audio_dir}...")
    files_by_date = get_audio_files_by_date(audio_dir)
    
    total_dates = len(files_by_date)
    print(f"Found {total_dates} dates to process.")
    
    processed_count = 0
    
    for date_str, files in files_by_date.items():
        if not files:
            continue
            
        target_output = audio_dir / f"limitless_audio_{date_str}.ogg"
        
        # 既に出力ファイルが存在する場合の処理
        # ここでは、「既存ファイルがある場合はマージしない」または「上書きする」などの方針が必要
        # ユーザーのリクエストは「同じ日付のファイルは一つの音声データにして」なので、
        # 未マージのtempファイルがあるならマージすべきだが、既存の完成ファイルとどうマージするかは不明確
        # 安全のため、既存ファイルがある場合はスキップし、ユーザーに通知する形にするか、
        # もしくは既存ファイルも含めてマージするか。
        # 今回は、tempファイルのみをマージして新規作成する。既存がある場合はスキップする。
        
        if target_output.exists():
            print(f"SKIP: {date_str} (Output file already exists: {target_output.name})")
            # tempファイルの扱いをどうするか？
            # 既にマージ済みと思われるので、何もしない（削除もしない、安全のため）
            continue

        print(f"Processing {date_str} ({len(files)} files)...")
        if merge_audio_files(files, str(target_output)):
            print(f"SUCCESS: Created {target_output.name}")
            # マージ成功したらtempファイルを削除
            for f in files:
                f.unlink()
            processed_count += 1
        
    print(f"Done. Processed {processed_count}/{total_dates} dates.")

if __name__ == "__main__":
    main()
