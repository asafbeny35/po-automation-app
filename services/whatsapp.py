from __future__ import annotations

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

from .config import settings


async def send_files_via_whatsapp_web(files: list[Path], caption: str) -> None:
    recipient = settings.whatsapp_recipient
    if not recipient:
        raise RuntimeError("WHATSAPP_RECIPIENT is missing.")

    storage_state_path = Path(settings.whatsapp_storage_state)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.whatsapp_headless)
        context_kwargs = {}
        if storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto(f"https://web.whatsapp.com/send?phone={recipient}")

        # First-time login flow: scan the QR and save session state.
        try:
            await page.wait_for_selector('div[contenteditable="true"][data-tab="3"]', timeout=15000)
        except Exception:
            print("Scan the WhatsApp QR code in the opened browser window.")
            await page.wait_for_selector('div[contenteditable="true"][data-tab="3"]', timeout=120000)
            await context.storage_state(path=str(storage_state_path))

        attach_btn = page.locator('button[title="Attach"], span[data-icon="plus-rounded"]')
        await attach_btn.first.wait_for(timeout=20000)
        await attach_btn.first.click()

        file_input = page.locator('input[type="file"]')
        await file_input.first.set_input_files([str(f) for f in files])

        caption_box = page.locator('div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"]')
        await caption_box.first.wait_for(timeout=20000)
        await caption_box.first.fill(caption)

        send_btn = page.locator('span[data-icon="send"], button[aria-label="Send"]')
        await send_btn.first.click()

        await asyncio.sleep(5)
        await context.storage_state(path=str(storage_state_path))
        await context.close()
        await browser.close()
