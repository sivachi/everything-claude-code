"""
Screenshot Processing and Formatting Module

【使用方法】
from screenshot_processor import ScreenshotProcessor

# インスタンス作成
processor = ScreenshotProcessor()

# スクリーンショットを解析
result = processor.analyze_screenshot("./screenshots/example.png")

# スクリーンショットをリサイズ
processor.resize_image(
    input_path="./screenshots/example.png",
    output_path="./screenshots/example_small.png",
    max_width=800
)

# スクリーンショットに情報を追加
processor.add_metadata(
    image_path="./screenshots/example.png",
    output_path="./screenshots/example_annotated.png",
    metadata={"url": "https://example.com", "timestamp": "2024-01-01 12:00:00"}
)

【処理内容】
1. スクリーンショット画像の読み込み
2. 画像の解析・処理（リサイズ、クロップ、メタデータ追加）
3. 画像の最適化と保存
4. 解析結果のレポート生成
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import json
from datetime import datetime
import hashlib


class ScreenshotProcessor:
    """
    スクリーンショット画像を処理・整形するクラス
    """

    def __init__(self):
        """初期化"""
        self.supported_formats = [".png", ".jpg", ".jpeg", ".webp"]

    def analyze_screenshot(self, image_path: str) -> Dict:
        """
        スクリーンショットの基本情報を解析

        Input:
            image_path: 画像ファイルのパス

        Output:
            Dict: 画像の解析結果
                {
                    "path": "...",
                    "size": {"width": 1280, "height": 720},
                    "format": "PNG",
                    "file_size_kb": 123.45,
                    "hash": "...",
                    "analyzed_at": "2024-01-01 12:00:00"
                }
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with Image.open(path) as img:
            # ファイルハッシュ計算
            file_hash = self._calculate_file_hash(path)

            result = {
                "path": str(path.absolute()),
                "filename": path.name,
                "size": {
                    "width": img.width,
                    "height": img.height
                },
                "format": img.format,
                "mode": img.mode,
                "file_size_kb": round(path.stat().st_size / 1024, 2),
                "hash": file_hash,
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        return result

    def resize_image(
        self,
        input_path: str,
        output_path: str,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        quality: int = 85
    ) -> str:
        """
        画像をリサイズ

        Input:
            input_path: 入力画像パス
            output_path: 出力画像パス
            max_width: 最大幅（Noneの場合はアスペクト比を維持）
            max_height: 最大高さ（Noneの場合はアスペクト比を維持）
            quality: 保存品質 (1-100)

        Output:
            str: 保存された画像のパス
        """
        with Image.open(input_path) as img:
            original_size = img.size

            # リサイズ計算
            new_size = self._calculate_resize(
                original_size,
                max_width,
                max_height
            )

            # リサイズ実行
            if new_size != original_size:
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # 出力ディレクトリ作成
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 保存
            img.save(output_path, quality=quality, optimize=True)

        return str(Path(output_path).absolute())

    def crop_image(
        self,
        input_path: str,
        output_path: str,
        crop_box: Tuple[int, int, int, int]
    ) -> str:
        """
        画像をクロップ

        Input:
            input_path: 入力画像パス
            output_path: 出力画像パス
            crop_box: クロップ領域 (left, top, right, bottom)

        Output:
            str: 保存された画像のパス
        """
        with Image.open(input_path) as img:
            cropped = img.crop(crop_box)

            # 出力ディレクトリ作成
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            cropped.save(output_path)

        return str(Path(output_path).absolute())

    def add_metadata(
        self,
        image_path: str,
        output_path: str,
        metadata: Dict,
        position: str = "bottom",
        padding: int = 20,
        font_size: int = 16,
        bg_color: Tuple[int, int, int, int] = (0, 0, 0, 180),
        text_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> str:
        """
        画像にメタデータを追加（テキストオーバーレイ）

        Input:
            image_path: 入力画像パス
            output_path: 出力画像パス
            metadata: 追加するメタデータ
            position: テキスト位置 ("top", "bottom")
            padding: パディング
            font_size: フォントサイズ
            bg_color: 背景色 (R, G, B, A)
            text_color: テキスト色 (R, G, B)

        Output:
            str: 保存された画像のパス
        """
        with Image.open(image_path) as img:
            # RGBA変換
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # メタデータテキスト作成
            text_lines = [f"{k}: {v}" for k, v in metadata.items()]

            # オーバーレイ用の透明レイヤー作成
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            # フォント設定（デフォルトフォント使用）
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()

            # テキスト領域サイズ計算
            line_height = font_size + 5
            text_height = len(text_lines) * line_height + padding * 2
            text_width = img.width

            # 背景矩形描画
            if position == "bottom":
                y_start = img.height - text_height
            else:  # top
                y_start = 0

            draw.rectangle(
                [(0, y_start), (text_width, y_start + text_height)],
                fill=bg_color
            )

            # テキスト描画
            y_offset = y_start + padding
            for line in text_lines:
                draw.text(
                    (padding, y_offset),
                    line,
                    fill=text_color,
                    font=font
                )
                y_offset += line_height

            # 画像を合成
            result = Image.alpha_composite(img, overlay)

            # RGB変換して保存
            result = result.convert('RGB')

            # 出力ディレクトリ作成
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            result.save(output_path)

        return str(Path(output_path).absolute())

    def compare_screenshots(
        self,
        image1_path: str,
        image2_path: str,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        2つのスクリーンショットを比較

        Input:
            image1_path: 画像1のパス
            image2_path: 画像2のパス
            output_path: 差分画像の保存パス（Noneの場合は保存しない）

        Output:
            Dict: 比較結果
                {
                    "identical": bool,
                    "difference_percentage": float,
                    "size_match": bool,
                    "diff_image_path": str or None
                }
        """
        with Image.open(image1_path) as img1, Image.open(image2_path) as img2:
            # サイズチェック
            size_match = img1.size == img2.size

            if not size_match:
                return {
                    "identical": False,
                    "difference_percentage": 100.0,
                    "size_match": False,
                    "diff_image_path": None
                }

            # ピクセル比較
            img1_data = list(img1.convert('RGB').getdata())
            img2_data = list(img2.convert('RGB').getdata())

            total_pixels = len(img1_data)
            different_pixels = sum(1 for p1, p2 in zip(img1_data, img2_data) if p1 != p2)

            difference_percentage = (different_pixels / total_pixels) * 100
            identical = different_pixels == 0

            # 差分画像生成
            diff_image_path = None
            if output_path and not identical:
                diff_image_path = self._create_diff_image(
                    img1, img2, output_path
                )

            return {
                "identical": identical,
                "difference_percentage": round(difference_percentage, 2),
                "size_match": size_match,
                "different_pixels": different_pixels,
                "total_pixels": total_pixels,
                "diff_image_path": diff_image_path
            }

    def generate_report(
        self,
        screenshots: List[Dict],
        output_path: str
    ) -> str:
        """
        スクリーンショット解析レポートを生成

        Input:
            screenshots: スクリーンショット情報のリスト
            output_path: レポート保存パス (JSON)

        Output:
            str: 保存されたレポートのパス
        """
        report = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_screenshots": len(screenshots),
            "screenshots": screenshots
        }

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return str(output_path_obj.absolute())

    def _calculate_resize(
        self,
        original_size: Tuple[int, int],
        max_width: Optional[int],
        max_height: Optional[int]
    ) -> Tuple[int, int]:
        """リサイズ後のサイズを計算"""
        width, height = original_size

        if max_width is None and max_height is None:
            return original_size

        if max_width and max_height:
            # 両方指定された場合、アスペクト比を維持して収まるように
            ratio = min(max_width / width, max_height / height)
        elif max_width:
            ratio = max_width / width
        else:  # max_height
            ratio = max_height / height

        new_width = int(width * ratio)
        new_height = int(height * ratio)

        return (new_width, new_height)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _create_diff_image(
        self,
        img1: Image.Image,
        img2: Image.Image,
        output_path: str
    ) -> str:
        """差分画像を作成"""
        img1_rgb = img1.convert('RGB')
        img2_rgb = img2.convert('RGB')

        diff = Image.new('RGB', img1.size)
        diff_pixels = diff.load()

        pixels1 = img1_rgb.load()
        pixels2 = img2_rgb.load()

        for y in range(img1.height):
            for x in range(img1.width):
                p1 = pixels1[x, y]
                p2 = pixels2[x, y]

                if p1 != p2:
                    # 差分がある部分を赤で表示
                    diff_pixels[x, y] = (255, 0, 0)
                else:
                    # 同じ部分はグレースケール
                    gray = int(sum(p1) / 3)
                    diff_pixels[x, y] = (gray, gray, gray)

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        diff.save(output_path)
        return str(output_path_obj.absolute())
