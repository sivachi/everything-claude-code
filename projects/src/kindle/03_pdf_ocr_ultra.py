#!/usr/bin/env python3
"""
PDF OCR Ultra - PDFに検索可能な超薄いテキストレイヤーを追加する最強OCRツール
日本語と多言語文書に最適化

主な機能:
- 4つのプリセット (ultra, balanced, fast, japanese)
- 画像の超強化処理（ノイズ除去、シャープ化、コントラスト調整）
- 透明テキストレイヤーでPDFを検索可能にする
- マルチスレッド並列処理で高速化
- テキスト抽出とメタデータの保存

使用例:
# 最高品質でOCR処理（時間がかかるが品質最高）
python3 pdf_ocr_ultra.py input.pdf --preset ultra

# バランス型処理（推奨）
python3 pdf_ocr_ultra.py input.pdf --preset balanced

# 高速処理（品質は低め）
python3 pdf_ocr_ultra.py input.pdf --preset fast

# 日本語縦書き文書用
python3 pdf_ocr_ultra.py japanese_doc.pdf --preset japanese

# テキストも別ファイルに保存
python3 pdf_ocr_ultra.py input.pdf --save-text

# 8スレッドで並列処理
python3 pdf_ocr_ultra.py input.pdf --threads 8

# 中国語+英語+日本語
python3 pdf_ocr_ultra.py input.pdf -l jpn+eng+chi_sim

プリセット詳細:
- ultra: 600 DPI, 全強化処理 (最高品質、最も遅い)
- balanced: 300 DPI, 適度な強化 (品質と速度のバランス)
- fast: 200 DPI, 強化処理なし (高速、品質低め)
- japanese: 400 DPI, 縦書き最適化 (日本語文書専用)
"""

