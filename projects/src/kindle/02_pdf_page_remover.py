#!/usr/bin/env python3
"""
PDF Page Remover - PDFの指定したページを削除・抽出するツール

主な機能:
- 指定したページを削除 (--remove "3,5,7-10")
- 指定したページのみ保持 (--keep "1-5,10")
- ページ範囲を抽出 (--extract 10 20)
- PDFを個別ファイルに分割 (--split)
- ページ情報の表示 (--info)

使用例:
# ページ2,4-6を削除
python3 pdf_page_remover.py input.pdf --remove "2,4-6"

# ページ1-5と10のみ保持
python3 pdf_page_remover.py input.pdf --keep "1-5,10"

# ページ10から20を抽出
python3 pdf_page_remover.py input.pdf --extract 10 20

# PDFを個別ページに分割
python3 pdf_page_remover.py input.pdf --split

# ページ情報を表示
python3 pdf_page_remover.py input.pdf --info

PyMuPDFを使用しているため高速で、日本語PDFにも対応しています。
"""

import os
import sys
import argparse
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Union, Set
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PDFPageRemover:
    """PDF page manipulation tool"""
    
    def __init__(self, input_path: str):
        """
        Initialize PDF page remover
        
        Args:
            input_path: Path to input PDF file
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"PDF file not found: {input_path}")
        
        self.input_path = input_path
        self.doc = fitz.open(input_path)
        self.total_pages = len(self.doc)
        logger.info(f"Loaded PDF with {self.total_pages} pages")
    
    def parse_page_ranges(self, page_spec: str) -> Set[int]:
        """
        Parse page specification string to page numbers
        
        Args:
            page_spec: Page specification (e.g., "1,3,5-8,10")
            
        Returns:
            Set of page numbers (0-indexed)
        """
        pages = set()
        
        for part in page_spec.split(','):
            part = part.strip()
            
            if '-' in part:
                # Range specification
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                
                # Convert to 0-indexed
                start = max(1, start) - 1
                end = min(self.total_pages, end) - 1
                
                for i in range(start, end + 1):
                    pages.add(i)
            else:
                # Single page
                page_num = int(part.strip())
                # Convert to 0-indexed
                page_idx = max(1, min(self.total_pages, page_num)) - 1
                pages.add(page_idx)
        
        return pages
    
    def remove_pages(self, pages_to_remove: Union[str, List[int]], 
                     output_path: str = None) -> str:
        """
        Remove specified pages from PDF
        
        Args:
            pages_to_remove: Page specification string or list of page numbers (1-indexed)
            output_path: Output file path
            
        Returns:
            Path to output file
        """
        if isinstance(pages_to_remove, str):
            remove_indices = self.parse_page_ranges(pages_to_remove)
        else:
            # Convert 1-indexed to 0-indexed
            remove_indices = {p - 1 for p in pages_to_remove if 1 <= p <= self.total_pages}
        
        if not remove_indices:
            logger.warning("No valid pages to remove")
            return self.input_path
        
        # Create output path if not specified
        if output_path is None:
            base_name = Path(self.input_path).stem
            suffix = Path(self.input_path).suffix
            output_path = str(Path(self.input_path).parent / f"{base_name}_removed{suffix}")
        
        # Create new document with remaining pages
        output_doc = fitz.open()
        pages_kept = 0
        
        for page_idx in range(self.total_pages):
            if page_idx not in remove_indices:
                output_doc.insert_pdf(self.doc, from_page=page_idx, to_page=page_idx)
                pages_kept += 1
        
        # Save output
        output_doc.save(output_path, garbage=4, deflate=True)
        output_doc.close()
        
        logger.info(f"Removed {len(remove_indices)} pages, kept {pages_kept} pages")
        logger.info(f"Saved to: {output_path}")
        
        return output_path
    
    def keep_pages(self, pages_to_keep: Union[str, List[int]], 
                   output_path: str = None) -> str:
        """
        Keep only specified pages
        
        Args:
            pages_to_keep: Page specification string or list of page numbers (1-indexed)
            output_path: Output file path
            
        Returns:
            Path to output file
        """
        if isinstance(pages_to_keep, str):
            keep_indices = self.parse_page_ranges(pages_to_keep)
        else:
            # Convert 1-indexed to 0-indexed
            keep_indices = {p - 1 for p in pages_to_keep if 1 <= p <= self.total_pages}
        
        if not keep_indices:
            logger.warning("No valid pages to keep")
            return self.input_path
        
        # Create output path if not specified
        if output_path is None:
            base_name = Path(self.input_path).stem
            suffix = Path(self.input_path).suffix
            output_path = str(Path(self.input_path).parent / f"{base_name}_extracted{suffix}")
        
        # Create new document with selected pages
        output_doc = fitz.open()
        
        # Sort page indices to maintain order
        for page_idx in sorted(keep_indices):
            output_doc.insert_pdf(self.doc, from_page=page_idx, to_page=page_idx)
        
        # Save output
        output_doc.save(output_path, garbage=4, deflate=True)
        output_doc.close()
        
        logger.info(f"Kept {len(keep_indices)} pages out of {self.total_pages}")
        logger.info(f"Saved to: {output_path}")
        
        return output_path
    
    def split_pdf(self, output_dir: str = None, pages_per_file: int = None) -> List[str]:
        """
        Split PDF into multiple files
        
        Args:
            output_dir: Output directory
            pages_per_file: Pages per split file (None = single pages)
            
        Returns:
            List of output file paths
        """
        if output_dir is None:
            output_dir = Path(self.input_path).parent / f"{Path(self.input_path).stem}_split"
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        output_files = []
        base_name = Path(self.input_path).stem
        
        if pages_per_file is None:
            pages_per_file = 1
        
        for start_idx in range(0, self.total_pages, pages_per_file):
            end_idx = min(start_idx + pages_per_file - 1, self.total_pages - 1)
            
            # Create output document
            output_doc = fitz.open()
            output_doc.insert_pdf(self.doc, from_page=start_idx, to_page=end_idx)
            
            # Generate filename
            if pages_per_file == 1:
                output_path = output_dir / f"{base_name}_page_{start_idx + 1:04d}.pdf"
            else:
                output_path = output_dir / f"{base_name}_pages_{start_idx + 1:04d}-{end_idx + 1:04d}.pdf"
            
            # Save
            output_doc.save(str(output_path), garbage=4, deflate=True)
            output_doc.close()
            output_files.append(str(output_path))
        
        logger.info(f"Split into {len(output_files)} files")
        return output_files
    
    def extract_range(self, start_page: int, end_page: int, 
                     output_path: str = None) -> str:
        """
        Extract a range of pages
        
        Args:
            start_page: Start page number (1-indexed)
            end_page: End page number (1-indexed)
            output_path: Output file path
            
        Returns:
            Path to output file
        """
        # Convert to 0-indexed
        start_idx = max(0, min(start_page - 1, self.total_pages - 1))
        end_idx = max(0, min(end_page - 1, self.total_pages - 1))
        
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        
        # Create output path if not specified
        if output_path is None:
            base_name = Path(self.input_path).stem
            suffix = Path(self.input_path).suffix
            output_path = str(Path(self.input_path).parent / 
                            f"{base_name}_pages_{start_page}-{end_page}{suffix}")
        
        # Create new document
        output_doc = fitz.open()
        output_doc.insert_pdf(self.doc, from_page=start_idx, to_page=end_idx)
        
        # Save output
        output_doc.save(output_path, garbage=4, deflate=True)
        output_doc.close()
        
        pages_extracted = end_idx - start_idx + 1
        logger.info(f"Extracted {pages_extracted} pages ({start_page} to {end_page})")
        logger.info(f"Saved to: {output_path}")
        
        return output_path
    
    def get_page_info(self) -> List[dict]:
        """
        Get information about all pages
        
        Returns:
            List of page information dictionaries
        """
        page_info = []
        
        for i, page in enumerate(self.doc):
            info = {
                'page_number': i + 1,
                'width': page.rect.width,
                'height': page.rect.height,
                'rotation': page.rotation,
                'text_length': len(page.get_text()),
                'images': len(page.get_images()),
                'links': len(page.get_links())
            }
            page_info.append(info)
        
        return page_info
    
    def close(self):
        """Close the PDF document"""
        if self.doc:
            self.doc.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PDF Page Remover - Remove or extract specific pages from PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Page specification format:
  - Single pages: 1,3,5,7
  - Ranges: 1-5,10-15
  - Mixed: 1,3-5,8,10-12

Examples:
  # Remove pages 3, 5, and 7-10
  python pdf_page_remover.py input.pdf --remove "3,5,7-10"
  
  # Keep only pages 1-5 and 10
  python pdf_page_remover.py input.pdf --keep "1-5,10"
  
  # Extract pages 10 to 20
  python pdf_page_remover.py input.pdf --extract 10 20
  
  # Split PDF into single pages
  python pdf_page_remover.py input.pdf --split
  
  # Split PDF into chunks of 5 pages
  python pdf_page_remover.py input.pdf --split --chunk-size 5
  
  # Get page information
  python pdf_page_remover.py input.pdf --info
        """
    )
    
    parser.add_argument('input', help='Input PDF file')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('--remove', help='Pages to remove (e.g., "1,3,5-8")')
    parser.add_argument('--keep', help='Pages to keep (e.g., "1-5,10")')
    parser.add_argument('--extract', nargs=2, type=int, metavar=('START', 'END'),
                       help='Extract page range')
    parser.add_argument('--split', action='store_true', 
                       help='Split PDF into separate files')
    parser.add_argument('--chunk-size', type=int, default=1,
                       help='Pages per split file (default: 1)')
    parser.add_argument('--split-dir', help='Output directory for split files')
    parser.add_argument('--info', action='store_true',
                       help='Show page information')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        with PDFPageRemover(args.input) as remover:
            
            if args.info:
                # Show page information
                page_info = remover.get_page_info()
                print(f"\nPDF Information: {args.input}")
                print(f"Total pages: {len(page_info)}")
                print("\nPage details:")
                for info in page_info:
                    print(f"  Page {info['page_number']:3d}: "
                          f"{info['width']:.0f}x{info['height']:.0f}px, "
                          f"Text: {info['text_length']} chars, "
                          f"Images: {info['images']}, "
                          f"Links: {info['links']}")
                return
            
            # Process based on operation
            if args.remove:
                output = remover.remove_pages(args.remove, args.output)
                print(f"\n✓ Pages removed successfully")
                print(f"  Output: {output}")
                
            elif args.keep:
                output = remover.keep_pages(args.keep, args.output)
                print(f"\n✓ Pages extracted successfully")
                print(f"  Output: {output}")
                
            elif args.extract:
                start, end = args.extract
                output = remover.extract_range(start, end, args.output)
                print(f"\n✓ Page range extracted successfully")
                print(f"  Output: {output}")
                
            elif args.split:
                outputs = remover.split_pdf(args.split_dir, args.chunk_size)
                print(f"\n✓ PDF split into {len(outputs)} files")
                if len(outputs) <= 10:
                    for output in outputs:
                        print(f"  - {output}")
                else:
                    print(f"  Output directory: {Path(outputs[0]).parent}")
                    
            else:
                print("No operation specified. Use --help for usage information.")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()