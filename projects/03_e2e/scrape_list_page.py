import re
from playwright.sync_api import sync_playwright

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
        
        # We need to get all links from this page
        links = page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a'));
            return anchors.map(a => ({text: a.innerText.trim(), href: a.href}));
        }""")
        
        video_pages = {}
        for link in links:
            href = link['href']
            text = link['text']
            # Only keep links that point to pages and have text that looks like "特別授業" or numbers
            if '/member/page.html?id=' in href and text and "特別授業" in text:
                if href not in video_pages or len(text) > len(video_pages[href]['text']):
                    video_pages[href] = link
                    
        print(f"Found {len(video_pages)} potential video pages in 一覧.")
        for href, data in video_pages.items():
            print(f"- {data['text']}: {href}")
            
        browser.close()

if __name__ == "__main__":
    run()