import os
import sys
import argparse
import tempfile
import shutil
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import logging
from datetime import datetime
import multiprocessing as mp
from functools import partial

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import pypdf
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
import cv2
import numpy as np
from tqdm import tqdm
import fitz  # PyMuPDF for better text extraction


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UltraOCRProcessor:
    """Advanced OCR processor with ultra-thin text layer"""
    
    PRESETS = {
        'ultra': {
            'dpi': 600,
            'enhance': True,
            'denoise': True,
            'sharpen': True,
            'contrast': 1.2,
            'brightness': 1.0,
            'psm': 6,
            'oem': 3
        },
        'fast': {
            'dpi': 200,
            'enhance': False,
            'denoise': False,
            'sharpen': False,
            'contrast': 1.0,
            'brightness': 1.0,
            'psm': 3,
            'oem': 3
        },
        'balanced': {
            'dpi': 300,
            'enhance': True,
            'denoise': True,
            'sharpen': False,
            'contrast': 1.1,
            'brightness': 1.0,
            'psm': 6,
            'oem': 3
        },
        'japanese': {
            'dpi': 400,
            'enhance': True,
            'denoise': True,
            'sharpen': True,
            'contrast': 1.3,
            'brightness': 1.1,
            'psm': 5,  # Vertical text
            'oem': 1   # LSTM only
        }
    }
    
    def __init__(self, language='jpn+eng', preset='balanced', threads=None):
        """
        Initialize Ultra OCR processor
        
        Args:
            language: Tesseract language code
            preset: Processing preset (ultra, fast, balanced, japanese)
            threads: Number of threads for parallel processing
        """
        self.language = language
        self.preset_name = preset
        self.settings = self.PRESETS.get(preset, self.PRESETS['balanced'])
        self.threads = threads or mp.cpu_count()
        
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check for required dependencies"""
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            logger.info("Installing: brew install tesseract tesseract-lang")
            sys.exit(1)
        
        try:
            import fitz
        except ImportError:
            logger.info("Installing PyMuPDF for better text handling...")
            os.system("pip install PyMuPDF")
    
    def ultra_enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Ultra enhancement for maximum OCR accuracy
        
        Args:
            image: Input image
            
        Returns:
            Enhanced image
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        if self.settings['denoise']:
            gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        if self.settings['sharpen']:
            kernel = np.array([[0, -1, 0],
                              [-1, 5, -1],
                              [0, -1, 0]])
            gray = cv2.filter2D(gray, -1, kernel)
        
        alpha = self.settings['contrast']
        beta = int((self.settings['brightness'] - 1) * 127)
        gray = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, morph_kernel)
        
        scale_factor = 2
        height, width = binary.shape
        binary = cv2.resize(binary, (width * scale_factor, height * scale_factor), 
                           interpolation=cv2.INTER_CUBIC)
        
        return binary
    
    def detect_text_orientation(self, image: Image.Image) -> Dict[str, Any]:
        """
        Detect text orientation and script
        
        Args:
            image: Input image
            
        Returns:
            Dictionary with orientation info
        """
        try:
            osd = pytesseract.image_to_osd(image)
            orientation = {}
            for line in osd.split('\n'):
                if 'Orientation in degrees' in line:
                    orientation['rotation'] = int(line.split(':')[-1].strip())
                elif 'Orientation confidence' in line:
                    orientation['confidence'] = float(line.split(':')[-1].strip())
                elif 'Script' in line and 'confidence' not in line:
                    orientation['script'] = line.split(':')[-1].strip()
            return orientation
        except Exception as e:
            logger.debug(f"Could not detect orientation: {e}")
            return {'rotation': 0, 'confidence': 0, 'script': 'Unknown'}
    
    def process_page_ultra(self, image: Image.Image, page_num: int) -> Dict[str, Any]:
        """
        Process page with ultra-thin text layer
        
        Args:
            image: Page image
            page_num: Page number
            
        Returns:
            Dictionary with text and metadata
        """
        try:
            orientation = self.detect_text_orientation(image)
            
            if orientation['rotation'] != 0:
                image = image.rotate(-orientation['rotation'], expand=True)
            
            if self.settings['enhance']:
                img_array = np.array(image)
                enhanced = self.ultra_enhance(img_array)
                image = Image.fromarray(enhanced)
            
            psm = self.settings['psm']
            if 'Japanese' in orientation.get('script', ''):
                psm = 5  # Vertical text mode
            
            custom_config = f'--oem {self.settings["oem"]} --psm {psm} -c preserve_interword_spaces=1'
            
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=custom_config
            )
            
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=pytesseract.Output.DICT,
                config=custom_config
            )
            
            confidence_scores = [conf for conf in data['conf'] if conf > 0]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            return {
                'text': text,
                'page_num': page_num,
                'confidence': avg_confidence,
                'word_count': len(text.split()),
                'char_count': len(text),
                'orientation': orientation,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"Error processing page {page_num}: {e}")
            return {
                'text': '',
                'page_num': page_num,
                'confidence': 0,
                'word_count': 0,
                'char_count': 0,
                'orientation': {},
                'data': {}
            }
    
    def create_ultra_thin_pdf(self, images: List[Image.Image], 
                             page_data: List[Dict], 
                             output_path: str):
        """
        Create PDF with ultra-thin invisible text layer
        
        Args:
            images: List of page images
            page_data: List of page data dictionaries
            output_path: Output path
        """
        try:
            doc = fitz.open()
            
            for image, data in zip(images, page_data):
                img_bytes = image.convert('RGB').tobytes()
                img_width, img_height = image.size
                
                page = doc.new_page(width=img_width, height=img_height)
                
                page.insert_image(page.rect, stream=img_bytes)
                
                if data['data'] and 'text' in data['data']:
                    for i, word in enumerate(data['data']['text']):
                        if word.strip() and data['data']['conf'][i] > 30:
                            x = data['data']['left'][i]
                            y = data['data']['top'][i]
                            w = data['data']['width'][i]
                            h = data['data']['height'][i]
                            
                            rect = fitz.Rect(x, y, x + w, y + h)
                            
                            page.insert_textbox(
                                rect,
                                word,
                                fontsize=1,  # Ultra-thin
                                color=(1, 1, 1),  # White (invisible)
                                fill=(1, 1, 1),  # White background
                                overlay=False
                            )
            
            doc.save(output_path, deflate=True, garbage=4)
            doc.close()
            
            logger.info(f"Created ultra-thin searchable PDF: {output_path}")
            
        except Exception as e:
            logger.error(f"Error creating ultra-thin PDF: {e}")
            self._fallback_pdf_creation(images, page_data, output_path)
    
    def _fallback_pdf_creation(self, images: List[Image.Image], 
                               page_data: List[Dict], 
                               output_path: str):
        """Fallback PDF creation method"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_pages = []
                
                for i, (image, data) in enumerate(zip(images, page_data)):
                    page_pdf = os.path.join(temp_dir, f"page_{i}.pdf")
                    
                    custom_config = f'--oem {self.settings["oem"]} --psm {self.settings["psm"]}'
                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                        image,
                        lang=self.language,
                        config=custom_config,
                        extension='pdf'
                    )
                    
                    with open(page_pdf, 'wb') as f:
                        f.write(pdf_bytes)
                    
                    pdf_pages.append(page_pdf)
                
                writer = PdfWriter()
                for page_pdf in pdf_pages:
                    reader = PdfReader(page_pdf)
                    for page in reader.pages:
                        writer.add_page(page)
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
        except Exception as e:
            logger.error(f"Fallback PDF creation failed: {e}")
            raise
    
    def process_pdf_ultra(self, input_path: str, 
                         output_path: Optional[str] = None,
                         save_text: bool = False) -> Tuple[bool, str, Dict]:
        """
        Process PDF with ultra settings
        
        Args:
            input_path: Input PDF path
            output_path: Output PDF path
            save_text: Whether to save extracted text
            
        Returns:
            Tuple of (success, output_path, metadata)
        """
        if not os.path.exists(input_path):
            logger.error(f"File not found: {input_path}")
            return False, "", {}
        
        if output_path is None:
            base_name = Path(input_path).stem
            output_path = str(Path(input_path).parent / f"{base_name}_ultra_ocr.pdf")
        
        try:
            start_time = datetime.now()
            logger.info(f"Processing with {self.preset_name} preset: {input_path}")
            
            images = convert_from_path(input_path, dpi=self.settings['dpi'])
            logger.info(f"Converted {len(images)} pages at {self.settings['dpi']} DPI")
            
            if self.threads > 1:
                logger.info(f"Using {self.threads} threads for parallel processing")
                with mp.Pool(self.threads) as pool:
                    process_func = partial(self.process_page_ultra)
                    page_data = list(tqdm(
                        pool.starmap(process_func, [(img, i+1) for i, img in enumerate(images)]),
                        total=len(images),
                        desc="OCR Processing"
                    ))
            else:
                page_data = []
                for i, image in enumerate(tqdm(images, desc="OCR Processing")):
                    data = self.process_page_ultra(image, i + 1)
                    page_data.append(data)
            
            logger.info("Creating ultra-thin searchable PDF...")
            self.create_ultra_thin_pdf(images, page_data, output_path)
            
            if save_text:
                text_path = output_path.replace('.pdf', '.txt')
                with open(text_path, 'w', encoding='utf-8') as f:
                    for data in page_data:
                        f.write(f"--- Page {data['page_num']} ---\n")
                        f.write(data['text'])
                        f.write("\n\n")
                logger.info(f"Saved extracted text: {text_path}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            metadata = {
                'input_file': input_path,
                'output_file': output_path,
                'pages': len(images),
                'preset': self.preset_name,
                'language': self.language,
                'dpi': self.settings['dpi'],
                'processing_time': processing_time,
                'avg_confidence': sum(d['confidence'] for d in page_data) / len(page_data),
                'total_words': sum(d['word_count'] for d in page_data),
                'total_chars': sum(d['char_count'] for d in page_data),
                'file_size_mb': os.path.getsize(output_path) / (1024 * 1024)
            }
            
            metadata_path = output_path.replace('.pdf', '_metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processing complete in {processing_time:.2f} seconds")
            logger.info(f"Average confidence: {metadata['avg_confidence']:.2f}%")
            
            return True, output_path, metadata
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return False, "", {}


def install_dependencies():
    """Install additional dependencies if needed"""
    packages = ['PyMuPDF', 'pdf2image']
    for package in packages:
        try:
            __import__(package.lower().replace('-', '_'))
        except ImportError:
            logger.info(f"Installing {package}...")
            os.system(f"pip install {package}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Ultra OCR - Advanced PDF text recognition with ultra-thin layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets:
  ultra    - Maximum quality, slower processing (600 DPI, full enhancement)
  balanced - Good quality and speed balance (300 DPI, moderate enhancement)
  fast     - Fast processing, lower quality (200 DPI, no enhancement)
  japanese - Optimized for Japanese vertical text (400 DPI, special settings)

Examples:
  # Ultra quality processing
  python pdf_ocr_ultra.py input.pdf --preset ultra
  
  # Fast processing for preview
  python pdf_ocr_ultra.py input.pdf --preset fast
  
  # Japanese document with text extraction
  python pdf_ocr_ultra.py japanese_doc.pdf --preset japanese --save-text
  
  # Parallel processing with 8 threads
  python pdf_ocr_ultra.py large_doc.pdf --threads 8
  
  # Custom language combination
  python pdf_ocr_ultra.py mixed_doc.pdf -l jpn+eng+chi_sim
        """
    )
    
    parser.add_argument('input', help='Input PDF file')
    parser.add_argument('-o', '--output', help='Output PDF path')
    parser.add_argument('-l', '--language', default='jpn+eng',
                       help='OCR language (default: jpn+eng)')
    parser.add_argument('--preset', choices=['ultra', 'fast', 'balanced', 'japanese'],
                       default='balanced', help='Processing preset')
    parser.add_argument('--threads', type=int,
                       help='Number of threads for parallel processing')
    parser.add_argument('--save-text', action='store_true',
                       help='Save extracted text to separate file')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    install_dependencies()
    
    processor = UltraOCRProcessor(
        language=args.language,
        preset=args.preset,
        threads=args.threads
    )
    
    success, output_path, metadata = processor.process_pdf_ultra(
        args.input,
        args.output,
        args.save_text
    )
    
    if success:
        print(f"\n✓ Successfully created ultra-thin searchable PDF")
        print(f"  Output: {output_path}")
        print(f"  Pages: {metadata['pages']}")
        print(f"  Time: {metadata['processing_time']:.2f}s")
        print(f"  Confidence: {metadata['avg_confidence']:.1f}%")
        print(f"  Size: {metadata['file_size_mb']:.2f} MB")
        print(f"\nYou can now select and copy text from the PDF!")
    else:
        print(f"\n✗ Processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()