import asyncio, sys
sys.path.insert(0, r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent')
from tools.browser_agent import connect_takeover, take_screenshot
import datetime

async def main():
    print('Attaching to CDP at port 9222...')
    browser, ctx, pages = await connect_takeover(verbose=True)
    if not browser:
        print('CDP attach failed - will fall back to fresh launch')
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        await take_screenshot('http://127.0.0.1:8000/static/northstar-os/index.html#/sourcescout', use_chrome=True)
        return
    
    print(f'Attached! Contexts: {len(browser.contexts)}, Pages: {len(pages)}')
    
    page = pages[0] if pages else await ctx.new_page()
    await page.goto('http://127.0.0.1:8000/static/northstar-os/index.html#/sourcescout', wait_until='networkidle', timeout=30000)
    print('Navigated to Sourcescout')
    
    await page.wait_for_timeout(5000)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_path = f'generated_images/screenshots/sourcescout_proof_{ts}.png'
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f'Screenshot saved: {screenshot_path}')
    print('=== PROOF COMPLETE ===')

asyncio.run(main())