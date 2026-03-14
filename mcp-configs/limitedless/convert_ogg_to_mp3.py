import os
import subprocess
from pathlib import Path

def convert_ogg_to_mp3(audio_dir: Path):
    """
    audio_dir内の.oggファイルを.mp3に変換する
    """
    ogg_files = list(audio_dir.glob("*.ogg"))
    total = len(ogg_files)
    
    if total == 0:
        print("No .ogg files found to convert.")
        return

    print(f"Found {total} .ogg files. Starting conversion...")
    
    success_count = 0
    
    for i, ogg_file in enumerate(ogg_files, 1):
        mp3_file = ogg_file.with_suffix(".mp3")
        
        if mp3_file.exists():
            print(f"[{i}/{total}] SKIP: {mp3_file.name} (Already exists)")
            continue
            
        print(f"[{i}/{total}] Converting: {ogg_file.name} -> {mp3_file.name}")
        
        try:
            # ffmpeg command
            # -i: input file
            # -c:a libmp3lame: audio codec
            # -q:a 2: VBR quality level 2 (standard, approx 170-210kbps)
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(ogg_file),
                "-c:a", "libmp3lame",
                "-q:a", "2",
                str(mp3_file)
            ]
            
            subprocess.run(cmd, check=True)
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            print(f"  FAILED: {ogg_file.name}")
            print(f"  Error: {e}")
            
    print("=" * 40)
    print(f"Conversion complete.")
    print(f"Converted: {success_count}/{total}")
    print("=" * 40)

def main():
    audio_dir = Path(__file__).parent / "audio"
    if not audio_dir.exists():
        print(f"Directory not found: {audio_dir}")
        return

    convert_ogg_to_mp3(audio_dir)

if __name__ == "__main__":
    main()
