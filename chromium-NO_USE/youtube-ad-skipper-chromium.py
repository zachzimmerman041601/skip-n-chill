"""
YouTube Ad Skipper using Playwright
Automatically clicks skip buttons on YouTube ads with real browser clicks.

Install: pip install playwright && playwright install chromium
Run: python youtube_ad_skipper.py
"""

import asyncio
from playwright.async_api import async_playwright

SKIP_SELECTORS = [
    '.ytp-skip-ad-button',
    '[id^="skip-button"]',
    '.ytp-ad-skip-button',
    '.ytp-ad-skip-button-modern',
]

OVERLAY_CLOSE = '.ytp-ad-overlay-close-button'


async def skip_ads(page):
    """Check for and click skip buttons."""
    for selector in SKIP_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=100):
                await btn.click()
                print(f'[Ad Skipper] Clicked: {selector}')
                return True
        except:
            pass
    return False


async def close_overlay(page):
    """Close overlay ads."""
    try:
        btn = page.locator(OVERLAY_CLOSE).first
        if await btn.is_visible(timeout=100):
            await btn.click()
            print('[Ad Skipper] Closed overlay ad')
    except:
        pass


async def main():
    async with async_playwright() as p:
        # Launch browser with persistent context to save login
        browser = await p.chromium.launch_persistent_context(
            user_data_dir='./youtube_profile',
            headless=False,
            args=['--start-maximized'],
            no_viewport=True
        )
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto('https://www.youtube.com')
        
        print('[Ad Skipper] Browser launched. Navigate to any video.')
        print('[Ad Skipper] Watching for ads... (Ctrl+C to quit)')
        
        # Main loop - check for skip button every 500ms
        while True:
            try:
                await skip_ads(page)
                await close_overlay(page)
                await asyncio.sleep(0.5)
            except Exception as e:
                # Page might be navigating, just continue
                await asyncio.sleep(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[Ad Skipper] Stopped.')