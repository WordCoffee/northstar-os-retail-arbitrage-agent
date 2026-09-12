"""Minimal test to find where Chrome launch hangs."""
import sys
import asyncio

async def main():
    print("Step 1: importing playwright...", flush=True)
    from playwright.async_api import async_playwright
    
    print("Step 2: starting playwright...", flush=True)
    async with async_playwright() as p:
        print("Step 3: launching Chrome (not persistent)...", flush=True)
        browser = await p.chromium.launch(
            headless=False,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        print("Step 4: Chrome launched OK!", flush=True)
        page = await browser.new_page(viewport={"width": 1024, "height": 768})
        print("Step 5: navigating to cloudflare...", flush=True)
        await page.goto("https://cloudflare.com/sign-up", wait_until="domcontentloaded", timeout=60000)
        print("Step 6: page loaded!", flush=True)
        await page.wait_for_timeout(2000)
        
        # Try to find email field
        email_sel = "input[type='email'], input[name='email'], input#email"
        loc = page.locator(email_sel).first
        count = await loc.count()
        print(f"Step 7: found {count} email field(s)", flush=True)
        
        if count > 0:
            await loc.fill("MograOrganics@gmail.com")
            print("Step 8: email filled!", flush=True)
        
        # Try password
        pass_sel = "input[type='password'], input[name='password']"
        loc2 = page.locator(pass_sel).first
        count2 = await loc2.count()
        print(f"Step 9: found {count2} password field(s)", flush=True)
        
        if count2 > 0:
            await loc2.fill("Xk9mP2vL7nQ4wR")
            print("Step 10: password filled!", flush=True)
        
        await page.screenshot(path="generated_images/screenshots/test_chrome_signup.png")
        print("Step 11: screenshot saved!", flush=True)
        
        await page.wait_for_timeout(5000)
        await browser.close()
        print("DONE", flush=True)

asyncio.run(main())
