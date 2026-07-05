import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        # Create a page with responsive desktop resolution
        page = await browser.new_page(viewport={"width": 1440, "height": 1080})
        
        # Navigate to local Streamlit
        print("Navigating to http://localhost:8501 ...")
        await page.goto("http://localhost:8501")
        
        # Wait for streamlit main view to load
        print("Waiting for dashboard to render...")
        await page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        # Extra wait to ensure all elements and graphics are settled
        await asyncio.sleep(5)
        
        # Ensure target assets directory exists
        os.makedirs("assets", exist_ok=True)
        
        # 1. Capture TAB 1: Paste Review Analysis (default active tab)
        print("Capturing Tab 1: Paste Review Analysis...")
        await page.screenshot(path="assets/screenshot_analyze.png", full_page=False)
        
        # Helper to click a tab by finding a button containing text
        async def click_tab(tab_name):
            tab_locator = page.locator(f"button[data-baseweb='tab']:has-text('{tab_name}')")
            if await tab_locator.count() == 0:
                # Fallback to general button search
                tab_locator = page.locator(f"button:has-text('{tab_name}')")
            
            if await tab_locator.count() > 0:
                await tab_locator.click()
                print(f"Clicked tab: {tab_name}")
                await asyncio.sleep(3) # Wait for page contents to render
                return True
            else:
                print(f"Tab button not found: {tab_name}")
                return False

        # 2. Capture TAB 2: Compare Products
        if await click_tab("Compare Products"):
            await page.screenshot(path="assets/screenshot_compare.png")
            
        # 3. Capture TAB 3: Product Lookup with a sample search
        if await click_tab("Product Lookup"):
            # Locate search input field
            search_input = page.locator("input[aria-label='Brand name, product name, or product ID']").first
            if await search_input.count() == 0:
                search_input = page.locator("input[placeholder*='e.g. LANEIGE']").first
            
            if await search_input.count() > 0:
                print("Typing search query in Product Lookup...")
                await search_input.fill("The True Cream Aqua Bomb")
                await search_input.press("Enter")
                # Wait for database queries & charts to finish rendering
                await asyncio.sleep(5)
                # Take screenshot
                await page.screenshot(path="assets/screenshot_lookup.png")
            else:
                print("Search input field not found on Product Lookup tab.")
                await page.screenshot(path="assets/screenshot_lookup_empty.png")

        # 4. Capture TAB 4: Database Explorer
        if await click_tab("Database Explorer"):
            await page.screenshot(path="assets/screenshot_explorer.png")
            
        # 5. Capture TAB 5: Seed Data
        if await click_tab("Seed Data"):
            await page.screenshot(path="assets/screenshot_seed.png")
            
        # 6. Capture TAB 6: Ask / About
        if await click_tab("Ask / About"):
            # Scroll down to capture the Q&A Assistant and Portfolio layout nicely
            await page.screenshot(path="assets/screenshot_about.png")
            
        await browser.close()
        print("All screenshots captured and saved to 'assets/' folder!")

if __name__ == "__main__":
    asyncio.run(main())
