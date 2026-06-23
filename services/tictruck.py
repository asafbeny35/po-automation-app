from playwright.sync_api import sync_playwright

def open_new_transport(po):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            storage_state="tictruck_state.json"
        )

        page = context.new_page()
        page.goto("https://bgavriel.tictruck.co.il/app/2.1/")

        page.wait_for_timeout(10000)

        # חדש
        page.get_by_text("חדש", exact=True).click()
        page.wait_for_timeout(3000)

        # לקוח
        customer_input = page.locator('input[name="ordering_customer_id"]')
        customer_input.click()
        customer_input.fill(po.customer_name)

        page.wait_for_timeout(2000)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")

        # מוצא
        origin_company = page.locator('input[name="dispatcher_customer_id"]')
        origin_company.click()
        origin_company.fill("בן יעקב פתרונות טקסטיל")

        page.wait_for_timeout(2000)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")

        # חיפה
        origin_location = page.locator('input[name="origin_location_id"]')
        origin_location.click()
        origin_location.fill("חיפה")

        page.wait_for_timeout(2000)
        page.get_by_role("option", name="חיפה", exact=True).click()

        print("🟢 הכל מוכן — הדפדפן נשאר פתוח")

        # 🔥 זה הסוד — לא יוצאים מה-context
        page.wait_for_timeout(999999999)
