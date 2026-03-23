from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://mentre.net/l/m/lS19sAGvax1Cor")
        page.wait_for_timeout(2000)
        
        # Take a screenshot to see what it looks like before login
        page.screenshot(path="pre_login.png")
        
        # We need to figure out the selectors
        print(page.content())
        
        browser.close()

run()
