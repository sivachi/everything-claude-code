#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kindle Batch Capture Tool (02_kindle_capture_batch.py)

Captures all books in the Kindle Library automatically.
REQUIREMENTS:
1. Kindle app must be in "List View" (Cmd+2).
2. The first book to capture must be selected in the list.
3. "Screen Recording" and "Accessibility" permissions for this terminal.

Usage:
    python3 02_kindle_capture_batch.py -o ./kindle_books
"""

import os
import sys
import time
import subprocess
import datetime
from pathlib import Path
import argparse

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:
    print("Installing required package Pillow ...")
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "--user"])
    from PIL import Image, ImageChops, ImageStat


# ---------- AppleScript / macOS helpers ----------

def run_osascript(script: str):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def activate_kindle():
    script = '''
    tell application "Amazon Kindle" to activate
    '''
    run_osascript(script)

def send_key(key_code_str):
    """Send a specific key code via System Events"""
    script = f'''
    tell application "System Events"
        key code {key_code_str}
    end tell
    '''
    run_osascript(script)

def send_enter():
    send_key("36")

def send_cmd_l():
    """Cmd+L to return to Library"""
    script = '''
    tell application "System Events"
        keystroke "l" using command down
    end tell
    '''
    run_osascript(script)

def send_down_arrow():
    send_key("125")

def send_right_arrow():
    """Next page"""
    send_key("124")

def send_left_arrow():
    """Previous page (sometimes needed for vertical books if mapped differently, but usually Right is forward)"""
    send_key("123")


# ---------- Capture & Image Analysis ----------

def capture_screen_to_pil(rect=None):
    """
    Captures screen.
    rect: (x, y, w, h) or None for full screen.
    Returns PIL Image.
    """
    filesuffix = f"tmp_{int(time.time()*1000)}.png"
    filepath = f"/tmp/{filesuffix}"
    
    args = ["screencapture", "-x", "-o"] # -o: no shadow
    if rect:
        args += ["-R", f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}"]
    args.append(filepath)
    
    subprocess.run(args, capture_output=True)
    
    if os.path.exists(filepath):
        img = Image.open(filepath).convert("RGB")
        try:
            os.remove(filepath)
        except:
            pass
        return img
    return None

def images_are_identical(img1, img2, threshold=5):
    """
    Returns True if img1 and img2 are effectively identical.
    threshold: allowed pixel difference average (0=exact match).
    """
    if img1 is None or img2 is None:
        return False
    # Resize to speed up comparison if large? No, difference is fast enough usually.
    # Just ensure sizes match
    if img1.size != img2.size:
        return False # Size changed, definitely different
    
    diff = ImageChops.difference(img1, img2)
    bbox = diff.getbbox()
    if bbox is None:
        return True # Exact match
    
    # Calculate stats
    stat = ImageStat.Stat(diff)
    # Average difference per band
    avg_diff = sum(stat.mean) / len(stat.mean)
    return avg_diff < threshold


# ---------- Main Logic ----------

def get_timestamp_name(index):
    now = datetime.datetime.now()
    return f"book_{now.strftime('%Y%m%d_%H%M%S')}_{index:03d}.pdf"

def wait_for_loading(delay):
    # Dynamic wait could be better, but fixed delay is safer for now
    time.sleep(delay)

def capture_single_book(output_path, delay=1.5, progress_callback=None):
    """
    Captures pages until end of book is detected.
    Returns: (success, page_count)
    """
    pages = []
    
    # Wait for book to open animation
    wait_for_loading(3.0) 
    
    # Loop capture
    page_num = 0
    consecutive_dupes = 0
    
    print("    Starting book capture...")
    
    while True:
        page_num += 1
        img = capture_screen_to_pil()
        
        if img is None:
            print("    [Error] Failed to capture screen.")
            break
            
        # Check against previous page
        if len(pages) > 0:
            if images_are_identical(pages[-1], img):
                print(f"    [End] Page {page_num} is identical to previous. Book finished.")
                break
        
        pages.append(img)
        print(f"    captured page {page_num}")
        
        # Turn page
        send_right_arrow()
        wait_for_loading(delay)
        
        # Safety break
        if page_num > 2000:
            print("    [Limit] Reached 2000 pages, stopping safety.")
            break

    if not pages:
        return False, 0

    # Save PDF
    print(f"    Saving PDF ({len(pages)} pages) to {output_path} ...")
    if len(pages) == 1:
        pages[0].save(output_path, resolution=150.0)
    else:
        pages[0].save(output_path, save_all=True, append_images=pages[1:], resolution=150.0)
        
    return True, len(pages)


def run_batch_capture(output_dir, delay):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Output Directory: {output_dir}")
    print("Switch to Kindle window in 5 seconds... Please select the first book in LIST view.")
    time.sleep(5)
    
    activate_kindle()
    time.sleep(1)
    
    book_index = 1
    
    while True:
        print(f"\n[Book {book_index}] Processing...")
        
        # 1. Capture Library State (to check if we moved later)
        library_img_before = capture_screen_to_pil()
        
        # 2. Open Book
        send_enter()
        
        # 3. Check if we actually entered a book?
        # A simple check: wait 3s, capture, compare with library_img_before
        time.sleep(3)
        current_img = capture_screen_to_pil()
        
        if images_are_identical(library_img_before, current_img, threshold=10):
            print("    [Warning] Screen did not change after pressing Enter. Are we at the end of the list or unable to open?")
            # Try once more? Or just stop?
            # If we are at the end, maybe we just selected nothing?
            # Let's assume end of list if we can't open a book.
            print("    Stopping batch process.")
            break

        # 4. Capture Book Content
        pdf_name = get_timestamp_name(book_index)
        pdf_path = output_dir / pdf_name
        
        success, page_count = capture_single_book(pdf_path, delay=delay)
        
        if success:
            print(f"    [Done] Saved {pdf_name}")
        else:
            print("    [Skip] Could not capture any pages.")

        # 5. Return to Library
        print("    Returning to Library...")
        send_cmd_l()
        time.sleep(3) # Wait for library to load
        
        # 6. Verify we are back in library (compare with before open)
        # Ideally current screen should resemble library_img_before, but selection might be same.
        # We just trust Cmd+L works.
        
        # 7. Move to Next Book
        print("    Moving to next book in list...")
        
        # Take verification shot before moving
        library_img_at_row = capture_screen_to_pil()
        
        send_down_arrow()
        time.sleep(1)
        
        # 8. Check if selection moved
        library_img_after_move = capture_screen_to_pil()
        
        if images_are_identical(library_img_at_row, library_img_after_move, threshold=2):
            print("    [End] Selection did not move (Screen identical after Down Arrow).")
            print("    Batch capture completed!")
            break
            
        book_index += 1


def main():
    parser = argparse.ArgumentParser(description="Kindle Batch Capture")
    parser.add_argument('-o', '--output', required=True, help='Output directory for PDFs')
    parser.add_argument('-d', '--delay', type=float, default=1.5, help='Page turn delay (seconds)')
    
    args = parser.parse_args()
    
    try:
        run_batch_capture(args.output, args.delay)
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    main()
