from playwright.sync_api import sync_playwright
import time


def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto("https://store.steampowered.com/app/105600/Terraria/")

        add_btn = page.query_selector(".btn_addtocart a")
        if add_btn:
            add_btn.click()
            time.sleep(2)
            page.goto("https://store.steampowered.com/cart/")

        page.wait_for_load_state("networkidle")

        print("\nSearching for 'Continue to payment' button...")
        buttons = page.get_by_text("Continue to payment").all()
        for i, btn in enumerate(buttons):
            print(f"Match {i}: {btn.evaluate('el => el.outerHTML')}")

        browser.close()


if __name__ == "__main__":
    verify()
