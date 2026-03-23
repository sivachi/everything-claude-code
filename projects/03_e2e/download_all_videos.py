import re
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "/Users/tadaakikurata/works/原田メソッド"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_filename(name):
    # Some titles have special characters, replace them with safe ones or space
    return re.sub(r'[\\/*?:"<>|]', " ", name).strip()

def run():
    print("Starting browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Logging in...")
        page.goto("https://mentre.net/l/m/lS19sAGvax1Cor")
        page.wait_for_timeout(2000)
        
        page.fill("input#UserLoginid", "iloliwakuwakudokidoki@gmail.com")
        page.fill("input#UserPassword", "LR7kTRsVrf%u3W=P")
        page.click("input[type=submit]")
        page.wait_for_timeout(3000)
        
        print("Going to 一覧 page...")
        page.goto("https://mentre.net/sp/eDflcMn5/zTRe9jAc/member/page.html?id=VFHnPPH1")
        page.wait_for_timeout(3000)
        
        # Get all page links from the list
        links = page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a'));
            return anchors.map(a => ({text: a.innerText.trim(), href: a.href}));
        }""")
        
        video_pages = {}
        for link in links:
            href = link['href']
            text = link['text']
            if '/member/page.html?id=' in href and text and "特別授業" in text:
                if href not in video_pages or len(text) > len(video_pages[href]['text']):
                    video_pages[href] = link
        
        print(f"Found {len(video_pages)} potential video pages.")
        
        # Now visit each page and extract iframe
        for i, (href, link_data) in enumerate(video_pages.items(), 1):
            title = link_data['text']
            if not title:
                title = f"video_{i}"
            
            # Make title filename safe
            title = sanitize_filename(title)
            
            # Skip if we already have it. Need to check if there's any file matching this title
            existing_files = list(Path(OUTPUT_DIR).glob(f"{title}.*"))
            # yt-dlp saves with extension. We just check if any file starts with this title (not .part)
            already_downloaded = False
            for ef in existing_files:
                if not str(ef).endswith('.part') and not str(ef).endswith('.ytdl'):
                    already_downloaded = True
                    break
                    
            if already_downloaded:
                print(f"[{i}/{len(video_pages)}] Already downloaded {title}. Skipping...")
                continue
                
            print(f"[{i}/{len(video_pages)}] Visiting {title}: {href}")
            try:
                page.goto(href, timeout=30000)
                page.wait_for_timeout(2000)
                
                iframes = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(i => i.src)")
                vimeo_urls = [src for src in iframes if 'vimeo.com' in src]
                
                if not vimeo_urls:
                    print(f"No Vimeo iframe found on {title}. Skipping.")
                    continue
                    
                for j, vimeo_url in enumerate(vimeo_urls):
                    vid_title = title if len(vimeo_urls) == 1 else f"{title}_{j+1}"
                    out_path = os.path.join(OUTPUT_DIR, f"{vid_title}.%(ext)s")
                    
                    print(f"  -> Downloading {vimeo_url}")
                    cmd = [
                        "yt-dlp",
                        "--referer", "https://mentre.net/",
                        "--no-overwrites",
                        "-o", out_path,
                        vimeo_url
                    ]
                    
                    subprocess.run(cmd, check=True)
                    print(f"  -> Successfully downloaded {vid_title}")
                    
            except Exception as e:
                print(f"Error on {title}: {e}")

        print("Finished downloading all videos.")
        browser.close()

if __name__ == "__main__":
    run()
