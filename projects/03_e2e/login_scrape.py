from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://mentre.net/l/m/lS19sAGvax1Cor")
        page.wait_for_timeout(2000)
        
        # Fill login form
        page.fill("input#UserLoginid", "iloliwakuwakudokidoki@gmail.com")
        page.fill("input#UserPassword", "LR7kTRsVrf%u3W=P")
        page.click("input[type=submit]")
        page.wait_for_timeout(3000)
        
        page.screenshot(path="post_login.png")
        
        print("--- PAGE URL AFTER LOGIN ---")
        print(page.url)
        print("--- LINKS ---")
        links = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}))")
        for link in links:
            print(link)
            
        print("--- IFRAMES ---")
        iframes = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(i => i.src)")
        for src in iframes:
            print(src)
            
        browser.close()

run()
